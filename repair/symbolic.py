"""Restricted affine obstruction checker for implicit Boolean input cubes.

Original reduced ordered Boolean decision diagrams. The checker rebuilds
symbolic execution; supplied formula labels and matrices are not trusted.
This is an executable checker, not a theorem-prover mechanization.
"""
from .model import validate, integer
from .errors import ResourceExhausted


class BDD:
    def __init__(self, order, cap=200000):
        self.ranks = {x:i for i,x in enumerate(order)}
        if len(self.ranks) != len(order): raise ValueError('duplicate variable')
        self.nodes = [None,None]
        self.unique = {}
        self.cache = {}
        self.cap = cap

    def node(self, variable, low, high):
        if low == high: return low
        key = (variable,low,high)
        if key in self.unique: return self.unique[key]
        if len(self.nodes) >= self.cap: raise ResourceExhausted('BDD node budget exceeded')
        k = len(self.nodes)
        self.nodes.append(key)
        self.unique[key] = k
        return k

    def var(self, name):
        return self.node(self.ranks[name],0,1)

    def op(self, operator, a, b):
        if operator not in ('xor','and','eq','lt'): raise ValueError('unsupported Boolean operator')
        if operator in ('xor','and','eq') and a > b: a,b = b,a
        key = (operator,a,b)
        if key in self.cache: return self.cache[key]
        if a < 2 and b < 2:
            v = {'xor':a^b,'and':a&b,'eq':int(a==b),'lt':int(a<b)}[operator]
        else:
            ra = self.nodes[a][0] if a > 1 else len(self.ranks)
            rb = self.nodes[b][0] if b > 1 else len(self.ranks)
            r = min(ra,rb)
            al,ah = self.nodes[a][1:] if ra==r else (a,a)
            bl,bh = self.nodes[b][1:] if rb==r else (b,b)
            v = self.node(r,self.op(operator,al,bl),self.op(operator,ah,bh))
        self.cache[key] = v
        return v

    def support(self, root):
        seen, ranks = set(),set()
        todo = [root]
        while todo:
            u = todo.pop()
            if u<2 or u in seen: continue
            seen.add(u)
            r,lo,hi = self.nodes[u]
            ranks.add(r)
            todo.extend((lo,hi))
        return ranks

    def evaluate(self, root, valuation):
        while root > 1:
            rank,lo,hi = self.nodes[root]
            root = hi if valuation[rank] else lo
        return root

    def restrict(self, root, variable, value):
        """Cofactor a diagram by one ranked variable."""
        memo = {}
        def visit(u):
            if u < 2: return u
            if u in memo: return memo[u]
            rank,lo,hi = self.nodes[u]
            if rank == variable: out = visit(hi if value else lo)
            elif rank > variable: out = u
            else: out = self.node(rank,visit(lo),visit(hi))
            memo[u] = out
            return out
        return visit(root)

    def compose(self, root, replacements):
        """Simultaneous functional substitution; replacements are not recursed."""
        memo = {}
        def visit(u):
            if u < 2: return u
            if u in memo: return memo[u]
            rank,lo,hi = self.nodes[u]
            a,z = visit(lo),visit(hi)
            condition = replacements.get(rank,self.node(rank,0,1))
            # ITE(c,z,a) = a XOR (c AND (a XOR z)); use apply to
            # rebuild the variable ordering after substitutions.
            out = self.op('xor',a,self.op('and',condition,self.op('xor',a,z)))
            memo[u] = out
            return out
        return visit(root)

    def satisfying_assignment(self, root):
        """Return a full deterministic valuation, or None if false."""
        if root == 0: return None
        values = [0]*len(self.ranks)
        while root > 1:
            rank,lo,hi = self.nodes[root]
            if lo != 0: root = lo
            else:
                values[rank] = 1
                root = hi
        return values


def full_rank(rows,d):
    work = [sum(1<<j for j in row) for row in rows]
    rank = 0
    for bit in range(d):
        pivot = next((j for j in range(rank,d) if work[j]&(1<<bit)),None)
        if pivot is None: continue
        work[rank],work[pivot] = work[pivot],work[rank]
        for j in range(d):
            if j != rank and work[j]&(1<<bit): work[j] ^= work[rank]
        rank += 1
    return rank==d


