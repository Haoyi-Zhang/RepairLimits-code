"""Bounded pre-lock discriminating pilot for the revised semantic boundary."""
import copy,json,resource,time
from pathlib import Path
from .cases import guarded_spec,expand_guarded
from .solve import synthesize
from .check import check_certificate,policy_replay
from .oracle import exact_oracle
from .symbolic import check_obstruction


def main():
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    cpu,wall = time.process_time(),time.monotonic()
    rows = []
    for d,mixed in [(2,False),(3,True),(4,False)]:
        spec,obstruction = guarded_spec(d,mixed)
        c = expand_guarded(spec)
        cert = synthesize(c)
        general = check_certificate(c,cert)
        oracle = exact_oracle(c)
        symbolic = check_obstruction(spec,obstruction)
        assert general['value']==oracle['value']==symbolic['uniform_optimum']==1
        assert oracle['hindsight']==0
        policy_replay(c,cert)
        removal = []
        for world in c['worlds']:
            part = copy.deepcopy(c)
            part['worlds'] = [w for w in part['worlds'] if w['id']!=world['id']]
            pc = synthesize(part)
            check_certificate(part,pc)
            assert pc['value']==0
            removal.append(world['id'])
        bad = copy.deepcopy(spec)
        # Safe hidden load before the first trap discloses a hidden bit.
        bad['program'].insert(0,['load',1,0])
        bad['world_family']['faults'] = [i+1 for i in bad['world_family']['faults']]
        rejected = False
        try: check_obstruction(bad,obstruction)
        except ValueError: rejected=True
        assert rejected
        rows.append({'case':c['id'],**symbolic,'certificate_nodes':general['nodes'],
                     'oracle_paths':oracle['path_count'],'oracle_combinations':oracle['combinations'],
                     'deletion_checks':len(removal),'leaked_observation_rejected':rejected})
    data = {'cases':rows,'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    Path('results').mkdir(exist_ok=True)
    Path('results/boundary-pilot.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))


if __name__=='__main__': main()
