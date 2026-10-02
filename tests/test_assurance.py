"""Deterministic semantic and negative-evidence checks, not deployed software tests."""
import copy,itertools,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from repair.model import (validate,State,initial,advance,act,event,observe,actions,loss)
from repair.check import (Machine,start,run,options,observation,distance,
                          check_certificate,policy_replay,strict_json)
from repair.solve import synthesize,extract_core
from repair.oracle import exact_oracle
from repair.cases import chain,mechanism_cases,guarded_spec,observed_guarded_spec,expand_guarded
from repair.symbolic import BDD,full_rank,classify_contract,check_obstruction
from repair.causality_pilot import replay_two_tail


def complete(case):
    certificate=synthesize(case)
    out=check_certificate(case,certificate)
    policy_replay(case,certificate)
    assert exact_oracle(case)['value']==out['value']
    return out['value']


class SchemaTests(unittest.TestCase):
    def test_malformed_cases(self):
        base=chain(2)
        mutations=[('bits',True),('bits',0),('bits',9),('registers',0),
            ('memory_size',0),('program',[]),('metric',[]),('metric','edit'),
            ('budget',-1),('budget',True),('weights',[]),('weights',[1,True]),
            ('read_actions',[]),('read_actions',[0,0]),('read_actions',[{}]),
            ('read_actions',[True]),('read_actions',[2]),('worlds',[])]
        for key,value in mutations:
            c=copy.deepcopy(base);c[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate(c)
        for instruction in (['emit','r00'],['emit','r١'],['emit','r'+('9'*10000)],
                ['emit','r1'],['branch',1,0],['load',False,0],['bad']):
            c=copy.deepcopy(base);c['program'][0]=instruction
            with self.subTest(instruction=instruction[:2]),self.assertRaises(ValueError):validate(c)
        for faults in ([[]],[0,0],[1],[True],[99]):
            c=copy.deepcopy(base);c['worlds'][0]['faults']=faults
            with self.subTest(faults=faults),self.assertRaises(ValueError):validate(c)
        c=copy.deepcopy(base);c['worlds'][1]['id']=c['worlds'][0]['id']
        with self.assertRaises(ValueError):validate(c)
        c=copy.deepcopy(base);c['worlds'][0]['memory']=[0,True]
        with self.assertRaises(ValueError):validate(c)
        c=copy.deepcopy(base);c['unknown']=1
        with self.assertRaises(ValueError):validate(c)

    def test_json_rejection(self):
        for text in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}',
                     '{"a":-Infinity}','{"a": [1,2,]}'):
            with self.subTest(text=text),self.assertRaises(ValueError):strict_json(text)
        self.assertEqual(strict_json('{"x":[0,1]}'),{'x':[0,1]})

    def test_resource_caps_are_unknown(self):
        c=chain(3)
        with self.assertRaises(RuntimeError):synthesize(c,node_limit=2)
        cert=synthesize(c)
        with self.assertRaises(ValueError):check_certificate(c,cert,max_nodes=2)
        for n in (0,True,200001):
            with self.assertRaises(ValueError):synthesize(c,node_limit=n)
        s,p=guarded_spec(3)
        with self.assertRaises(RuntimeError):classify_contract(s,p,node_limit=2)

        # The maximum declared explicit-world count must not depend on the host
        # recursion limit when each world contributes a single compatible path.
        root=Path(__file__).resolve().parents[1]
        boundary=root/'inputs'/'regression'/'oracle-1024-no-faults.json'
        result=exact_oracle(json.loads(boundary.read_text()))
        self.assertEqual(result,{'value':0,'hindsight':0,'path_count':1024,'combinations':1024})

        def cli(*args):
            return subprocess.run([sys.executable,'-m','repair.cli',*map(str,args)],
                                  cwd=root,text=True,capture_output=True,check=False)
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            normal=root/'inputs'/'correlated-xor.json'
            solved=cli('solve',normal)
            self.assertEqual((solved.returncode,json.loads(solved.stdout)['value']),(0,0))
            certificate=td/'certificate.json';certificate.write_text(solved.stdout)
            checked=cli('check',normal,certificate)
            self.assertEqual((checked.returncode,json.loads(checked.stdout)['check']['value']),(0,0))
            oracle=cli('oracle',normal)
            self.assertEqual((oracle.returncode,json.loads(oracle.stdout)['value']),(0,0))

            bounded=cli('symbolic',root/'inputs'/'implicit'/'guarded-20-mixed.json',
                        '--order','actions-first')
            bounded_error=json.loads(bounded.stderr)
            self.assertEqual(bounded.returncode,3)
            self.assertEqual((bounded_error['status'],bounded_error['stage']),
                             ('unknown-resource','semantic-search'))

            malformed=root/'inputs'/'regression'/'malformed-missing-fields.json'
            rejected=cli('solve',malformed);rejected_error=json.loads(rejected.stderr)
            self.assertEqual(rejected.returncode,2)
            self.assertEqual((rejected_error['status'],rejected_error['stage']),
                             ('rejected','input-validation'))


