# Model and certificate boundary

The explicit input schema is validated by `repair.model.validate`. An input
contains a unique case identifier, bit width 1–8, 1–64 registers, 1–64 memory
cells, 1–256 instructions, 1–1024 worlds, a loss metric, output-position weights,
and a nonnegative integer budget. All branches jump strictly forward. Registers
start at zero; words wrap modulo 2^bits. Only constant/register expressions and
`const`, `copy`, `xor`, `add`, `eq`, `lt`, `load`, `store`, `emit`, `branch`, `halt`
are allowed. Programs never perform an unchecked host-memory access.

A world contains its initial memory and fixed set of trapped load/store sites.
It is chosen once, not resampled after an observation. A faulty or out-of-range
load selects a replacement from the finite read palette; a trapped store is
discarded. The fault-free reference ignores injected sites, but a genuinely
out-of-range reference access rejects the input. There is no abort action.
Thus any conclusion depends on the declared input/fault domain and reference.

The handler sees event kind, program counter, registers and emitted output at
its decisions. It remembers its entire observation/action history; it does not
read world identifiers, initial memory, hidden heap cells, the fault schedule,
or reference output. Program instructions can reveal hidden values by loading
registers. Register visibility before a decision is accounted for even if the
value is later overwritten. This is an interface restriction, not an assertion
that a privileged process could never inspect its heap.

A trace is the sequence of emitted machine words. Weights are indexed by trace
position, not static emit-site number; their length is the number of syntactic
emit instructions, which bounds every trace. Hamming is bitwise popcount, L1 is
absolute unsigned difference, and word loss is equality mismatch. Missing words
incur the metric's maximum single-word loss times that position's weight. This
is positional alignment, not edit distance. Zero weights make a pseudometric.

A value certificate is a finite rooted DAG. Split nodes must cover exactly all
observable successor groups and carry their maximum value. Choice nodes must
cover every legal action, not just the recommended action, and carry the minimum
child value with a valid selected action. Leaves list exactly the remaining
worlds with independently recomputed full-trace costs. The checker reconstructs
all semantic transitions, rejects unreachable extra nodes and cycles, and
bounds semantic (node,state) visits. This certifies optimality in the finite
model, not the appropriateness of the user's loss function. The CLI never writes
to paths derived from a case identifier; `campaign` generates only its own fixed
safe identifiers.

The symbolic interface uses an implicit Boolean cube and a supplied invertible
binary affine map. Its narrower straight-line semantics and premises are checked
by `repair.symbolic.classify_contract`. It checks the healthy output is zero,
actual output is exactly the affine equality, the prescribed choices occur,
and every visible predecision component. Symbolic and explicit worlds may not
both be supplied. The premise tag `affine-obstruction` names the schema; it does
not predetermine whether the classification is obstruction or repairable.
A node-cap outcome is unknown. A malformed or unproved premise is rejected.

Inclusion-minimal means every one-world deletion restores feasibility; by
monotonicity this implies all proper subsets are feasible. Minimum means no
smaller unsatisfiable subset exists anywhere in the original domain. The
ordinary deletion routine provides only inclusion-minimality. The full-domain
minimum conclusion comes from the unique-failure theorem, not that routine.

The compatible-path oracle enumerates paths within each world and combines one
path per world subject to history/action compatibility. Its cross-world search
uses explicit depth-first frames rather than one Python call frame per world.
The retained 1,024-world no-fault fixture therefore exercises the maximum
explicit world count under the default CPython recursion limit. CLI rejection
is reserved for malformed inputs or invalid evidence; resource or stack
exhaustion during a valid semantic search is reported as `unknown-resource`.
