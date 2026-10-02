"""Discriminating intake pilot: exact oracle, uniformity negative control and mutation."""
import json,time,resource
from pathlib import Path
from copy import deepcopy
from .cases import chain
from .solve import synthesize
from .check import check_certificate,policy_replay
from .oracle import exact_oracle


def main():
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    start=time.process_time(); wall=time.perf_counter()
    results=[]
    for d,k in [(1,0),(3,1),(4,0)]:
        c=chain(d,k,budget=0)
        cert=synthesize(c); checked=check_certificate(c,cert); oracle=exact_oracle(c); rows=policy_replay(c,cert)
        assert checked['value']==oracle['value']==d-k
        bad=deepcopy(cert); bad['value']=0
        try: check_certificate(c,bad)
        except ValueError: rejected=True
        else: rejected=False
        assert rejected and oracle['hindsight']==0
        results.append({'case':c['id'],'worlds':len(c['worlds']),'instructions':len(c['program']), 'word_bits':c['bits'],
                        'uniform_optimum':cert['value'],'hindsight_optimum':oracle['hindsight'],'certificate_nodes':len(cert['nodes']),
                        'oracle_paths':oracle['path_count'],'oracle_combinations':oracle['combinations'],'forged_zero_rejected':rejected})
    result={'cases':results,'cpu_seconds':time.process_time()-start,'wall_seconds':time.perf_counter()-wall,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    Path('results/pilot.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