class InstructionTests(unittest.TestCase):
    def test_arithmetic_truth_tables(self):
        for bits in range(1,5):
            q=2**bits
            for op in ('xor','add','eq','lt'):
                for a in range(q):
                    for b in range(q):
                        c={'id':'instruction','bits':bits,'registers':3,'memory_size':1,
                            'program':[[op,2,'r0','r1'],['emit','r2']],
                            'worlds':[{'id':'w','memory':[0],'faults':[]}],
                            'metric':'hamming','weights':[1],'budget':0}
                        w=c['worlds'][0]
                        x=advance(c,w,State(0,(a,b,0),(0,)))
                        y=run(c,w,Machine(0,(a,b,0),(0,)))
                        target={'xor':a^b,'add':a+b,'eq':int(a==b),'lt':int(a<b)}[op]%q
                        self.assertEqual(x.trace,(target,));self.assertEqual(y.output,(target,))

    def test_all_mechanism_paths(self):
        count=0
        for c in mechanism_cases():
            validate(c)
            for w in c['worlds']:
                todo=[(initial(c,w),start(c,w))]
                while todo:
                    x,y=todo.pop();x=advance(c,w,x);y=run(c,w,y)
                    self.assertEqual((x.pc,x.regs,x.memory,x.trace),(y.counter,y.values,y.cells,y.output))
                    self.assertEqual(observe(c,x),observation(c,y));count+=1
                    if event(c,x)!='halt':
                        self.assertEqual(actions(c,x),options(c,y))
                        for a in actions(c,x):todo.append((act(c,x,a),run(c,w,y,choice=a)))
        # Exercise two terminal control-flow edges not present in the mechanism corpus:
        # a taken branch directly to the program end, and an explicit halt before emit.
        for program in ([['const',0,1],['branch','r0',4],['emit',0],['halt']],
                        [['halt'],['emit',1]]):
            c={'id':'terminal-edge','bits':1,'registers':1,'memory_size':1,
               'program':program,'worlds':[{'id':'w','memory':[0],'faults':[]}],
               'metric':'hamming','weights':[1],'budget':0}
            validate(c);w=c['worlds'][0]
            x=advance(c,w,initial(c,w));y=run(c,w,start(c,w))
            self.assertEqual((x.pc,x.regs,x.memory,x.trace),(y.counter,y.values,y.cells,y.output))
            self.assertEqual(event(c,x),'halt');self.assertEqual(observe(c,x),observation(c,y))
            self.assertEqual(x.trace,())
        self.assertGreater(count,100)

    def test_distance_tables_and_missing_words(self):
        c=chain(2);c['bits']=2;c['weights']=[2,3]
        seqs=[()]+[(a,) for a in range(4)]+list(itertools.product(range(4),repeat=2))
        for metric in ('hamming','l1','word'):
            c['metric']=metric
            for a in seqs:
                for b in seqs:
                    self.assertEqual(loss(c,a,b),distance(c,a,b))
                    self.assertEqual(loss(c,a,b),loss(c,b,a))
                    self.assertGreaterEqual(loss(c,a,b),0)
                    if a==b:self.assertEqual(loss(c,a,b),0)
        c['metric']='hamming';self.assertEqual(loss(c,(0,),()),4)
        c['metric']='l1';self.assertEqual(loss(c,(0,),()),6)
        c['metric']='word';self.assertEqual(loss(c,(0,),()),2)

    def test_bad_reference_rejected_by_both(self):
        c=chain(1);c['program'][0]=['load',0,1]
        with self.assertRaises(ValueError):synthesize(c)
        with self.assertRaises(ValueError):check_certificate(c,{'case':c['id'],'root':'0','value':0,'nodes':{'0':{}}})


