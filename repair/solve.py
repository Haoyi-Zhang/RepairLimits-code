"""Exact finite information-set minimax with a complete value certificate."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from .model import State, validate, integer, initial, advance, event, observe, actions, act, loss
from .errors import ResourceExhausted


def synthesize(c: dict, node_limit: int = 200000) -> dict:
    validate(c)
    integer(node_limit,1,200000,'synthesis node cap')
    worlds = {w['id']: w for w in c['worlds']}
    refs = {k:advance(c,w,initial(c,w),True).trace for k,w in worlds.items()}
    nodes, cache = {}, {}
    def visit(entries: tuple[tuple[str,State],...]) -> str:
        normalized = tuple((k,advance(c,worlds[k],s)) for k,s in entries)
        if normalized in cache: return cache[normalized]
        if len(nodes) >= node_limit: raise ResourceExhausted('certificate node limit')
        nid = str(len(nodes)); cache[normalized] = nid; nodes[nid] = {}
        groups = defaultdict(list)
        for k,s in normalized: groups[observe(c,s)].append((k,s))
        if len(groups) > 1:
            children = {o:visit(tuple(v)) for o,v in sorted(groups.items())}
            node = {'kind':'split','value':max(nodes[t]['value'] for t in children.values()),'children':children}
        else:
            sample = normalized[0][1]
            if event(c,sample) == 'halt':
                costs = {k:loss(c,s.trace,refs[k]) for k,s in normalized}
                node = {'kind':'leaf','value':max(costs.values()),'costs':costs}
            else:
                children = {str(a):visit(tuple((k,act(c,s,a)) for k,s in normalized)) for a in actions(c,sample)}
                best = min(children, key=lambda a:(nodes[children[a]]['value'],int(a)))
                node = {'kind':'choice','value':nodes[children[best]]['value'],'best':int(best),'children':children}
        nodes[nid] = node
        return nid
    root = visit(tuple(sorted((k,initial(c,w)) for k,w in worlds.items())))
    return {'case':c['id'],'root':root,'value':nodes[root]['value'],'nodes':nodes}


def extract_core(c: dict, budget: int, reverse: bool = False) -> list[str]:
    """Deletion-minimal, NOT minimum-cardinality. Full-world optimum must exceed B."""
    integer(budget,0,10**9,'core budget')
    if synthesize(c)['value'] <= budget: raise ValueError('case is feasible')
    current = deepcopy(c)
    for wid in sorted((w['id'] for w in c['worlds']), reverse=reverse):
        trial = deepcopy(current)
        trial['worlds'] = [w for w in trial['worlds'] if w['id'] != wid]
        if trial['worlds'] and synthesize(trial)['value'] > budget: current = trial
    return [w['id'] for w in current['worlds']]
