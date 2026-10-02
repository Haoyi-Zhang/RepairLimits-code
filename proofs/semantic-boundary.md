# Semantic maps and input obstructions

## Model and conventions

A world fixes an initial finite heap and a set of failed memory-instruction sites before execution. The reference run uses the same initial heap and ignores the seeded failures; it must have no invalid memory access. The actual program checks every memory access. At a failed or out-of-bounds read a handler supplies a value from a declared finite palette; at a failed or out-of-bounds write it discards that write. These operations never access invalid storage. The program is acyclic, has fixed-width registers, and has a finite heap. Thus every legal continuation terminates. No claim is made about unbounded programs, production memory corruption, or recovery of an unspecified intended behavior.

At a handler decision the observation is the event kind, instruction position, register values and emitted trace. The handler may remember the sequence of observations and its own past actions. It cannot inspect the heap, the world identifier, the fault schedule or the reference trace except insofar as the program has exposed their consequences in an observation. A deterministic policy is a function on those observation/action histories. One policy must work for every world in the declared domain.

For a program P, policy pi and world w, write T(pi,w) for the actual trace and R(w) for the reference trace. For a declared nonnegative integer trace loss L and budget B, pi is admissible on U precisely when L(T(pi,w),R(w)) <= B for every w in U. An input obstruction is a subset U on which no policy is admissible. An inclusion-minimal obstruction loses this property after any one world is removed. A minimum obstruction has smallest cardinality among all obstructions in the specified full domain. These are different notions.

The finite explicit implementation uses positional weighted Hamming, absolute-value or word-mismatch loss. Missing output positions receive the maximum per-token loss. The geometry below concerns unweighted Hamming loss on fixed-length traces only.

## Proposition 1: fixed-world min-max semantics

Let K contain pairs (w,s_w) of world identifiers and their current full states after execution has been normalized to a handler boundary or termination. Keep the same identifier, heap, registers and entire emitted trace throughout a branch. Partition K by the current visible observation. For a terminal block, the value is the maximum complete trace loss of its members. For a nonterminal block with one common observation, its value is the minimum, over legal common actions, of the value of the normalized successor set. At a partition node the value is the maximum of its nonempty observation blocks. These equations compute

    min_pi max_{w in K} L(T(pi,w),R(w)).

### Proof

Induct on the largest number of remaining program instructions, with normalization and observation partition treated as administrative steps. At termination the equation is the definition of the worst-world loss. At one common observation the handler must choose the same action for every member; conversely every declared action is a legal common action. After that action, deterministic execution fixes the successors. Distinct next observations may have independently chosen continuation policies because a policy may remember its observations. Consequently minimization may be performed separately in each observation branch, and the worst branch determines the guarantee. The program counter strictly increases at every executed instruction, including repaired memory instructions, so the induction is well-founded.

The apparent maximizing player does not get to replace the initial world during execution. Along any selected observation path the retained world sets are nonempty and nested subsets of the original finite domain, with each world propagated by its own deterministic transitions. A terminal maximizing member therefore determines one fixed initial world consistent with the whole path. Conversely every initial world follows exactly one such path. This establishes equality with a fixed-world adversary, not a stronger resampling adversary.

A knowledge-set memoization key may omit the earlier visible history only when it retains the full current world-indexed states and references remain fixed. Two equal such keys have equal future transition systems, observations, legal actions and terminal losses. For each occurrence of the key, the same optimal suffix policy can be used. Keeping only scalar accumulated maxima or independent heap marginals does not satisfy this argument.

## Corollary 2: shared-map compression (attributed)

