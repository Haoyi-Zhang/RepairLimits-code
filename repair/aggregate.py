"""Rebuild deterministic tables from all retained campaign chunks; fail on missing evidence."""
from __future__ import annotations
import csv,json
from collections import Counter
from pathlib import Path
from .campaign import write_json

CHUNKS={'correlations':range(8),'mechanisms':range(1),'chains':range(1,8),
        'guarded':range(12),'timing':range(8),'abstract':range(24),'symbolic':range(40)}

def build(root=Path('.')):
    root=Path(root);chunks=[];explicit=[];symbolic=[];abstract=[];timing=[];cohorts=[]
    for cohort,indices in CHUNKS.items():
        group=[]
        for index in indices:
            p=root/'results/chunks'/f'{cohort}-{index}.json'
            d=json.loads(p.read_text())
            if d['cohort']!=cohort or d['chunk']!=index or d['workers']!=1: raise ValueError('chunk identity')
            group.append(d);chunks.append(d)
            if cohort=='abstract': abstract.append(d['results'])
            elif cohort=='symbolic': symbolic.extend(d['results'])
            else:
                for r in d['results']:
                    if r['oracle'] is not None and r['value']!=r['oracle']['value']: raise ValueError('oracle mismatch')
                    c=json.loads((root/'inputs'/(r['case']+'.json')).read_text())
                    cert=json.loads((root/'results/certificates'/(r['case']+'.json')).read_text())
                    replay=json.loads((root/'results/replays'/(r['case']+'.json')).read_text())
                    if cert['value']!=r['value'] or max(x['loss'] for x in replay)!=r['value']: raise ValueError('stored evidence mismatch')
                    if len(c['worlds'])!=r['worlds'] or len(c['program'])!=r['instructions']: raise ValueError('input dimensions')
                    explicit.append({'cohort':cohort,**r})
                    if cohort=='timing': timing.append(r)
        count=sum(len(d['results']['rows']) if cohort=='abstract' else len(d['results']) for d in group)
        cohorts.append({'cohort':cohort,'instances':count,'chunks':len(group),'cpu_seconds':sum(d['cpu_seconds'] for d in group),'peak_rss_kib':max(d['peak_rss_kib'] for d in group)})
    if len({r['case'] for r in explicit})!=len(explicit): raise ValueError('duplicate explicit identity')
    summary={'chunks':len(chunks),'explicit_instances':len(explicit),'oracle_checked_instances':sum(r['oracle'] is not None for r in explicit),
             'abstract_games':sum(d['games'] for d in abstract),'abstract_repairable':sum(d['repairable'] for d in abstract),
             'abstract_obstruction':sum(d['obstruction'] for d in abstract),'timing_repairable':sum(r['value']==0 for r in timing),
             'timing_obstruction':sum(r['value']==1 for r in timing),'symbolic_checks':len(symbolic),
             'symbolic_outcomes':dict(Counter(r['status'] for r in symbolic)),
             'guarded_deletion_checks':sum(len(r.get('all_world_deletions',[])) for r in explicit),
             'zero_baseline_strictly_worse':sum(r['zero_value']>r['value'] for r in explicit),
             'cpu_seconds_completed_chunks':sum(d['cpu_seconds'] for d in chunks),'peak_rss_kib_completed_chunks':max(d['peak_rss_kib'] for d in chunks)}
    write_json(root/'results/summary.json',summary)
    out=root/'results/tables';out.mkdir(parents=True,exist_ok=True)
    def table(name,fields,rows):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    table('cohorts.csv',list(cohorts[0]),cohorts)
    table('explicit.csv',['cohort','case','worlds','instructions','bits','value','zero_value','certificate_nodes'],explicit)
    table('symbolic.csv',['case','dimensions','variable_order','status','allocated_bdd_nodes','node_cap','instructions','worlds','minimum_core'],symbolic)
    table('timing.csv',['case','decision','coordinate','value','worlds'],timing)
    table('mechanisms.csv',['case','bits','worlds','instructions','value','zero_value'],[r for r in explicit if r['cohort']=='mechanisms'])
    table('guarded.csv',['case','worlds','instructions','value','certificate_nodes'],[r for r in explicit if r['cohort']=='guarded'])
    return summary

if __name__=='__main__': print(json.dumps(build(),sort_keys=True))
