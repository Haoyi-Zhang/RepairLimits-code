"""Measured exact pilot for the observation-timing dichotomy."""
import copy,json,resource,time
from pathlib import Path
from .cases import observed_guarded_spec,expand_guarded
from .solve import synthesize
from .check import check_certificate,policy_replay,run,start,distance
from .oracle import exact_oracle
from .symbolic import classify_contract


def replay_two_tail(c,policy):
    rows=[]
    for w in c['worlds']:
        m=run(c,w,start(c,w)); branch=None
        ideal=run(c,w,start(c,w),ideal=True).output
        actions=[]
        for i in range(len(policy['first_word'])):
            if i==policy['decision']:
                if m.counter!=policy['pc']: raise ValueError('policy location mismatch')
                source=m.values if policy['component_kind']=='register' else m.output
                bit=source[policy['component_index']]
                branch='second_word' if bit==policy['first_diagonal_bit'] else 'first_word'
            action=policy[branch or 'first_word'][i]
            actions.append(action)
            m=run(c,w,m,choice=action)
        cost=distance(c,m.output,ideal)
        if cost!=0: raise AssertionError('two-tail policy failed concrete replay')
        rows.append({'world':w['id'],'actions':actions,'reference':list(ideal),
                     'actual':list(m.output),'loss':cost})
    return rows


def main():
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    cpu,wall=time.process_time(),time.monotonic()
    results=[]
    patterns=[(2,False,()),(3,False,((0,0),)),(3,False,((2,0),)),
              (3,False,((2,2),)),(3,True,((2,0),)),(3,True,((1,2),)),
              (4,False,((1,0),(3,1))), (4,True,((2,3),))]
    for d,mixed,leaks in patterns:
        spec,premise=observed_guarded_spec(d,mixed,leaks)
        case=expand_guarded(spec)
        result=classify_contract(spec,premise)
        cert=synthesize(case)
        checked=check_certificate(case,cert)
        oracle=exact_oracle(case)
        replay=policy_replay(case,cert)
        assert result['uniform_optimum']==checked['value']==oracle['value']
        assert oracle['hindsight']==0
        if result['classification']=='repairable':
            positive=replay_two_tail(case,result['policy'])
        else: positive=[]
        results.append({'case':case['id'],**result,'exact_nodes':checked['nodes'],
            'oracle_paths':oracle['path_count'],'oracle_combinations':oracle['combinations'],
            'policy_replay_worlds':len(replay),'two_tail_replay_worlds':len(positive)})
    out={'cases':results,'cpu_seconds':time.process_time()-cpu,
         'wall_seconds':time.monotonic()-wall,
         'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    Path('results/causality-pilot.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__': main()
