"""Exact no-certificate control on the same finite full-history contract.

Uses the audit VM, not the synthesis VM or a supplied failure relation. This is
ordinary information-set minimax, not a new algorithm. It retains optimal
suffix actions, but does not export an all-alternatives value certificate.
"""
from dataclasses import dataclass
from .model import validate, integer
from .check import start, run, observation, options, distance
from .errors import ResourceExhausted


@dataclass
class ValueSolution:
    value: int
    states: int
    root: int
    policy: dict


def solve_value(case, state_limit=200000):
    validate(case)
    integer(state_limit, 1, 200000, 'value-only state cap')
    worlds = {w['id']: w for w in case['worlds']}
    references = {k: run(case, w, start(case, w), ideal=True).output
                  for k, w in worlds.items()}
    cache, values, policy = {}, {}, {}

    def visit(entries):
        states = tuple((k, run(case, worlds[k], m)) for k, m in entries)
        if states in cache:
            return cache[states]
        if len(cache) >= state_limit:
            raise ResourceExhausted('value-only state budget exceeded')
        key = len(cache)
        cache[states] = key
        groups = {}
        for k, m in states:
            groups.setdefault(observation(case, m), []).append((k, m))
        if len(groups) > 1:
            successors = {obs: visit(tuple(group))
                          for obs, group in sorted(groups.items())}
            values[key] = max(values[j] for j in successors.values())
            policy[key] = ('split', successors)
        else:
            actions = options(case, states[0][1])
            if not actions:
                values[key] = max(distance(case, m.output, references[k])
                                  for k, m in states)
                policy[key] = ('leaf', None)
            else:
                alternatives = {}
                for action in actions:
                    alternatives[action] = visit(tuple(
                        (k, run(case, worlds[k], m, choice=action))
                        for k, m in states))
                best = min(actions, key=lambda a: (values[alternatives[a]], a))
                values[key] = values[alternatives[best]]
                policy[key] = ('choice', (best, alternatives[best]))
        return key

    root = visit(tuple(sorted((k, start(case, w)) for k, w in worlds.items())))
    return ValueSolution(values[root], len(cache), root, policy)


def replay_value_policy(case, solution):
    """Policy dispatch uses observed histories/selected edges, never world IDs."""
    rows = []
    for world in case['worlds']:
        reference = run(case, world, start(case, world), ideal=True).output
        machine = run(case, world, start(case, world))
        key = solution.root
        for _ in range(2 * len(case['program']) + 3):
            kind, payload = solution.policy[key]
            if kind == 'leaf':
                if options(case, machine):
                    raise ValueError('unfinished value-only policy')
                break
            if kind == 'split':
                key = payload[observation(case, machine)]
            elif kind == 'choice':
                action, key = payload
                if action not in options(case, machine):
                    raise ValueError('illegal value-only policy action')
                machine = run(case, world, machine, choice=action)
            else:
                raise ValueError('value-only policy node')
        else:
            raise ValueError('value-only policy depth')
        rows.append({'world': world['id'], 'reference': list(reference),
                     'actual': list(machine.output),
                     'loss': distance(case, machine.output, reference)})
    if max(row['loss'] for row in rows) != solution.value:
        raise ValueError('value-only policy replay value')
    return rows
