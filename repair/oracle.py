"""Exhaustive compatible-path oracle, NOT information-set dynamic programming.

The oracle and checker share the audit interpreter. Paths from different worlds
must prescribe identical actions at identical complete observation/action
histories. A finite compatible path family is exactly an executable policy.
"""
from __future__ import annotations
from .model import validate
from .check import start, run, observation, options, distance
from .errors import ResourceExhausted


def paths(c,w,path_cap=100000):
    reference = run(c,w,start(c,w),ideal=True).output
    answer = []
    def walk(m,history,rules):
        m = run(c,w,m); obs = observation(c,m); key = history + (obs,)
        acts = options(c,m)
        if not acts:
            answer.append((distance(c,m.output,reference),dict(rules),m.output))
            if len(answer) > path_cap: raise ResourceExhausted('oracle path cap')
        else:
            for a in acts:
                rules[key] = a
                walk(run(c,w,m,choice=a),key+(str(a),),rules)
                del rules[key]
    walk(start(c,w),(),{})
    return answer


def exact_oracle(c,combination_cap=2000000):
    validate(c)
    catalog = [paths(c,w) for w in c['worlds']]
    hindsight = max(min(p[0] for p in ps) for ps in catalog)
    ordered = sorted(catalog,key=len)
    best = float('inf'); tests = 0; policy = {}; winner = None

    # The search is depth-first, as before, but the frames are explicit.  The
    # declared schema permits 1,024 worlds, which can exceed CPython's default
    # call-stack limit even when every world contributes exactly one path.
    # Each frame owns the policy keys introduced by its parent branch and
    # removes them when that simulated recursive call returns.
    stack = [{
        'index': 0,
        'worst': 0,
        'entered': False,
        'choices': (),
        'next': 0,
        'added': (),
    }]
    while stack:
        frame = stack[-1]
        if not frame['entered']:
            frame['entered'] = True
            if frame['worst'] >= best:
                for key in frame['added']: del policy[key]
                stack.pop()
                continue
            if frame['index'] == len(ordered):
                best = frame['worst']; winner = dict(policy)
                for key in frame['added']: del policy[key]
                stack.pop()
                continue
            frame['choices'] = sorted(ordered[frame['index']],key=lambda x:x[0])

        if frame['next'] == len(frame['choices']):
            for key in frame['added']: del policy[key]
            stack.pop()
            continue

        cost,rules,_ = frame['choices'][frame['next']]
        frame['next'] += 1
        tests += 1
        if tests > combination_cap: raise ResourceExhausted('oracle combination cap')
        next_worst = max(frame['worst'],cost)
        if next_worst >= best or any(k in policy and policy[k] != a for k,a in rules.items()):
            continue
        added = tuple(k for k in rules if k not in policy)
        policy.update(rules)
        stack.append({
            'index': frame['index']+1,
            'worst': next_worst,
            'entered': False,
            'choices': (),
            'next': 0,
            'added': added,
        })

    if best == float('inf'): raise RuntimeError('no compatible policy: implementation fault')
    return {'value':int(best),'hindsight':hindsight,'path_count':sum(map(len,catalog)),'combinations':tests}
