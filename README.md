# Observational limits of budgeted failure-oblivious repair

This artifact implements a finite checked-memory interpreter, exact repair
synthesis, a separately implemented semantic certificate checker, an exhaustive
compatible-path oracle, and a symbolic observation-timing checker. Its inputs
are authored bounded programs. The mathematical arguments are in
[proofs/semantic-boundary.md](proofs/semantic-boundary.md).

## Requirements

Full reproduction and the bounded CLI require CPython 3.10 or later on a POSIX
system with `resource.setrlimit`. Only the Python standard library is used;
no network access, external dataset, solver, or model service is needed.
The symbolic cache regressions below also run on Windows without POSIX limits.

## Quick checks

Run from this directory:

```sh
python -B tests/symbolic_cache_regression.py
```

This runs six pure finite regression methods against literal truth tables,
including visibility, overwritten observations, witness replay, call isolation,
and node-cap boundaries. These controls are separate from campaign counts.

On POSIX, produce and check a small certificate:

```sh
python -B -m repair.cli solve inputs/correlated-xor.json > /tmp/repair-certificate.json
python -B -m repair.cli check inputs/correlated-xor.json /tmp/repair-certificate.json
python -B -m repair.cli oracle inputs/correlated-xor.json
python -B -m repair.cli symbolic inputs/implicit/guarded-20-mixed.json
```

CLI schema or semantic rejection exits with code 2; a declared search, memory,
or stack limit exits with code 3 and an unknown-resource status. Error JSON
identifies the phase. A resource limit does not establish infeasibility.

## Full reproduction

```sh
sh reproduce.sh
```

Run this command in a disposable copy: it regenerates inputs and results in
place. The script runs one scientific child at a time, executes all 100 fixed
campaign chunks, aggregates the results, and rechecks retained certificates
and oracle comparisons. Individual chunks can be rerun with
`python -m repair.campaign COHORT INDEX`; exact ranges are in
`reproduce.sh` and `repair/aggregate.py`.

Each scientific process has 40 CPU seconds, 3 GiB address space, and fixed
diagram limits. The four largest guarded chunks use sequential slices; the
logical chunk records their summed CPU and maximum RSS. An interrupted or
failed chunk does not publish a completed result. See
[docs/resources.md](docs/resources.md) for resource accounting.

The scientific CI runs the full POSIX campaign, checks frozen coverage and all
27 assurance groups, runs the six cache controls separately, and uploads raw
logs and results even after failure. The repository-integrity workflow checks
syntax and required material. Current run outcomes are in the repository's
Actions view rather than encoded as a permanent README claim.

## Inputs, outputs, and interpretation

- `inputs/`: explicit programs, implicit specifications, and regression fixtures.
- `results/chunks/`: campaign outcomes and resource observations.
- `results/certificates/` and `results/replays/`: branch evidence and world-level traces.
- `results/summary.json` and `results/tables/`: outputs of `repair.aggregate`.
- `results/final-audit.json`: retained-evidence recomputation by `repair.final_audit`.
- `tests/`: assurance, admission, chunk-boundary, and cache regressions.
- [docs/model.md](docs/model.md): model, observations, and checking contracts.

The checked unique-failure fragment has an observation-dependent dichotomy:
past-choice-only observations yield one failing input per policy, while an
observation of an unchosen coordinate yields a two-tail zero-loss policy.
The owned zero-budget family realizes a core of size 2^d.
The Hamming-compression bound uses Alon, Jin and Sudakov's existing theorem.

The synthesis and checking VMs have separate source implementations; the path
oracle shares the checking VM. The written arguments provide the general
proofs, while executable checks cover finite instances. The fixtures are not
deployment-bug samples.

[docs/value-cost.md](docs/value-cost.md) describes the portable retained-input
recheck and same-guarantee no-certificate minimax control. It includes complete
input-to-replay costs and unfavorable overhead. Portable measurements do not
enforce POSIX resource limits; the POSIX subprocess test group is excluded,
not counted as passed.

## Provenance and license

Original code, generated data, and original documentation use [LICENSE](LICENSE).
Literature attribution is in `external_resources.csv`; the claim-evidence
ledger maps results to proofs and outputs. The metadata-verification CSV is a
bounded metadata record, not full-text certification. No third-party paper or
implementation is redistributed.

An AI research executor contributed to the implementations. Their separate
source code is not independent authorship or external review. The artifact
contains no human experiment or real faulting-application deployment.
