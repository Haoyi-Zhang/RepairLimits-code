"""Deterministic, bounded campaign. Each command is one resumable chunk.

No external programs, datasets, model services, or network access are used.
"""
from __future__ import annotations
import argparse,copy,itertools,json,os,resource,time
from pathlib import Path
from .cases import (chain,correlation_cases,mechanism_cases,guarded_spec,
                    observed_guarded_spec,expand_guarded)
from .solve import synthesize,extract_core
from .check import check_certificate,policy_replay,start,run,distance
from .oracle import exact_oracle
from .symbolic import classify_contract
from .causality_pilot import replay_two_tail


def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n')
    os.replace(tmp,path)


def evaluate(case,oracle=True):
    begin=time.process_time()
    cert=synthesize(case)
    audit=check_certificate(case,cert)
    replay=policy_replay(case,cert)
    other=exact_oracle(case) if oracle else None
    if other is not None and other['value']!=audit['value']:
        raise AssertionError('path-oracle disagreement')
    write_json(Path('inputs')/(case['id']+'.json'),case)
    write_json(Path('results/certificates')/(case['id']+'.json'),cert)
    write_json(Path('results/replays')/(case['id']+'.json'),replay)
    zero=[]
    for world in case['worlds']:
        m=run(case,world,start(case,world))
        while m.counter<len(case['program']) and case['program'][m.counter][0]!='halt':
            action=-1 if case['program'][m.counter][0]=='store' else min(case.get('read_actions',[0]))
            m=run(case,world,m,choice=action)
        reference=run(case,world,start(case,world),ideal=True).output
        zero.append(distance(case,m.output,reference))
    return {'case':case['id'],'worlds':len(case['worlds']),
            'instructions':len(case['program']),'bits':case['bits'],
            'value':audit['value'],'certificate_nodes':audit['nodes'],
            'zero_value':max(zero),'oracle':other,
            'cpu_seconds':time.process_time()-begin}


def run_correlations(index):
    cases=list(correlation_cases())[index*32:(index+1)*32]
    if not cases: raise ValueError('empty correlation chunk')
    return [evaluate(c) for c in cases]


def run_mechanisms(_): return [evaluate(c) for c in mechanism_cases()]


def run_chains(d):
    if not 1<=d<=7: raise ValueError('chain dimension')
    rows=[]
    for k in range(d+1):
        c=chain(d,k,budget=d-k)
        row=evaluate(c,oracle=d<=4)
        if row['value']!=d-k: raise AssertionError('copy-chain identity failed')
        rows.append(row)
    return rows


def run_guarded(index):
    if not 0<=index<12: raise ValueError('guarded chunk')
    d=index//2+1;mixed=bool(index%2)
    spec,premise=guarded_spec(d,mixed)
    c=expand_guarded(spec)
    row=evaluate(c,oracle=d<=4)
    symbolic=classify_contract(spec,premise)
    if row['value']!=symbolic['uniform_optimum'] or symbolic['minimum_core']!=2**d:
        raise AssertionError('affine obstruction disagreement')
    deleted=[]
    for world in c['worlds']:
        part=copy.deepcopy(c)
        part['worlds']=[w for w in part['worlds'] if w['id']!=world['id']]
        cert=synthesize(part);checked=check_certificate(part,cert)
        policy_replay(part,cert)
        if checked['value']!=0: raise AssertionError('deletion does not restore feasibility')
        deleted.append({'removed':world['id'],'value':checked['value']})
    row['all_world_deletions']=deleted;row['symbolic']=symbolic
    write_json(Path('inputs/implicit')/(spec['id']+'.json'),{'specification':spec,'premise':premise})
    return [row]


def run_timing(index):
    if not 0<=index<8: raise ValueError('timing chunk')
    d=index//2+1;mixed=bool(index%2);rows=[]
    for i in range(d):
        for j in range(d):
            spec,premise=observed_guarded_spec(d,mixed,((i,j),))
            case=expand_guarded(spec)
            row=evaluate(case,oracle=True)
            symbolic=classify_contract(spec,premise)
            if symbolic['uniform_optimum']!=row['value']:
                raise AssertionError('timing classification disagreement')
            row['decision']=i;row['coordinate']=j;row['symbolic']=symbolic
            if symbolic['classification']=='repairable':
                replay=replay_two_tail(case,symbolic['policy'])
                write_json(Path('results/two-tail')/(case['id']+'.json'),replay)
            write_json(Path('inputs/implicit')/(spec['id']+'.json'),{'specification':spec,'premise':premise})
            rows.append(row)
    return rows


