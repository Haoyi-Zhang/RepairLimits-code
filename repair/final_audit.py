"""Recompute retained finite evidence from files and reject cross-file drift.

This audit is deterministic and self-contained.  It does not constitute an
independent author or a proof assistant; it is a final consistency pass over
all explicit certificates/replays, every stored exact-oracle comparison, timing
witness replays, chunk identities, aggregate counts, and bibliography metadata.
"""
from __future__ import annotations

import csv
import json
import resource
import time
from collections import Counter
from pathlib import Path

from .aggregate import CHUNKS
from .campaign import write_json
from .causality_pilot import replay_two_tail
from .check import check_certificate, policy_replay
from .model import validate
from .oracle import exact_oracle


def load(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (40, 40))
    cpu, wall = time.process_time(), time.monotonic()
    root = Path('.')

    expected_chunks = {f'{cohort}-{i}.json' for cohort, indices in CHUNKS.items() for i in indices}
    actual_chunks = {p.name for p in (root / 'results/chunks').glob('*.json')}
    if actual_chunks != expected_chunks:
        raise ValueError('chunk set mismatch')

    rows_by_case = {}
    oracle_checked = 0
    abstract_games = abstract_repairable = abstract_obstruction = 0
    symbolic = []
    for cohort, indices in CHUNKS.items():
        for index in indices:
            chunk = load(root / 'results/chunks' / f'{cohort}-{index}.json')
            if chunk['cohort'] != cohort or chunk['chunk'] != index or chunk['workers'] != 1:
                raise ValueError('chunk identity mismatch')
            if cohort == 'abstract':
                result = chunk['results']
                if len(result['rows']) != result['games']:
                    raise ValueError('abstract row count mismatch')
                abstract_games += result['games']
                abstract_repairable += result['repairable']
                abstract_obstruction += result['obstruction']
            elif cohort == 'symbolic':
                symbolic.extend(chunk['results'])
            else:
                for row in chunk['results']:
                    if row['case'] in rows_by_case:
                        raise ValueError('duplicate explicit case')
                    rows_by_case[row['case']] = row
                    oracle_checked += row['oracle'] is not None

    case_ids = set(rows_by_case)
    input_ids = {p.stem for p in (root / 'inputs').glob('*.json')}
    certificate_ids = {p.stem for p in (root / 'results/certificates').glob('*.json')}
    replay_ids = {p.stem for p in (root / 'results/replays').glob('*.json')}
    if not (case_ids == input_ids == certificate_ids == replay_ids):
        raise ValueError('explicit evidence file-set mismatch')

    for case_id, row in sorted(rows_by_case.items()):
        case = load(root / 'inputs' / f'{case_id}.json')
        certificate = load(root / 'results/certificates' / f'{case_id}.json')
        stored_replay = load(root / 'results/replays' / f'{case_id}.json')
        validate(case)
        checked = check_certificate(case, certificate)
        rebuilt_replay = policy_replay(case, certificate)
        if rebuilt_replay != stored_replay:
            raise ValueError(f'replay mismatch: {case_id}')
        if checked['value'] != row['value'] or checked['nodes'] != row['certificate_nodes']:
            raise ValueError(f'certificate summary mismatch: {case_id}')
        if len(case['worlds']) != row['worlds'] or len(case['program']) != row['instructions']:
            raise ValueError(f'input dimension mismatch: {case_id}')
        if row['oracle'] is not None and exact_oracle(case) != row['oracle']:
            raise ValueError(f'oracle mismatch: {case_id}')

    expected_two_tail = set()
    for case_id, row in rows_by_case.items():
        symbolic_result = row.get('symbolic')
        if symbolic_result and symbolic_result.get('classification') == 'repairable':
            expected_two_tail.add(case_id)
            rebuilt = replay_two_tail(load(root / 'inputs' / f'{case_id}.json'), symbolic_result['policy'])
            if rebuilt != load(root / 'results/two-tail' / f'{case_id}.json'):
                raise ValueError(f'two-tail replay mismatch: {case_id}')
    actual_two_tail = {p.stem for p in (root / 'results/two-tail').glob('*.json')}
    if actual_two_tail != expected_two_tail:
        raise ValueError('two-tail evidence file-set mismatch')

    summary = load(root / 'results/summary.json')
    expected_summary = {
        'chunks': len(expected_chunks),
        'explicit_instances': len(rows_by_case),
        'oracle_checked_instances': oracle_checked,
        'abstract_games': abstract_games,
        'abstract_repairable': abstract_repairable,
        'abstract_obstruction': abstract_obstruction,
        'symbolic_checks': len(symbolic),
        'symbolic_outcomes': dict(Counter(row['status'] for row in symbolic)),
        'timing_repairable': sum(row.get('symbolic', {}).get('classification') == 'repairable'
                                 for row in rows_by_case.values() if row['case'].startswith('guarded-') and '-observe-' in row['case']),
        'timing_obstruction': sum(row.get('symbolic', {}).get('classification') == 'obstruction'
                                  for row in rows_by_case.values() if row['case'].startswith('guarded-') and '-observe-' in row['case']),
        'guarded_deletion_checks': sum(len(row.get('all_world_deletions', [])) for row in rows_by_case.values()),
        'zero_baseline_strictly_worse': sum(row['zero_value'] > row['value'] for row in rows_by_case.values()),
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            raise ValueError(f'summary mismatch: {key}')

    with (root / 'bibliography_verification.csv').open(newline='') as f:
        bibliography = list(csv.DictReader(f))
    keys = [row['key'] for row in bibliography]
    if len(bibliography) != 30 or len(set(keys)) != 30:
        raise ValueError('bibliography verification row/key count')
    required = {'title', 'publication', 'year', 'identifier', 'verification_url', 'verification_basis', 'access_date'}
    if any(not required <= row.keys() or any(not row[field] for field in required) for row in bibliography):
        raise ValueError('incomplete bibliography verification row')
    if any(not row['verification_url'].startswith('https://') for row in bibliography):
        raise ValueError('bibliography verification URL')

    with (root / 'external_resources.csv').open(newline='') as f:
        resources = list(csv.DictReader(f))
    if len({row['name'] for row in resources}) != len(resources):
        raise ValueError('duplicate external resource name')

    out = {
        'status': 'pass',
        'chunks_checked': len(expected_chunks),
        'explicit_certificates_rechecked': len(rows_by_case),
        'policy_replays_recomputed': len(rows_by_case),
        'exact_oracles_recomputed': oracle_checked,
        'two_tail_replays_recomputed': len(expected_two_tail),
        'abstract_games_accounted': abstract_games,
        'symbolic_rows_accounted': len(symbolic),
        'bibliography_rows_checked': len(bibliography),
        'external_resource_rows_checked': len(resources),
        'cpu_seconds': time.process_time() - cpu,
        'wall_seconds': time.monotonic() - wall,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'workers': 1,
    }
    write_json(root / 'results/final-audit.json', out)
    print(json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    main()
