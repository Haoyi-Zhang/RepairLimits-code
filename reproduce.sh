#!/bin/sh
# All children are sequential. Each campaign command enforces its own 40 CPU-s cap.
set -eu
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
python -m repair.pilot
python -m repair.boundary_pilot
python -m repair.causality_pilot
python -m repair.assurance
for i in 0 1 2 3 4 5 6 7; do python -m repair.campaign correlations "$i"; done
python -m repair.campaign mechanisms 0
for i in 1 2 3 4 5 6 7; do python -m repair.campaign chains "$i"; done
for i in 0 1 2 3 4 5 6 7 8 9 10 11; do python -m repair.campaign guarded "$i"; done
for i in 0 1 2 3 4 5 6 7; do python -m repair.campaign timing "$i"; done
for i in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23; do python -m repair.campaign abstract "$i"; done
for i in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39; do python -m repair.campaign symbolic "$i"; done
python -m repair.aggregate
python -m repair.final_audit
