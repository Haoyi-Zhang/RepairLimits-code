"""Certificate checker with a separately written interpreter and distance evaluator.

Only the declarative input validator is shared with synthesis. No synthesis
transition, observation, objective or search function is imported. This is
implementation diversity, not an independent author or a mechanized proof.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from .model import validate,integer
from .errors import ResourceExhausted


def strict_json(text: str) -> dict:
    def pairs(items):
        d = {}
        for k,v in items:
            if k in d: raise ValueError('duplicate JSON key')
            d[k] = v
        return d
    def bad(_): raise ValueError('nonfinite JSON number')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


@dataclass(frozen=True)
class Machine:
    counter: int
    values: tuple[int,...]
    cells: tuple[int,...]
    output: tuple[int,...] = ()


def start(c,w): return Machine(0,tuple(0 for _ in range(c['registers'])),tuple(w['memory']))


def run(c,w,m,choice=None,ideal=False):
    """Resume a trap (when choice is supplied), then stop at next trap or halt."""
    ip, r, h, out = m.counter, list(m.values), list(m.cells), list(m.output)
    program = c['program']; modulus = 2**c['bits']
    def val(x): return x if type(x) is int else r[int(x[1:])]
    if choice is not None:
        instruction = program[ip]
        if instruction[0] == 'load': r[instruction[1]] = choice
        elif instruction[0] != 'store' or choice != -1: raise ValueError('bad resume')
        ip += 1
    while ip < len(program):
        instruction = program[ip]; op = instruction[0]; jump = ip+1
        if op == 'halt': break
        if op == 'load' or op == 'store':
            at = val(instruction[2] if op == 'load' else instruction[1])
            trapped = at < 0 or at >= len(h) or (not ideal and ip in w['faults'])
            if trapped:
                if ideal: raise ValueError('invalid reference')
                break
            if op == 'load': r[instruction[1]] = h[at]
            else: h[at] = val(instruction[2]) % modulus
        elif op == 'const' or op == 'copy': r[instruction[1]] = val(instruction[2]) % modulus
        elif op in ('xor','add','eq','lt'):
            left,right = val(instruction[2]),val(instruction[3])
            if op == 'xor': result = left ^ right
            elif op == 'add': result = left + right
            elif op == 'eq': result = 1 if left == right else 0
            else: result = 1 if left < right else 0
            r[instruction[1]] = result % modulus
        elif op == 'emit': out.append(val(instruction[1]) % modulus)
        elif op == 'branch':
            if val(instruction[1]) != 0: jump = instruction[2]
        else: raise ValueError('unknown instruction')
        ip = jump
    return Machine(ip,tuple(r),tuple(h),tuple(out))


def observation(c,m):
    tag = 'halt' if m.counter == len(c['program']) else c['program'][m.counter][0]
    return json.dumps([tag,m.counter,list(m.values),list(m.output)],separators=(',',':'))


def options(c,m):
    if m.counter == len(c['program']): return []
    op = c['program'][m.counter][0]
    if op == 'halt': return []
    if op == 'store': return [-1]
    if op == 'load': return sorted(c.get('read_actions',list(range(2**c['bits']))))
    raise ValueError('not a boundary')


def distance(c,a,b):
    n = max(len(a),len(b)); value = 0
    for i in range(n):
        u = a[i] if i < len(a) else None
        v = b[i] if i < len(b) else None
        if u is None or v is None:
            d = c['bits'] if c['metric'] == 'hamming' else ((2**c['bits']-1) if c['metric'] == 'l1' else 1)
        elif c['metric'] == 'hamming':
            d = sum(((u >> j)&1) != ((v >> j)&1) for j in range(c['bits']))
        elif c['metric'] == 'word': d = int(u != v)
        else: d = max(u,v)-min(u,v)
        value += d*c['weights'][i]
    return value


def check_certificate(c: dict, cert: dict, max_nodes=200000) -> dict:
    validate(c)
    integer(max_nodes,1,200000,'checker node cap')
    if type(cert) is not dict or set(cert) != {'case','root','value','nodes'} or cert['case'] != c['id']:
        raise ValueError('certificate header')
    nodes = cert['nodes']
    if type(nodes) is not dict or not 1 <= len(nodes) <= max_nodes: raise ValueError('node count')
    if type(cert['value']) is not int or cert['value'] < 0: raise ValueError('root value')
    ws = {w['id']:w for w in c['worlds']}
    ideal = {k:run(c,w,start(c,w),ideal=True).output for k,w in ws.items()}
    checked, active, visited = {}, set(), set()
    def visit(nid, states, depth=0):
        if type(nid) is not str or nid not in nodes: raise ValueError('node reference')
        if depth > 2*len(c['program'])+2: raise ValueError('depth')
        states = tuple((k,run(c,ws[k],m)) for k,m in states)
        key = (nid,states)
        if key in checked: return checked[key]
        if len(checked)+len(active) >= max_nodes: raise ResourceExhausted('semantic-check budget exceeded')
        if nid in active: raise ValueError('cycle')
        active.add(nid); visited.add(nid)
        node = nodes[nid]
        if type(node) is not dict or type(node.get('value')) is not int or node['value'] < 0:
            raise ValueError('node value')
        groups = {}
        for k,m in states: groups.setdefault(observation(c,m),[]).append((k,m))
        if len(groups) != 1:
            if set(node) != {'kind','value','children'} or node['kind'] != 'split' or type(node['children']) is not dict or set(node['children']) != set(groups):
                raise ValueError('observation coverage')
            actual = max(visit(node['children'][o],tuple(g),depth+1) for o,g in groups.items())
        else:
            acts = options(c,states[0][1])
            if not acts:
                costs = {k:distance(c,m.output,ideal[k]) for k,m in states}
                if set(node) != {'kind','value','costs'} or node['kind'] != 'leaf' or type(node['costs']) is not dict:
                    raise ValueError('leaf fields')
                if any(type(v) is not int for v in node['costs'].values()) or node['costs'] != costs:
                    raise ValueError('terminal costs')
                actual = max(costs.values())
            else:
                if set(node) != {'kind','value','best','children'} or node['kind'] != 'choice' or type(node['children']) is not dict or set(node['children']) != {str(a) for a in acts}:
                    raise ValueError('action coverage')
                if type(node['best']) is not int or node['best'] not in acts: raise ValueError('best action')
                values = {a:visit(node['children'][str(a)],tuple((k,run(c,ws[k],m,choice=a)) for k,m in states),depth+1) for a in acts}
                actual = min(values.values())
                if values[node['best']] != actual: raise ValueError('nonoptimal best action')
        if node['value'] != actual: raise ValueError('wrong node value')
        active.remove(nid); checked[key] = actual
        return actual
    v = visit(cert['root'],tuple(sorted((k,start(c,w)) for k,w in ws.items())))
    if v != cert['value'] or visited != set(nodes): raise ValueError('root value or unreachable nodes')
    return {'value':v,'nodes':len(visited),'feasible':v <= c['budget']}


def policy_replay(c,cert):
    """Replay the selected policy separately for each world, using no world ID in dispatch."""
    rows = []
    for w in c['worlds']:
        ideal = run(c,w,start(c,w),ideal=True).output
        m = run(c,w,start(c,w)); nid = cert['root']; count = 0
        while True:
            count += 1
            if count > 2*len(c['program'])+2: raise ValueError('policy depth')
            n = cert['nodes'][nid]
            if n['kind'] == 'split': nid = n['children'][observation(c,m)]
            elif n['kind'] == 'choice':
                a = n['best']; m = run(c,w,m,choice=a); nid = n['children'][str(a)]
            elif n['kind'] == 'leaf': break
            else: raise ValueError('policy node')
        rows.append({'world':w['id'],'reference':list(ideal),'actual':list(m.output),'loss':distance(c,m.output,ideal)})
    if max(x['loss'] for x in rows) != cert['value']: raise ValueError('policy replay value')
    return rows
