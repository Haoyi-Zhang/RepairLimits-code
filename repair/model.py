"""Validated input format and the synthesis-side bounded interpreter.

Memory is accessible to programs through checked loads/stores. A repair handler
observes only (event, pc, registers, emitted trace), not the initial world label,
heap, fault schedule, or reference execution. All jumps are strictly forward.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
from typing import Any


def integer(x: Any, low: int, high: int, what: str) -> int:
    if type(x) is not int or not low <= x <= high:
        raise ValueError(f"invalid {what}")
    return x


def validate(c: dict) -> None:
    required = {"id", "bits", "registers", "memory_size", "program", "worlds", "metric", "weights", "budget"}
    if type(c) is not dict or not required <= c.keys() or c.keys() - required - {"read_actions"}:
        raise ValueError("case fields")
    if type(c['id']) is not str or not c['id'] or len(c['id']) > 100:
        raise ValueError("case id")
    b = integer(c['bits'], 1, 8, 'bits'); q = 1 << b
    nr = integer(c['registers'], 1, 64, 'register count')
    m = integer(c['memory_size'], 1, 64, 'memory size')
    p = c['program']
    if type(p) is not list or not 1 <= len(p) <= 256:
        raise ValueError('program length')
    def expr(e: Any) -> None:
        if type(e) is int and 0 <= e <= 65535: return
        if type(e) is str and 2 <= len(e) <= 3 and e.startswith('r') and e[1:].isascii() and e[1:].isdigit() and str(int(e[1:])) == e[1:]:
            integer(int(e[1:]), 0, nr-1, 'register'); return
        raise ValueError('expression')
    arities = {'const':3, 'copy':3, 'xor':4, 'add':4, 'eq':4, 'lt':4, 'load':3, 'store':3, 'emit':2, 'branch':3, 'halt':1}
    for pc, ins in enumerate(p):
        if type(ins) is not list or not ins or type(ins[0]) is not str or ins[0] not in arities or len(ins) != arities[ins[0]]:
            raise ValueError('instruction')
        op = ins[0]
        if op in {'const','copy','xor','add','eq','lt','load'}:
            integer(ins[1], 0, nr-1, 'destination')
            for e in ins[2:]: expr(e)
        elif op == 'store': expr(ins[1]); expr(ins[2])
        elif op == 'emit': expr(ins[1])
        elif op == 'branch':
            expr(ins[1]); integer(ins[2], pc+1, len(p), 'forward target')
    nout = sum(i[0] == 'emit' for i in p)
    if type(c['weights']) is not list or len(c['weights']) != nout:
        raise ValueError('weights length')
    for w in c['weights']: integer(w, 0, 10000, 'weight')
    if type(c['metric']) is not str or c['metric'] not in {'hamming','l1','word'}: raise ValueError('metric')
    integer(c['budget'], 0, 10**9, 'budget')
    actions = c.get('read_actions', list(range(q)))
    if type(actions) is not list or not 1 <= len(actions) <= q: raise ValueError('actions')
    for a in actions: integer(a, 0, q-1, 'read action')
    if len(set(actions)) != len(actions): raise ValueError('duplicate actions')
    ws = c['worlds']
    if type(ws) is not list or not 1 <= len(ws) <= 1024: raise ValueError('world count')
    ids = []
    for w in ws:
        if type(w) is not dict or set(w) != {'id','memory','faults'}: raise ValueError('world fields')
        if type(w['id']) is not str or not w['id'] or len(w['id']) > 100: raise ValueError('world id')
        ids.append(w['id'])
        if type(w['memory']) is not list or len(w['memory']) != m: raise ValueError('memory length')
        for v in w['memory']: integer(v, 0, q-1, 'memory value')
        if type(w['faults']) is not list or len(w['faults']) > len(p): raise ValueError('fault list')
        for f in w['faults']:
            integer(f, 0, len(p)-1, 'fault site')
            if p[f][0] not in {'load','store'}: raise ValueError('fault not a memory access')
        if len(set(w['faults'])) != len(w['faults']): raise ValueError('duplicate faults')
    if len(set(ids)) != len(ids): raise ValueError('duplicate world ids')


@dataclass(frozen=True)
class State:
    pc: int
    regs: tuple[int, ...]
    memory: tuple[int, ...]
    trace: tuple[int, ...] = ()


def initial(c: dict, w: dict) -> State:
    return State(0, (0,)*c['registers'], tuple(w['memory']))


def ev(e: Any, s: State) -> int:
    return e if type(e) is int else s.regs[int(e[1:])]


def advance(c: dict, w: dict, s: State, reference: bool = False) -> State:
    p, mask = c['program'], (1 << c['bits'])-1
    while s.pc < len(p):
        ins = p[s.pc]; op = ins[0]
        if op == 'halt': return s
        if op in {'load','store'}:
            idx = ev(ins[2] if op == 'load' else ins[1], s)
            invalid = not 0 <= idx < c['memory_size']
            if invalid or (not reference and s.pc in w['faults']):
                if reference: raise ValueError('reference access is out of bounds')
                return s
        regs, mem, tr, nxt = list(s.regs), list(s.memory), s.trace, s.pc+1
        if op in {'const','copy'}: regs[ins[1]] = ev(ins[2], s) & mask
        elif op in {'xor','add','eq','lt'}:
            a,b = ev(ins[2],s),ev(ins[3],s)
            v = {'xor':lambda:a^b, 'add':lambda:a+b, 'eq':lambda:int(a==b), 'lt':lambda:int(a<b)}[op]()
            regs[ins[1]] = v & mask
        elif op == 'load': regs[ins[1]] = mem[idx]
        elif op == 'store': mem[idx] = ev(ins[2],s) & mask
        elif op == 'emit': tr += (ev(ins[1],s) & mask,)
        elif op == 'branch': nxt = ins[2] if ev(ins[1],s) else nxt
        s = State(nxt, tuple(regs), tuple(mem), tr)
    return s


def event(c: dict, s: State) -> str:
    if s.pc == len(c['program']) or c['program'][s.pc][0] == 'halt': return 'halt'
    return c['program'][s.pc][0]


def observe(c: dict, s: State) -> str:
    return json.dumps([event(c,s),s.pc,s.regs,s.trace], separators=(',',':'))


def actions(c: dict, s: State) -> list[int]:
    return sorted(c.get('read_actions', range(1 << c['bits']))) if event(c,s) == 'load' else [-1]


def act(c: dict, s: State, a: int) -> State:
    if a not in actions(c,s) or event(c,s) == 'halt': raise ValueError('illegal action')
    r = list(s.regs)
    if event(c,s) == 'load': r[c['program'][s.pc][1]] = a
    return State(s.pc+1,tuple(r),s.memory,s.trace)


def loss(c: dict, actual: tuple[int,...], reference: tuple[int,...]) -> int:
    missing = {'hamming':c['bits'],'l1':(1 << c['bits'])-1,'word':1}[c['metric']]
    total = 0
    for i in range(max(len(actual),len(reference))):
        if i >= len(actual) or i >= len(reference): delta = missing
        elif c['metric'] == 'hamming': delta = (actual[i]^reference[i]).bit_count()
        elif c['metric'] == 'l1': delta = abs(actual[i]-reference[i])
        else: delta = int(actual[i] != reference[i])
        total += c['weights'][i]*delta
    return total
