# Observational limits of budgeted failure-oblivious repair

This repository contains a finite checked-memory interpreter, exact synthesis,
a separately implemented semantic certificate checker, an exhaustive compatible-
path oracle, and a restricted symbolic observation-timing checker. It is a
self-contained research artifact, not a production recovery or security tool.
No external datasets, solvers, model services, or network access are required.

## What is established

The full arguments are in `proofs/semantic-boundary.md`. In the unique-failure
bijection fragment, substituting each repair word's unique failing input into
its predecision observations gives an exact dichotomy: all substituted
observations depend only on past choices, so every policy fails on exactly one
input and the entire domain is a minimum impossibility core; or some observation
depends on an unchosen coordinate, yielding a two-tail zero-loss policy.
An owned program family realizes a zero-budget, one-output-bit core of size
2^d. This is a restricted program-semantic result, not a universal synthesis
algorithm. The common-map Hamming compression bound is a direct corollary of
Alon, Jin and Sudakov's existing theorem and is not claimed as new.

## Run

Use Python 3.10 or later on a POSIX system supporting `resource.setrlimit`.
Only the standard library is used. From this directory:

```sh
python -m repair.pilot
python -m repair.boundary_pilot
python -m repair.causality_pilot
python -m repair.assurance
python -m repair.cli solve inputs/correlated-xor.json > /tmp/repair-certificate.json
python -m repair.cli check inputs/correlated-xor.json /tmp/repair-certificate.json
python -m repair.cli oracle inputs/correlated-xor.json
python -m repair.cli symbolic inputs/implicit/guarded-20-mixed.json
python -m repair.aggregate
python -m repair.final_audit
```

To rerun the entire deterministic campaign:

```sh
sh reproduce.sh
```

The script runs one scientific worker at a time and overwrites current generated
inputs/results, not source files. Each of its 100 campaign chunks can instead be
run separately using `python -m repair.campaign COHORT INDEX`; the complete index
ranges are in `repair/aggregate.py` and `reproduce.sh`. Interrupted chunks do not
publish a completed chunk result; rerun that chunk. No file is downloaded.
The four largest guarded chunks use sequential slices of at most eight world
deletions, with no change to the logical 100-chunk campaign or its 252 deletion
checks. Each process retains the 40-CPU-second and 3-GiB limits. The logical
chunk records the sum of its children’s CPU time and their largest RSS; its
aggregate CPU can exceed 40 seconds. A child failure leaves no completed new
chunk result. Slower systems can still hit a per-process limit. Such termination
is **unknown**, never proof of infeasibility. BDD node caps are deliberately not
raised to turn unfavorable outcomes into successes.

The current assurance suite has 22 test groups. The retained POSIX campaign
records 16; two added observation-boundary groups exercise six guarded program
variants without changing the frozen cohort counts. They distinguish a value
overwritten before a decision from one saved in another visible register.

Six separate pure finite controls run with
`python -B tests/symbolic_cache_regression.py`, explicitly in scientific CI.
They use test-local concrete truth tables and two-tail replay, every-register
visibility/overwrite controls, call-local map/order checks and exact node-cap
boundaries. They do not import POSIX resource controllers, replace the 22-group
native assurance suite, or constitute a new full-campaign receipt.

Within one symbolic classification, repeated observation roots share only their
diagonal BDD root and immutable support under that call's fixed substitution.
Every component still intersects support with its current future-action set.
Prefix/policy substitutions for positive replay are recomputed separately;
no entries survive into another BDD, map, call or variable order. At most 20
decisions and 65 visible register/output components bound this local index to
1,300 entries. Diagram allocation caps, first-witness order and unknown outcomes
are unchanged. No measured speedup or broader semantic guarantee is claimed.

For the flat standalone repository, `.github/workflows/scientific-checks.yml`
prepares the same complete campaign on Ubuntu 24.04 for pushes to `main` and
manual dispatch. It uses a 15-minute whole-campaign wall limit, the existing
per-process limits and fixed diagram caps, strict coverage gates, and an
always-run upload of the nonhidden `raw-output/` logs and `results/` tree. This
workflow is prepared configuration, not a record of a hosted run. The separate
repository-integrity workflow checks source syntax and materials only.

The CLI distinguishes phases. Malformed JSON, schema violations, and invalid
semantic evidence return exit code 2 with `status: rejected`; a declared search
cap, memory exhaustion, or call-stack exhaustion during semantic execution
returns exit code 3 with `status: unknown-resource`. The error JSON includes a
`stage` field (`input-validation`, `semantic-validation`, or `semantic-search`).
The compatible-path oracle's cross-world depth-first search uses explicit stack
frames, so the declared 1,024-world interface does not depend on CPython's
default recursion depth.

## Evidence and limits

`results/chunks/` holds raw outcomes and resource observations. `results/summary.json`
and `results/tables/` are derived by `repair.aggregate`; `results/reproduction.json`
records a fresh ZIP-extraction run and a resource-normalized structural comparison
of 1,374 scientific files with no scientific differences. `results/final-audit.json`
records a fresh recomputation of all explicit certificates/replays, all stored
exact-oracle comparisons, all positive two-tail witnesses, and metadata counts.
The aggregator checks
stored dimensions, certificate values, and replay maxima, but is not a substitute
for recomputing certificates. `results/certificates/` includes all action branches;
`results/replays/` includes every input world's reference/actual trace and loss.
All abstract two-choice games retain individual outcomes. Guarded deletion
checks retain deleted identifiers and checked values; their full certificates
are regenerated rather than duplicated. Implicit input specifications, including
full-domain dimensions and affine premises, are under `inputs/implicit/`.
`inputs/regression/oracle-1024-no-faults.json` is the retained maximum-world
boundary fixture. `results/oracle-1024-boundary-pre-fix.json` preserves the
observed original failure, while `results/oracle-1024-boundary-regression.json`
records the repaired solver/checker/oracle agreement and CLI status checks.
`results/oracle-1024-existing-evidence-comparison.json` verifies that the
previous campaign evidence remained unchanged apart from rerun resource fields.
The repaired standalone ZIP was also executed from a fresh extraction through
all 100 fixed chunks and final audit; the comparison summary is embedded in
`results/oracle-1024-boundary-regression.json`.

The synthesis VM and checking VM are separately written. The path oracle shares
the checking VM: there are not three independent semantic implementations.
General proofs are written mathematical arguments, not proof-assistant theorems.
The same AI research executor authored these components; code diversity is not
an independent review. No human experiment or real faulting application was run.
All examples are deliberately bounded programs, not a sample of deployment bugs.
See `docs/model.md`, `docs/resources.md`, `bibliography_verification.csv`, and the claim-evidence ledger.

## Provenance and license

Original code, generated inputs, and original artifact documentation are covered
by `LICENSE`. Literature is attributed in `external_resources.csv`; the 30 manuscript entries
are audited in `bibliography_verification.csv`. No copyrighted research PDF or
external implementation source is bundled.
