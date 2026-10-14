# Certificate cost on the declared finite contract

`repair.evidence_recheck` reuses the 374 retained explicit programs and their
exact declared world sets; it does not add a workload population. Both measured
paths read the same input bytes, validate the same finite schema, compute each
world's healthy reference, solve the same full-history minimax problem, and
replay an attaining uniform policy on every declared world. Neither path gives
world identifiers, heap contents, or healthy traces to the executing handler.
All current observations remain visible. The control uses the checking VM and
ordinary information-set dynamic programming without importing the synthesis
search. It retains optimal suffix actions but exports no complete value DAG.

The semantic guarantee is the same exact finite optimum and attaining policy
conditional on trusted implementations. The assurance interface is different:
only the certificate path exports all alternatives for a separate checker.
The control is not an equally portable optimality proof and the shared audit VM
is not an additional independent interpreter. The compatible-path oracle is
recomputed for the unchanged 349 eligible cases; the other 25 remain unrun.

Measurement order alternates by lexical case ordinal, fixed before measurement.
Each invocation starts fresh algorithmic caches; no learned matrix or retained
optimum is given to either measured solver. Costs include input file acquisition
and strict parsing, validation, reference evaluation, search, full policy replay,
and output serialization/write. The certificate path additionally generates,
serializes, reparses, and independently checks its complete DAG. CPU and wall
time are single-run host observations under `tracemalloc`; its peak is traced
Python allocation, not RSS or total physical memory. Operating-system file caches
are not flushed and short per-case CPU readings can be zero at clock resolution.
There is no independent workload sampling, latency-distribution estimate, or
production speedup claim. The certificate overhead is retained even when it is
unfavorable. Whole-process CPU includes imports, source inventory, generation,
shared cross-checks, deletions, abstract games, and symbolic checks; the outer
command wall additionally includes interpreter startup. These are measured
execution costs, not a full human development or maintenance-cost estimate.

The portable command runs on the current Windows Python host without importing
or impersonating POSIX `resource`. Its semantic node and path limits are
unchanged, but it imposes no OS address-space or CPU cap. This is not a receipt
for the POSIX CLI, historical subprocess orchestration, or a hosted CI run.
The older POSIX measurements and all 12 symbolic node-cap unknown outcomes stay
intact. All 98,304 abstract rows and 80 symbolic configurations are actually
recomputed, not merely inferred from their summary counts.

Run from the standalone artifact with a **new** output directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m repair.evidence_recheck --output /tmp/repair-semantic-normal
PYTHONDONTWRITEBYTECODE=1 python -B -O -m repair.evidence_recheck --output /tmp/repair-semantic-optimized
```

On Windows set `PYTHONDONTWRITEBYTECODE=1` in the shell and choose a new local
directory. Existing output directories are rejected. Historical files are read
and byte-checked, never overwritten by this command. `source_bindings` in each
summary names artifact-relative implementation files. The row-level input
digests bind costs and values to the retained inputs. Reconstructed certificates
and certificate-policy replays must equal their historical JSON structures;
the value-only replays must equal those same traces and losses.

The admission regression uses a seven-node complete certificate for a two-read
copy program, with a six-node checking quota. Before repair it raised
`ValueError('node count')`; the repaired checker raises `ResourceExhausted`.
At seven nodes it proves the exact optimum two and zero-budget infeasibility.
Thus resource refusal and semantic impossibility are not interchangeable.
An empty, non-dictionary, or format-oversized node map is still rejected.
Boolean numeric fields and Boolean quotas remain invalid. This is a resource
classification repair, not evidence of a new theorem or deployed recovery gain.