class CertificateTests(unittest.TestCase):
    def test_value_dag_mutations(self):
        c=chain(3,1);good=synthesize(c);self.assertEqual(check_certificate(c,good)['value'],2)
        choice=next(k for k,v in good['nodes'].items() if v['kind']=='choice')
        split=next(k for k,v in good['nodes'].items() if v['kind']=='split')
        leaf=next(k for k,v in good['nodes'].items() if v['kind']=='leaf')
        mutations=[]
        def add(name,fn):
            bad=copy.deepcopy(good);fn(bad);mutations.append((name,bad))
        add('root-value',lambda d:d.__setitem__('value',0))
        add('root-reference',lambda d:d.__setitem__('root','absent'))
        add('root-bool',lambda d:d.__setitem__('value',True))
        add('node-value',lambda d:d['nodes'][choice].__setitem__('value',99))
        add('node-bool',lambda d:d['nodes'][choice].__setitem__('value',False))
        add('missing-action',lambda d:d['nodes'][choice]['children'].pop('1'))
        add('extra-action',lambda d:d['nodes'][choice]['children'].__setitem__('2',leaf))
        add('best-action',lambda d:d['nodes'][choice].__setitem__('best',2))
        add('best-bool',lambda d:d['nodes'][choice].__setitem__('best',False))
        add('missing-observation',lambda d:d['nodes'][split]['children'].pop(next(iter(d['nodes'][split]['children']))))
        add('extra-observation',lambda d:d['nodes'][split]['children'].__setitem__('invented',leaf))
        add('cycle',lambda d:d['nodes'][choice]['children'].__setitem__('0',choice))
        add('unreachable',lambda d:d['nodes'].__setitem__('unreachable',copy.deepcopy(d['nodes'][leaf])))
        add('leaf-value',lambda d:d['nodes'][leaf]['costs'].__setitem__(next(iter(d['nodes'][leaf]['costs'])),999))
        add('leaf-bool',lambda d:d['nodes'][leaf]['costs'].__setitem__(next(iter(d['nodes'][leaf]['costs'])),False))
        add('leaf-world',lambda d:d['nodes'][leaf]['costs'].__setitem__('invented',0))
        add('case-label',lambda d:d.__setitem__('case','wrong'))
        add('unknown-field',lambda d:d.__setitem__('unchecked',1))
        for name,bad in mutations:
            with self.subTest(mutation=name),self.assertRaises((ValueError,RuntimeError)):check_certificate(c,bad)
        # A valid node can be valid only for its reconstructed semantic state.
        bad=copy.deepcopy(good);bad['nodes'][choice]['children']['1']=bad['nodes'][choice]['children']['0']
        with self.assertRaises((ValueError,RuntimeError)):check_certificate(c,bad)

    def test_world_relabel_reorder_budget(self):
        c=chain(3,1);v=complete(c)
        for i,w in enumerate(c['worlds']):w['id']='world-'+str(100-i)
        c['worlds'].reverse();self.assertEqual(complete(c),v)
        cert=synthesize(c)
        for b in range(4):
            c['budget']=b
            self.assertEqual(check_certificate(c,cert)['feasible'],v<=b)
        # Deterministic cross-algorithm checks over every semantic mechanism case.
        # This remains one assurance group; it broadens the instances within it.
        for case in mechanism_cases():
            with self.subTest(case=case['id']):complete(case)