def game_value(g,o0,o1,worlds=(0,1,2,3)):
    """Direct nested enumeration; no repair interpreter, BDD or certificate code."""
    outer=[]
    for first_observation in (0,1):
        group=[x for x in worlds if o0[x]==first_observation]
        if not group: continue
        action_values=[]
        for a in (0,1):
            subvalues=[]
            for second_observation in (0,1):
                sub=[x for x in group if o1[a][x]==second_observation]
                if sub:
                    subvalues.append(min(max(int(x==g[2*a+b]) for x in sub) for b in (0,1)))
            action_values.append(max(subvalues))
        outer.append(min(action_values))
    return max(outer)


def run_abstract(index):
    if not 0<=index<24: raise ValueError('abstract permutation chunk')
    g=list(itertools.permutations(range(4)))[index]
    rows=[];positive=negative=0
    for mask0 in range(16):
        o0=[(mask0>>x)&1 for x in range(4)]
        for mask1 in range(256):
            o1=[[(mask1>>(4*a+x))&1 for x in range(4)] for a in (0,1)]
            ds=[[o0[g[r]] for r in range(4)],
                [o1[r//2][g[r]] for r in range(4)]]
            witness=None
            for i in (0,1):
                for r in range(4):
                    for s in range(r+1,4):
                        if (i==0 or r//2==s//2) and ds[i][r]!=ds[i][s]:
                            witness=(i,r,s);break
                    if witness is not None:break
                if witness is not None:break
            expected=int(witness is None)
            actual=game_value(g,o0,o1)
            if expected!=actual: raise AssertionError('abstract criterion refuted')
            if witness is None:
                negative+=1
                for x in range(4):
                    if game_value(g,o0,o1,tuple(y for y in range(4) if y!=x))!=0:
                        raise AssertionError('abstract core deletion failed')
            else:
                positive+=1;i,r,s=witness
                for x in range(4):
                    obs=o0[x] if i==0 else o1[r//2][x]
                    chosen=s if obs==ds[i][r] else r
                    if x==g[chosen]: raise AssertionError('abstract two-tail policy failed')
            # Retain exhaustive raw outcomes, not just an aggregate count.
            rows.append([mask0,mask1,actual,*(witness if witness else (-1,-1,-1))])
    return {'bijection':list(g),'columns':['first_mask','second_mask','value','decision','word0','word1'],
            'rows':rows,'repairable':positive,'obstruction':negative,'games':len(rows)}


def run_symbolic(index):
    if not 0<=index<40: raise ValueError('symbolic chunk')
    d=index//2+1;mixed=bool(index%2)
    spec,premise=guarded_spec(d,mixed)
    write_json(Path('inputs/implicit')/(spec['id']+'.json'),{'specification':spec,'premise':premise})
    rows=[]
    for order in ('interleaved','actions-first'):
        begin=time.process_time()
        try:
            classified=classify_contract(spec,premise,order=order,node_limit=200000)
            if classified['uniform_optimum']!=1: raise AssertionError('blind classification failed')
            row={'status':'checked',**classified}
        except RuntimeError as error:
            if str(error)!='BDD node budget exceeded': raise
            row={'status':'unknown-node-cap','dimensions':d,'variable_order':order,'node_cap':200000}
        rows.append({'case':spec['id'],**row,'cpu_seconds':time.process_time()-begin})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohort',choices=['correlations','mechanisms','chains','guarded','timing','abstract','symbolic'])
    parser.add_argument('index',type=int)
    args=parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    cpu,wall=time.process_time(),time.monotonic()
    result=globals()['run_'+args.cohort](args.index)
    output={'cohort':args.cohort,'chunk':args.index,'results':result,
            'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    target=Path('results/chunks')/(args.cohort+'-'+str(args.index)+'.json')
    write_json(target,output)
    print(json.dumps({'cohort':args.cohort,'chunk':args.index,
        'cpu_seconds':output['cpu_seconds'],'peak_rss_kib':output['peak_rss_kib']}))


if __name__=='__main__':main()