def classify_contract(spec, certificate, order='interleaved', node_limit=200000, *, require_blind=False):
    """Return exact obstruction or two-tail policy evidence, or reject.

    Only straight-line, one-bit, literal-address programs are supported here;
    the general explicit checker accepts the larger bounded language.
    """
    integer(node_limit,2,200000,'BDD node cap')
    if not isinstance(spec,dict) or 'world_family' not in spec: raise ValueError('implicit cube required')
    if 'worlds' in spec: raise ValueError('implicit and explicit worlds cannot be combined')
    f = spec['world_family']
    if not isinstance(f,dict) or set(f)!={'kind','dimensions','faults'} or f['kind']!='boolean-cube':
        raise ValueError('unsupported family')
    d = integer(f['dimensions'],1,20,'dimensions')
    c = {k:v for k,v in spec.items() if k!='world_family'}
    c['worlds'] = [{'id':'shape','memory':[0]*(2*d),'faults':f['faults']}]
    validate(c)
    if c['bits']!=1 or c['memory_size']!=2*d or c['metric']!='hamming' or c['weights']!=[1] or c['budget']!=0:
        raise ValueError('obstruction requires one-bit Hamming output, zero budget, and a two-block heap')
    if sorted(c.get('read_actions',[0,1]))!=[0,1]: raise ValueError('both read actions required')
    if not isinstance(certificate,dict) or set(certificate)!={'kind','rows','offset'} or certificate['kind']!='affine-obstruction':
        raise ValueError('invalid obstruction certificate')
    rows,offset = certificate['rows'],certificate['offset']
    if not isinstance(rows,list) or len(rows)!=d or not isinstance(offset,list) or len(offset)!=d: raise ValueError('affine shape')
    for row in rows:
        if not isinstance(row,list): raise ValueError('affine row')
        for v in row: integer(v,0,d-1,'affine coordinate')
        if len(set(row))!=len(row): raise ValueError('duplicate affine coordinate')
    for x in offset: integer(x,0,1,'offset')
    if not full_rank(rows,d): raise ValueError('affine map is not bijective')
    xs = [f'x{i}' for i in range(d)]
    rs = [f'r{i}' for i in range(d)]
    if order=='interleaved': names = [v for pair in zip(rs,xs) for v in pair]
    elif order=='actions-first': names = rs+xs
    else: raise ValueError('unknown variable order')
    b = BDD(names,node_limit)
    hidden = {b.ranks[x] for x in xs}
    initial = [b.var(x) for x in xs]+[0]*d
    fault_sites = set(f['faults'])

    observations = []
    def execute(ideal):
        memory = list(initial)
        regs = [0]*c['registers']
        output = []
        decisions = 0
        def expression(x):
            if type(x) is int:
                if x not in (0,1): raise ValueError('non-Boolean value expression')
                return x
            return regs[int(x[1:])]
        for pc,ins in enumerate(c['program']):
            op = ins[0]
            if op in ('branch','halt'): raise ValueError('straight-line fragment required')
            if op in ('load','store'):
                addr = ins[2] if op=='load' else ins[1]
                if type(addr) is not int or not 0<=addr<len(memory): raise ValueError('literal in-bounds address required')
                if pc in fault_sites and not ideal:
                    if op!='load': raise ValueError('only read faults in obstruction fragment')
                    if decisions>=d: raise ValueError('too many fault actions')
                    # pc/event are fixed. All visible registers and past output
                    # must be independent of hidden input, at every decision.
                    if require_blind:
                        for value in regs+output:
                            if b.support(value)&hidden: raise ValueError('hidden input observed before a choice')
                    observations.append((pc,list(regs),list(output)))
                    regs[ins[1]] = b.var(rs[decisions])
                    decisions += 1
                elif op=='load': regs[ins[1]] = memory[addr]
                else: memory[addr] = expression(ins[2])
            elif op in ('const','copy'): regs[ins[1]] = expression(ins[2])
            elif op in ('xor','add','eq','lt'):
                operator = 'xor' if op=='add' else op
                regs[ins[1]] = b.op(operator,expression(ins[2]),expression(ins[3]))
            elif op=='emit': output.append(expression(ins[1]))
            else: raise ValueError('unsupported instruction')
        if not ideal and decisions!=d: raise ValueError('exactly d read decisions required')
        if len(output)!=1: raise ValueError('one output required')
        return output[0]

    ideal = execute(True)
    actual = execute(False)
    if ideal!=0: raise ValueError('reference is not constantly zero')
    expected = 1
    image = []
    for i,(row,constant) in enumerate(zip(rows,offset)):
        value = constant
        for j in row: value = b.op('xor',value,b.var(rs[j]))
        image.append(value)
        equal = b.op('eq',b.var(xs[i]),value)
        expected = b.op('and',expected,equal)
    if actual!=expected: raise ValueError('output is not the certified affine equality')
    substitutions = {b.ranks[x]:g for x,g in zip(xs,image)}
    # One immutable result per root under this invocation's fixed diagonal map.
    diagonal_cache = {}
    witness = None
    for decision,(pc,registers,trace) in enumerate(observations):
        future = {b.ranks[r] for r in rs[decision:]}
        for kind,components in (('register',registers),('output',trace)):
            for component,formula in enumerate(components):
                if formula not in diagonal_cache:
                    diagonal = b.compose(formula,substitutions)
                    diagonal_cache[formula] = (diagonal,frozenset(b.support(diagonal)))
                diagonal,support = diagonal_cache[formula]
                dependent = support&future
                if not dependent: continue
                pivot = min(dependent)
                low = b.restrict(diagonal,pivot,0)
                high = b.restrict(diagonal,pivot,1)
                assignment = b.satisfying_assignment(b.op('xor',low,high))
                if assignment is None: raise AssertionError('reduced BDD support has no influence')
                av0,av1 = list(assignment),list(assignment)
                av0[pivot],av1[pivot] = 0,1
                r0 = [av0[b.ranks[r]] for r in rs]
                r1 = [av1[b.ranks[r]] for r in rs]
                o0,o1 = b.evaluate(diagonal,av0),b.evaluate(diagonal,av1)
                if r0[:decision]!=r1[:decision] or o0==o1:
                    raise AssertionError('invalid dependence witness')
                witness = {'decision':decision,'pc':pc,'component_kind':kind,
                           'component_index':component,'first_word':r0,
                           'second_word':r1,'first_diagonal_bit':o0,
                           'second_diagonal_bit':o1}
                # Symbolically recheck the constructed two-tail strategy.
                # Force the common prefix to obtain the real observed bit.
                prefix = {b.ranks[rs[j]]:r0[j] for j in range(decision)}
                observed = b.compose(formula,prefix)
                select_second = b.op('eq',observed,o0)
                policy_map = dict(prefix)
                for j in range(decision,d):
                    policy_map[b.ranks[rs[j]]] = b.op('xor',r0[j],
                        b.op('and',select_second,r0[j]^r1[j]))
                if b.compose(actual,policy_map)!=0:
                    raise AssertionError('constructed policy fails symbolic replay')
                break
            if witness is not None: break
        if witness is not None: break
    result = {'dimensions':d,'worlds':2**d,
              'classification':'obstruction' if witness is None else 'repairable',
              'uniform_optimum':1 if witness is None else 0,
              'hindsight_optimum':0,'output_bits':1,
              'allocated_bdd_nodes':len(b.nodes),'variable_order':order,
              'instructions':len(c['program'])}
    if witness is None: result['minimum_core'] = 2**d
    else: result['policy'] = witness
    return result


def check_obstruction(spec, certificate, order='interleaved', node_limit=200000):
    """Strict blind-fragment wrapper retained for the original pilot."""
    return classify_contract(spec,certificate,order,node_limit,require_blind=True)