class SymbolicTests(unittest.TestCase):
    def test_bdd_truth_tables(self):
        for order in (['a','b','c'],['c','b','a']):
            b=BDD(order);a,z,c=(b.var(n) for n in ('a','b','c'))
            formulas=[0,1,a,z,c,b.op('xor',a,z),b.op('and',a,c),b.op('eq',z,c),b.op('lt',a,z)]
            valuations=list(itertools.product(range(2),repeat=3))
            for f in formulas:
                for g in formulas:
                    for op in ('xor','and','eq','lt'):
                        h=b.op(op,f,g)
                        for v in valuations:
                            fv,gv=b.evaluate(f,v),b.evaluate(g,v)
                            expected={'xor':fv^gv,'and':fv&gv,'eq':int(fv==gv),'lt':int(fv<gv)}[op]
                            self.assertEqual(b.evaluate(h,v),expected)
                for rank in range(3):
                    for value in (0,1):
                        co=b.restrict(f,rank,value)
                        for v in valuations:
                            substituted=list(v);substituted[rank]=value
                            self.assertEqual(b.evaluate(co,v),b.evaluate(f,substituted))
                substitutions={b.ranks['a']:b.op('xor',z,c),b.ranks['b']:a}
                h=b.compose(f,substitutions)
                for v in valuations:
                    changed=list(v)
                    for r,g in substitutions.items():changed[r]=b.evaluate(g,v)
                    self.assertEqual(b.evaluate(h,v),b.evaluate(f,changed))
                support={i for i in range(3) if any(b.evaluate(f,v)!=b.evaluate(f,v[:i]+(1-v[i],)+v[i+1:]) for v in valuations)}
                self.assertEqual(b.support(f),support)
                witness=b.satisfying_assignment(f)
                if witness is None:self.assertFalse(any(b.evaluate(f,v) for v in valuations))
                else:self.assertEqual(b.evaluate(f,witness),1)

    def test_rank_all_small_matrices(self):
        for d in range(1,4):
            for bits in itertools.product(range(2),repeat=d*d):
                rows=[[j for j in range(d) if bits[d*i+j]] for i in range(d)]
                images={tuple(sum(word[j] for j in row)%2 for row in rows) for word in itertools.product(range(2),repeat=d)}
                self.assertEqual(full_rank(rows,d),len(images)==2**d)

    def test_affine_premise_mutations(self):
        spec,premise=guarded_spec(3)
        bads=[]
        def add(name,fn):
            s,p=copy.deepcopy(spec),copy.deepcopy(premise);fn(s,p);bads.append((name,s,p))
        add('singular',lambda s,p:p['rows'].__setitem__(1,list(p['rows'][0])))
        add('wrong-offset',lambda s,p:p['offset'].__setitem__(1,0))
        add('duplicate-coordinate',lambda s,p:p['rows'].__setitem__(0,[0,0]))
        add('bad-output',lambda s,p:s['program'].__setitem__(-1,['emit',0]))
        add('nonzero-reference',lambda s,p:s['program'].__setitem__(-1,['emit',1]))
        add('branch',lambda s,p:s['program'].__setitem__(-2,['branch',0,len(s['program'])]))
        add('symbolic-address',lambda s,p:s['program'].__setitem__(0,['load',0,'r0']))
        add('read-count',lambda s,p:s['world_family']['faults'].pop())
        add('write-fault',lambda s,p:s['world_family']['faults'].__setitem__(0,1))
        add('palette',lambda s,p:s.__setitem__('read_actions',[0]))
        add('nonboolean',lambda s,p:s.__setitem__('bits',2))
        add('positive-budget',lambda s,p:s.__setitem__('budget',1))
        add('extra-worlds',lambda s,p:s.__setitem__('worlds',[]))
        add('unknown-premise',lambda s,p:p.__setitem__('unchecked',1))
        for name,s,p in bads:
            with self.subTest(mutation=name),self.assertRaises(ValueError):classify_contract(s,p)
        s,p=observed_guarded_spec(3,False,((0,0),))
        with self.assertRaises(ValueError):check_obstruction(s,p)
        out=classify_contract(s,p);self.assertEqual(out['classification'],'repairable')
        case=expand_guarded(s);policy=out['policy']
        self.assertEqual(len(replay_two_tail(case,policy)),len(case['worlds']))
        bad=copy.deepcopy(policy);bad['pc']+=1
        with self.assertRaises(ValueError):replay_two_tail(case,bad)
        bad=copy.deepcopy(policy);bad['first_word'][0]^=1
        with self.assertRaises(AssertionError):replay_two_tail(case,bad)


