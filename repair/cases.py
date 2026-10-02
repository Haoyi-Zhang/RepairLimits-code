"""Original benign finite inputs, deterministic enumeration; no external programs."""
from itertools import product


def chain(d=3, reveal=0, words=None, name=None, budget=1):
    if words is None: words = list(product(range(2),repeat=d))
    program = []
    for i in range(d): program += [['load',0,i],['emit','r0']]
    return {'id':name or f'chain-{d}-{reveal}','bits':1,'registers':1,'memory_size':d,
            'program':program,'worlds':[{'id':''.join(map(str,x)),'memory':list(x),'faults':[2*i for i in range(reveal,d)]} for x in words],
            'metric':'hamming','weights':[1]*d,'budget':budget}


def correlation_cases():
    words = list(product(range(2),repeat=3))
    for mask in range(1,256):
        yield chain(words=[w for i,w in enumerate(words) if mask & (1 << i)],name=f'correlation-{mask:03d}')


def mechanism_cases():
    def c(name,bits,memories,program,faults,metric='hamming',regs=3,weights=None):
        return {'id':name,'bits':bits,'registers':regs,'memory_size':len(memories[0]),'program':program,
                'worlds':[{'id':str(i),'memory':list(m),'faults':list(f)} for i,(m,f) in enumerate(product(memories,faults))],
                'metric':metric,'weights':weights if weights is not None else [1]*sum(i[0]=='emit' for i in program),'budget':1}
    yield c('overwritten-read',1,[[0],[1]],[['load',0,0],['const',0,1],['emit','r0']],[[0]])
    yield c('correlated-xor',1,[[0,0],[1,1]],[['load',0,0],['load',1,1],['xor',2,'r0','r1'],['emit','r2']],[[0,1]])
    yield c('independent-xor',1,list(product(range(2),repeat=2)),[['load',0,0],['load',1,1],['xor',2,'r0','r1'],['emit','r2']],[[0,1]])
    yield c('lost-write',1,[[0],[1]],[['const',0,1],['store',0,'r0'],['load',1,0],['emit','r1']],[[1],[]])
    yield c('alias-write',2,[[0,1],[1,0]],[['load',0,0],['store',1,'r0'],['load',1,1],['emit','r1']],[[0,1],[1]])
    yield c('dynamic-address',2,[[0,1],[1,0]],[['load',0,0],['load',1,'r0'],['emit','r1']],[[0],[]])
    yield c('branch-length',1,[[0],[1]],[['load',0,0],['branch','r0',4],['emit',0],['emit',1],['emit','r0']],[[0]])
    yield c('wraparound',2,[[0],[1],[2],[3]],[['load',0,0],['add',1,'r0',3],['emit','r1']],[[0]])
    yield c('absolute-center',3,[[0],[3],[7]],[['load',0,0],['emit','r0']],[[0]],metric='l1')
    yield c('word-center',3,[[0],[3],[7]],[['load',0,0],['emit','r0']],[[0]],metric='word')
    yield c('weighted-debt',1,[[0,0],[1,1]],[['load',0,0],['emit','r0'],['load',0,1],['emit','r0']],[[0,2]],weights=[1,3])
    yield c('comparison-copy',2,[[0],[1],[2],[3]],[['load',0,0],['lt',1,'r0',2],['eq',2,'r0',0],['copy',0,'r1'],['emit','r0'],['emit','r2'],['halt']],[[0]])


def guarded_spec(d=3, mixed=False):
    """Implicit cube input and original straight-line Boolean program.

    First d reads fail. Their arbitrary results are saved in the upper heap.
    Healthy reads AFTER the last decision check x = A*r+b and emit one bit.
    A is unit lower triangular; its first output is not r[0], so the
    fault-free reference always emits zero. No production fault is used.
    """
    if type(d) is not int or not 1 <= d <= 20:
        raise ValueError('guarded dimensions must be between 1 and 20')
    rows = [[i] if not mixed else sorted(set([i]+([i-1] if i else [])+([0] if i>2 and i%2 else []))) for i in range(d)]
    offset = [1]*d if not mixed else [1]+[0]*(d-1)
    program = []
    faults = []
    for i in range(d):
        faults.append(len(program))
        program += [['load',0,i],['store',d+i,'r0']]
    program += [['const',2,1]]
    for i in range(d):
        program += [['const',0,offset[i]]]
        for j in rows[i]:
            program += [['load',1,d+j],['xor',0,'r0','r1']]
        program += [['load',1,i],['eq',0,'r0','r1'],
                    ['xor',1,'r2',1],['lt',2,'r1','r0']]
    program += [['emit','r2']]
    return {'id':f'guarded-{d}-'+('mixed' if mixed else 'diagonal'),
            'bits':1,'registers':3,'memory_size':2*d,'program':program,
            'metric':'hamming','weights':[1],'budget':0,
            'world_family':{'kind':'boolean-cube','dimensions':d,'faults':faults}}, \
           {'kind':'affine-obstruction','rows':rows,'offset':offset}


def expand_guarded(spec):
    """Expand an implicit family only for bounded explicit cross-checks."""
    import copy
    d = spec['world_family']['dimensions']
    if d > 10: raise ValueError('explicit expansion is limited to 1024 worlds')
    c = copy.deepcopy(spec)
    family = c.pop('world_family')
    c['worlds'] = [{'id':''.join(map(str,x)), 'memory':list(x)+[0]*d,
                    'faults':list(family['faults'])}
                   for x in product(range(2),repeat=d)]
    return c


def observed_guarded_spec(d=3, mixed=False, leaks=()):
    """Insert healthy coordinate reads immediately before chosen fault reads.

    Each (decision, coordinate) pair loads that input bit into visible r1.
    Leaks are part of the program, not an oracle supplied to the handler.
    Multiple loads before one decision leave only the last loaded bit in r1.
    """
    spec,cert = guarded_spec(d,mixed)
    by_decision = {}
    for decision,coordinate in leaks:
        if type(decision) is not int or not 0 <= decision < d: raise ValueError('leak decision')
        if type(coordinate) is not int or not 0 <= coordinate < d: raise ValueError('leak coordinate')
        by_decision.setdefault(decision,[]).append(coordinate)
    oldfaults = set(spec['world_family']['faults'])
    instructions,faults = [],[]
    decision = 0
    for pc,ins in enumerate(spec['program']):
        if pc in oldfaults:
            for coordinate in by_decision.get(decision,[]):
                instructions.append(['load',1,coordinate])
            faults.append(len(instructions))
            decision += 1
        instructions.append(ins)
    spec['program'] = instructions
    spec['world_family']['faults'] = faults
    suffix = '-'.join(f'{i}.{j}' for i,j in leaks) or 'none'
    spec['id'] += '-observe-'+suffix
    return spec,cert