Let C be any candidate set, let F:C -> X^n be any common map, and let each world w specify a reference center R(w) in X^n. For a finite world set U and an integer 0 <= B < n, there is a subset U' of U of size at most 2^(B+1) such that

    {c in C : for every w in U, dist_H(F(c),R(w)) <= B}
      =
    {c in C : for every w in U', dist_H(F(c),R(w)) <= B}.

In particular, if U is an obstruction then it has an obstruction of size at most 2^(B+1). For B >= n the Hamming constraints are vacuous. An empty candidate set is already infeasible with no input constraints.

### Proof and attribution

Theorem 1.2 of Alon, Jin and Sudakov, "The Helly number of Hamming balls and related problems," arXiv:2405.10275, states that the intersection of any finite family of radius-B Hamming balls in X^n equals the intersection of at most 2^(B+1) members, for n > B. Apply that equality to the balls centered at R(w), and take its preimage under F. Preimages preserve intersections and equality. No surjectivity, convexity, injectivity or unrestricted candidate space is required. This is a direct corollary of the cited theorem, not a new Helly bound.

In particular, the familiar example consisting of all d-bit reference strings with budget d-1 is the antipodal lower-bound construction in their Proposition 2.1 (itself attributed there to earlier work). It must not be presented as a new result of this project.

## Theorem 3: constant-budget semantic obstruction

For each d >= 1 there is a straight-line, one-bit-word, checked-memory program with 3 registers, 2d heap cells, d failed reads with binary replacement choices, and 9d+2 instructions, for which:

1. Every fault-free reference run emits the single bit 0.
2. Each world separately admits a zero-loss continuation.
3. No observation-uniform policy has loss zero on all 2^d worlds.
4. Removing any single world makes a zero-loss uniform policy possible.

Thus the minimum obstruction has exactly 2^d worlds even though the budget is zero and the output has one bit. No upper bound depending only on loss budget and output length holds for this broader program class.

### Construction

The first d heap cells contain x in {0,1}^d; the next d cells initially contain zero. For i=0,...,d-1, the program reads cell i into a temporary register at a failed site and writes the returned repair bit r_i into cell d+i with a healthy write. All such repair choices precede all healthy reads of the initial input. The initial registers are zero. The observation at each choice depends on the previous repair bits but not on x.

The remaining straight-line code computes and emits

    G(r,x) = 1 exactly when x = not r.

This uses an equality accumulator and two temporary registers. For each coordinate it initializes a temporary to 1, XORs the corresponding stored repair bit, reads the corresponding original input bit, compares them, and updates the accumulator by a Boolean AND encoded using XOR and less-than. There are two instructions per repair choice, one accumulator initialization, seven instructions per comparison, and one emit, giving 9d+2 instructions. The code is given in the input generator and is checked symbolically rather than trusted by name.

### Proof

Before every repair choice the handler-visible state is independent of x. Inducting over the d choices, any deterministic observation-uniform policy therefore produces one common word r for all worlds. Every word r is realizable by a policy which chooses its coordinates in order.

In the reference execution the reads are healthy, so r=x. A nonempty binary word is unequal to its complement, and the reference output is zero. In the actual execution the output differs from the reference exactly at the single world x=not r. For any uniform policy choose that world; the loss is one, proving full-domain infeasibility at budget zero. This quantification is "for every fixed policy there exists a fixed world," not online alteration of the world.

For any omitted world x0, choose r=not x0. The only failing world is x0, so all remaining worlds have loss zero. Therefore every proper subset of the full domain is feasible and the full set is both inclusion-minimal and minimum. A single world x also has a zero-loss continuation, for example r=x. The full-domain optimum is exactly one, because output length is one and both words are bits.

The shared-map corollary does not apply: although the reference is constant and the output has length one, the repaired output map G(.,x) depends on the hidden world. The construction exploits later healthy computation, not unchecked storage or a reference value supplied to the handler.

## Proposition 4: matching finite-action bound

For any blind repair problem with a nonempty finite set C of possible common action words, every infeasible world domain has an obstruction of at most |C| worlds.

### Proof

For each c in C choose one world w_c on which c exceeds the budget; such a world exists by infeasibility. The set of chosen worlds rejects every candidate. Its cardinality is at most |C|. This elementary set-cover argument is not claimed as a new combinatorial result. Theorem 3 realizes equality when C={0,1}^d within the stated checked-memory program class.

## Theorem 5: restricted affine certificate

Suppose an implicit-domain instance has d binary read choices, all handler observations before these choices are independent of the hidden x in {0,1}^d, every word r in {0,1}^d is realizable, the reference output is the constant bit zero, and the actual output is

    G(r,x) = [x = A r XOR b],

where A is an invertible d-by-d binary matrix. Then its full-domain optimum is one, its hindsight optimum is zero, and its minimum obstruction has size 2^d at budget zero.

### Proof

The map g(r)=Ar XOR b is a bijection. Every uniform controller determines one r, which fails exactly at x=g(r). Omitting x0 allows r=g^{-1}(x0), which passes every remaining world. Every singleton has a passing candidate because 2^d >= 2 and exactly one candidate fails there. The reference condition is separately required: it does not follow merely from the invertibility of A. The explicit construction uses a fixed-point-free map to obtain the constant-zero reference, but the checker directly verifies the actual reference program rather than trusting that construction.

### Executable assurance boundary

The restricted checker symbolically executes both reference and repaired programs using an original implementation of reduced ordered binary decision diagrams. It rejects branch instructions, nonliteral addresses, non-Boolean values, failed writes, an incorrect number of choices, a nonconstant reference, hidden-input dependence in a handler observation, a singular matrix, or a mismatch between the computed output and the claimed affine equality. Gaussian elimination checks invertibility. Thus an accepted certificate establishes the premises of this mathematical theorem subject to the correctness of the checker implementation and input parsing.

A certificate contains the affine matrix and offset; the domain uses an explicit Boolean-cube schema. Its payload is O(d^2) bits in dense form (O(d) nonzero entries for the diagonal instance), whereas any explicitly listed obstruction contains 2^d distinct d-bit worlds, requiring Omega(d*2^d) raw world bits. This is a representation comparison for this family, not a lower bound for all proof systems. BDD size and checking time may be exponential in variable order or program structure; no general polynomial bound is asserted. The executable validation is not a proof-assistant mechanization.

## Proposition 6: exact finite path oracle

For each world, enumerate every legal finite execution and record the action selected at each full handler observation/action history. A set containing one execution per world can be implemented by one deterministic observation-uniform policy if and only if all recorded maps agree wherever their domains overlap.

### Proof

Necessity follows from functionality of a policy. For sufficiency, take the union of the agreeing maps and assign arbitrary legal actions elsewhere. Induction over each chosen execution shows that the resulting policy reaches its next recorded history and chooses its recorded action. This realizes all chosen executions. Minimizing the maximum terminal loss over these compatible choices therefore gives the same optimum as Proposition 1, using a different enumeration algorithm. Sharing one audit interpreter between the path oracle and certificate replay limits their implementation independence and is disclosed.

## Correlation and accounting diagnostics

For a fixed continuation with per-output losses delta_i(w), max_w sum_i delta_i(w) <= sum_i max_w delta_i(w). The inequality may be strict: for the m one-hot Boolean worlds and a zero output word, the left side is one and the right side is m. Consequently summing local worst-case debts is a conservative upper bound, not an exact worst-world loss. Conversely, resetting a budget at each failure can admit a continuation whose cumulative loss exceeds the single declared end-to-end budget. The general checker uses complete terminal traces and preserves world identity; it does not infer a metric on final behavior from the replacement values alone.

## Status

The arguments above are mathematical proofs written for this project. They are not externally refereed and are not mechanically verified general theorems. The two pilot result files contain finite and symbolic execution evidence for small instances. A systematic campaign, certificate mutation suite, literature-supported novelty assessment and manuscript are separate obligations; the existence of this document does not establish their completion.

## 8. An exact observation-timing criterion for unique-failure contracts

Let the choice positions be 0,...,d-1, each with a nonempty finite alphabet
A_i. Every run executes these positions in this order, with an input-independent
schedule and no other nondeterminism. A complete forced action word is an
element r of C = product_i A_i. Suppose there is a bijection g:C -> W such
that a run in world x violates the zero-loss contract exactly when x=g(r).
This is a substantial restriction on the semantics, not a property of arbitrary
repair problems. All input worlds remain fixed throughout execution. A
strategy observes and remembers its complete observation/action history.

Write O_i(a,x) for the observation before decision i under forced prefix
a=r_<i and input x. Define D_i(r)=O_i(r_<i,g(r)). This substitution is only an
analysis device: no executing repair sees g(r) or future actions. Call D_i
prefix-dependent when D_i(r)=D_i(s) for all r,s with r_<i=s_<i.

**Theorem 7 (observation-timing dichotomy).** Under these premises:

(a) If every D_i is prefix-dependent, every deterministic uniform strategy
fails on exactly one world. The complete W is a minimum-cardinality
impossibility core, and its cardinality is |C|.

(b) If some D_i is not prefix-dependent, a uniform strategy choosing between
two fixed tails at decision i has zero loss on every world. It is sufficient
to branch on a single distinguishing observation component when observations
are tuples of finite values.

*Proof of (a).* Fix any deterministic strategy. Construct an action word in
order. At step i, the earlier actions have already been chosen. Prefix
dependence fixes D_i from this prefix, independently of how the word will be
completed. Earlier D_j and earlier actions are also fixed, so the strategy
chooses one next action. This constructs exactly one r*. With x*=g(r*),
ordinary execution has, by induction, the same observations D_i(r*) and
therefore the same action word r*. It fails. Conversely, any failing execution
has x=g(r). At step zero it must take the same action as the construction;
induction gives r=r*, hence x=x*. Thus the failing world is unique. For any
proper subset U of W choose x0 outside U and the constant-action strategy
r=g^{-1}(x0), ignoring all observations. It fails only at x0 and satisfies U.
The whole W is therefore the sole unsatisfiable subset and has minimum size
|C|. This reasoning does not change the chosen input during a run.

*Proof of (b).* Choose r0,r1 with a common prefix a of length i and distinct
D_i values. Follow a while ignoring earlier observations. Let o be the actual
observation at i. Choose tail r0_>=i when o != D_i(r0); otherwise choose tail
r1_>=i. Remember this choice and ignore later observations. If the first
branch were to fail, its world would be g(r0), making its observation D_i(r0),
contradicting the branch condition. If the second branch failed, its world
would be g(r1), making the observed value D_i(r1) != D_i(r0), again a
contradiction. Both tails share the already executed prefix, so this defines
an executable uniform strategy. For tuple observations, choose any component
on which the two diagonal observations differ and apply the same argument to
that component alone. QED.

This is a fixed-point/diagonalization argument, not a claim that causality or
fixed-point induction is a newly discovered mathematical principle. Its
research use here is to connect a checkable program-semantic premise to both
a repair witness and an exact obstruction-size conclusion. The core statement is frozen for systematic falsification; its novelty and
venue significance require the accompanying closest-work analysis.

**Corollary 8 (affine sensor timing).** Let g(r)=Ar+b over F_2, with A
invertible. Suppose a sensor observes Hx after a fixed prefix of length k and
before the next choice; assume all other observations, including subsequent
ones, introduce no additional dependence on still unchosen coordinates.
The substituted observation is H A_prefix r_prefix + H A_suffix r_suffix +
Hb. If H A_suffix is nonzero, a zero-loss strategy exists. If it is zero,
and all other observations are prefix-dependent, the full cube is the
minimum impossibility core. This follows because a nonzero coefficient is
exactly Boolean functional dependence on an unchosen coordinate. Computing
Hx through ordinary instructions can expose intermediate registers; the
corollary cannot be applied by ignoring these registers. The implemented
checker analyzes every visible component at every fault decision instead.

**Symbolic implementation assurance.** The extended checker reconstructs
fault-free and repaired Boolean semantics with a reduced ordered BDD. It
checks the constant reference and the unique-failure affine equality, then
substitutes g into each predecision register/trace component. Future-variable
support is equivalent to non-prefix-dependence for reduced Boolean diagrams.
A differing cofactor supplies two action words. The resulting policy is
substituted back into the actual output diagram, which must reduce to zero.
This is executable exact finite reasoning under a trusted, unmechanized BDD
implementation; diagrams and caches can grow exponentially. Resource failure
is not a classification of the input.