class DiagnosticTests(unittest.TestCase):
    def test_one_hot_and_hindsight(self):
        for d in range(2,6):
            words=[tuple(int(i==j) for j in range(d)) for i in range(d)]
            c=chain(d,words=words)
            self.assertEqual(max(sum(w) for w in words),1)
            self.assertEqual(sum(max(w[j] for w in words) for j in range(d)),d)
            self.assertEqual(complete(c),1)
        c=chain(2,words=[(0,0),(1,1)])
        self.assertEqual(complete(c),1)
        self.assertEqual(exact_oracle(c)['hindsight'],0)
        self.assertEqual(max(sum(w) for w in ((0,0),(1,1))),2) # zero-replacement baseline

    def test_local_reset_is_not_global_budget(self):
        c=chain(2,words=[(1,1)],budget=1)
        w=c['worlds'][0]
        reference=run(c,w,start(c,w),ideal=True).output
        actual=(0,0)
        self.assertEqual([int(a!=b) for a,b in zip(actual,reference)],[1,1])
        self.assertEqual(distance(c,actual,reference),2)
        self.assertGreater(distance(c,actual,reference),c['budget'])

    def test_minimal_is_not_minimum(self):
        words=[(0,0,0),(0,1,1),(1,0,1),(1,1,0),(1,1,1)]
        c=chain(3,words=words,budget=1)
        forward=extract_core(c,1);reverse=extract_core(c,1,reverse=True)
        self.assertEqual(set(forward),{'000','111'})
        self.assertEqual(set(reverse),{'000','011','101','110'})
        minima=[]
        for k in range(1,len(words)+1):
            for subset in itertools.combinations(words,k):
                if synthesize(chain(3,words=subset,budget=1))['value']>1:minima.append(subset)
            if minima:break
        self.assertEqual(k,2)
        for core in (forward,reverse):
            part=copy.deepcopy(c);part['worlds']=[w for w in c['worlds'] if w['id'] in core]
            self.assertGreater(complete(part),1)
            for omit in core:
                sub=copy.deepcopy(part);sub['worlds']=[w for w in part['worlds'] if w['id']!=omit]
                self.assertLessEqual(complete(sub),1)

    def test_information_and_domain_monotonicity(self):
        words=list(itertools.product(range(2),repeat=3));previous=3
        for k in range(4):
            v=complete(chain(3,k));self.assertLessEqual(v,previous);previous=v
        full=chain(3);full_value=complete(full)
        for omit in words:
            c=chain(3,words=[w for w in words if w!=omit]);self.assertLessEqual(complete(c),full_value)
        c=chain(2,words=[(0,0),(1,1)]);c['read_actions']=[0]
        restricted=complete(c);del c['read_actions']
        self.assertLessEqual(complete(c),restricted)


if __name__=='__main__':unittest.main()
