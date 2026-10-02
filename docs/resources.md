# Resource accounting and reproducibility boundary

At scientific intake the CPU quota was four cores and the memory ceiling 4 GiB;
measured current memory use was 359,243,776 bytes and writable space was
32,029,835,264 bytes. There was no stress test. Scientific execution used one
worker, 3-GiB process address-space caps, and 40-CPU-second per-chunk caps. It
requested no GPU, external compute, model/API service, or parallel scientific
child. The experiment did not request or configure swap; this is not a claim
that host swap state was independently measured.

## Final retained clean reproduction (2026-09-17)

A temporary standalone-repository ZIP was extracted into a fresh directory.
Every generated input and result was deleted before execution. The three pilots,
16 assurance groups, all 100 fixed campaign chunks, aggregation, and the final
audit were then run sequentially with one worker. The retained 100 completed
chunks record 73.852731904 CPU seconds in aggregate and a maximum observed
process RSS of 151,216 KiB. The pilots record 0.019229670, 0.420113107, and
0.100985289 CPU seconds; assurance records 0.115491941 CPU seconds; the final
audit records 2.320419350 CPU seconds. These are local feasibility observations,
not portable performance measurements. Short values may be zero at the clock's
resolution.

Two outer tool calls reached the environment wall limit while `guarded-11` and
`symbolic-21` were active. Atomic result publication left neither active chunk
file behind. Each missing fixed index was subsequently executed once to
completion; no completed chunk was duplicated. Charging the full 40-CPU-second
per-child cap for both interrupted active children gives a conservative
153.852731904-second upper bound for campaign-chunk CPU. Exact all-session CPU,
including unmetered orchestration and any partially consumed interrupted-child
CPU, is not known and is not claimed.

The clean run and the pre-run delivery candidate were compared structurally over
1,374 scientific files: 474 generated inputs, 374 complete certificates, 374
per-world replays, 100 chunk files, 40 positive two-tail replays, six aggregate
CSV tables, and six root scientific result files (the three pilots, assurance,
summary, and final audit). File sets agreed. JSON comparison excluded only
`cpu_seconds`, `wall_seconds`, `peak_rss_kib`,
`cpu_seconds_completed_chunks`, and `peak_rss_kib_completed_chunks`; the
matching CPU/RSS columns in `cohorts.csv` were likewise excluded. No scientific
difference remained. The retained evidence is the clean-run output itself, and
`results/reproduction.json` records the comparison. The 12 capped symbolic
configurations remain `unknown-node-cap`; resource exhaustion was not relabeled
as infeasibility.

## Explicit-world oracle boundary regression (2026-09-25)

Under Linux/CPython with the default recursion limit of 1,000, the retained
one-bit fixture with one register, ten heap cells, the single instruction
`emit 0`, unit Hamming weight, zero budget, and all 1,024 distinct ten-bit
initial memories first returned exit code 2 with `status: rejected` and
`maximum recursion depth exceeded`. This is an observed pre-repair result, not
a static inference. Each world has no fault and exactly one execution path;
thus the failure occurred in cross-world path selection rather than path or
combination-cap exhaustion.

After replacing the one-call-per-world selector with an explicit depth-first
stack, the same fixture returns value zero from synthesis, certificate checking,
and the compatible-path oracle. The checker replays all 1,024 worlds at zero
loss; the oracle records 1,024 paths and 1,024 attempted combinations. A fixed
symbolic node-cap case returns exit code 3 with `unknown-resource` at stage
`semantic-search`, while a missing-fields input returns exit code 2 with
`rejected` at stage `input-validation`. The 16 assurance groups pass, and the
final audit recomputes the existing 374 certificates/replays and 349 stored
exact-oracle comparisons without a scientific mismatch. Raw command outputs
are retained in `results/oracle-1024-boundary-pre-fix.json` and
`results/oracle-1024-boundary-regression.json`.

## Acquisition and interpretation boundary

No experimental dataset or executable baseline was downloaded. The supplied
85,267-byte template ZIP expands to 353,285 bytes. Scholarly sources were read
through web retrieval and publisher, DOI, author, institutional, or archive
records; provider-side transfer size is not measured and is not represented as
zero. No copyrighted research PDF or external implementation is bundled. The
artifact retains its exact generated inputs and original code rather than
relying on an omitted cache.

Outputs depend only on integer/Boolean semantics and deterministic enumeration.
Elapsed time, CPU time, and RSS are expected to differ across systems. A
successful command is not by itself a proof of the mathematical theorems; the
written proofs, certificate checks, exact finite oracles, mutation tests, and
replays address distinct obligations. No bit-for-bit resource-record claim,
toolchain fingerprint, hash/commit manifest, or version-tagged artifact is made.
