"""Fresh, portable semantic recheck and same-input value-only cost control.

No POSIX resource shim or native-application claim. Output must be a new directory.
Historical files are read, never overwritten. The command runs exact finite
algorithms with their unchanged node/path caps; OS CPU/AS limits are not imposed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import tracemalloc

MODULE_WALL_START = time.perf_counter()
from .aggregate import CHUNKS
from .campaign import run_abstract, run_symbolic, guarded_deletions
from .cases import correlation_cases, mechanism_cases, chain, guarded_spec, observed_guarded_spec, expand_guarded
from .causality_pilot import replay_two_tail
from .check import strict_json, check_certificate, policy_replay
from .errors import ResourceExhausted
from .oracle import exact_oracle
from .solve import synthesize
from .symbolic import classify_contract
from .value_only import solve_value, replay_value_policy


def load(path):
    return strict_json(path.read_text(encoding='utf-8'))


def scientific(value):
    if isinstance(value, dict):
        return {k: scientific(v) for k, v in value.items()
                if k not in {'cpu_seconds', 'wall_seconds', 'peak_rss_kib'}}
    if isinstance(value, list):
        return [scientific(v) for v in value]
    return value


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')


def measure(function):
    tracemalloc.start()
    cpu, wall = time.process_time(), time.perf_counter()
    result = function()
    elapsed_cpu, elapsed_wall = time.process_time() - cpu, time.perf_counter() - wall
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {'cpu_seconds': elapsed_cpu, 'wall_seconds': elapsed_wall,
                    'peak_python_traced_bytes': peak}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('output must not exist: historical evidence is immutable')
    output.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1]
    program_files = sorted((source / 'repair').glob('*.py'))
    source_bindings = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in program_files}
    historical = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for folder in ('inputs', 'results') for p in (source / folder).rglob('*') if p.is_file()}
    # process_time is cumulative from process creation, including imports and
    # initial inventory. The module wall boundary precedes algorithm imports;
    # the outer command record separately includes interpreter startup.
    start_cpu, start_wall = 0.0, MODULE_WALL_START
    explicit = []
    expected_rows = {}
    for cohort, indices in CHUNKS.items():
        for index in indices:
            chunk = load(source / 'results/chunks' / f'{cohort}-{index}.json')
            if chunk['cohort'] != cohort or chunk['chunk'] != index or chunk['workers'] != 1:
                raise ValueError('historical chunk identity')
            if cohort not in ('abstract', 'symbolic'):
                for row in chunk['results']:
                    if row['case'] in expected_rows:
                        raise ValueError('duplicate historical case')
                    expected_rows[row['case']] = (cohort, row)
    # Bind the retained source data to actual deterministic generators as well.
    generated = list(correlation_cases()) + list(mechanism_cases())
    generated += [chain(d, k, budget=d-k) for d in range(1, 8) for k in range(d+1)]
    generated += [expand_guarded(guarded_spec(d, mixed)[0]) for d in range(1, 7) for mixed in (False, True)]
    generated += [expand_guarded(observed_guarded_spec(d, mixed, ((i, j),))[0])
                  for d in range(1, 5) for mixed in (False, True)
                  for i in range(d) for j in range(d)]
    if {c['id'] for c in generated} != set(expected_rows) or len(generated) != 374:
        raise ValueError('generator/source population mismatch')
    for case in generated:
        if case != load(source / 'inputs' / (case['id'] + '.json')):
            raise ValueError('generator/input mismatch')

    oracle_count = two_tail_count = 0
    for ordinal, case_id in enumerate(sorted(expected_rows)):
        cohort, old = expected_rows[case_id]
        input_path = source / 'inputs' / (case_id + '.json')
        # Each path reacquires the identical retained bytes. Alternating order is
        # fixed by lexical ordinal, not selected after seeing measurements.
        def certified():
            case = load(input_path)
            certificate = synthesize(case)
            serialized = json.dumps(certificate, sort_keys=True, separators=(',', ':'))
            checked = check_certificate(case, strict_json(serialized))
            replay = policy_replay(case, certificate)
            write(output / 'certificates' / (case_id + '.json'), certificate)
            write(output / 'replays' / (case_id + '.json'), replay)
            return checked, certificate, replay, len(serialized.encode('utf-8'))
        def control():
            case = load(input_path)
            solution = solve_value(case)
            replay = replay_value_policy(case, solution)
            write(output / 'value-only-replays' / (case_id + '.json'), replay)
            return solution.value, solution.states, replay
        if ordinal % 2:
            baseline, baseline_cost = measure(control)
            evidence, certificate_cost = measure(certified)
        else:
            evidence, certificate_cost = measure(certified)
            baseline, baseline_cost = measure(control)
        checked, certificate, replay, certificate_bytes = evidence
        if checked['value'] != old['value'] or checked['nodes'] != old['certificate_nodes']:
            raise ValueError('recomputed explicit value/node mismatch: ' + case_id)
        if certificate != load(source / 'results/certificates' / (case_id + '.json')):
            raise ValueError('recomputed certificate mismatch: ' + case_id)
        if replay != load(source / 'results/replays' / (case_id + '.json')):
            raise ValueError('recomputed replay mismatch: ' + case_id)
        if (baseline[0], baseline[1], baseline[2]) != (checked['value'], checked['nodes'], replay):
            raise ValueError('same-input no-certificate disagreement: ' + case_id)
        oracle, oracle_cost = None, None
        if old['oracle'] is not None:
            oracle, oracle_cost = measure(lambda: exact_oracle(load(input_path)))
            if oracle != old['oracle']:
                raise ValueError('recomputed exact-oracle mismatch: ' + case_id)
            oracle_count += 1
        if 'symbolic' in old:
            descriptor = load(source / 'inputs/implicit' / (case_id + '.json'))
            symbolic = classify_contract(descriptor['specification'], descriptor['premise'])
            if symbolic != old['symbolic']:
                raise ValueError('explicit/symbolic mismatch: ' + case_id)
            if symbolic['classification'] == 'repairable':
                tails = replay_two_tail(load(input_path), symbolic['policy'])
                if tails != load(source / 'results/two-tail' / (case_id + '.json')):
                    raise ValueError('two-tail mismatch: ' + case_id)
                write(output / 'two-tail' / (case_id + '.json'), tails)
                two_tail_count += 1
        row = {'case': case_id, 'cohort': cohort, 'value': checked['value'],
               'input_bytes': input_path.stat().st_size,
               'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
               'worlds': old['worlds'], 'instructions': old['instructions'],
               'states': checked['nodes'], 'certificate_json_bytes': certificate_bytes,
               'certificate_path': certificate_cost, 'value_only_path': baseline_cost,
               'path_oracle': oracle, 'path_oracle_cost': oracle_cost,
               'measurement_order': ['value-only', 'certificate'] if ordinal % 2 else ['certificate', 'value-only']}
        explicit.append(row)
        write(output / 'explicit-rows.json', explicit)
        if ordinal % 50 == 0:
            print(json.dumps({'explicit_completed': ordinal+1}), flush=True)

    deletions = []
    os.chdir(output)  # Reviewed symbolic helpers publish only below fresh output.
    for index in range(12):
        size = 2**(index//2+1)
        rows = guarded_deletions(index, 0, size)
        previous = load(source / 'results/chunks' / f'guarded-{index}.json')['results'][0]['all_world_deletions']
        if rows != previous:
            raise ValueError('deletion mismatch')
        deletions.append({'index': index, 'rows': rows})
    write(output / 'deletions.json', deletions)
    games = 0
    for index in range(24):
        rows = run_abstract(index)
        if rows != load(source / 'results/chunks' / f'abstract-{index}.json')['results']:
            raise ValueError('abstract raw-row mismatch')
        write(output / 'abstract' / f'{index}.json', rows)
        games += rows['games']
    symbolic_rows = []
    for index in range(40):
        rows = run_symbolic(index)
        if scientific(rows) != scientific(load(source / 'results/chunks' / f'symbolic-{index}.json')['results']):
            raise ValueError('symbolic raw-row mismatch')
        symbolic_rows.extend(rows)
        print(json.dumps({'symbolic_completed': index+1}), flush=True)
    write(output / 'symbolic-rows.json', symbolic_rows)
    # Repeat the maximum-world boundary, not an application workload.
    boundary = load(source / 'inputs/regression/oracle-1024-no-faults.json')
    boundary_certificate = synthesize(boundary)
    boundary_result = {'check': check_certificate(boundary, boundary_certificate),
                       'oracle': exact_oracle(boundary),
                       'replay_worlds': len(policy_replay(boundary, boundary_certificate)),
                       'value_only': solve_value(boundary).value}
    write(output / 'oracle-boundary.json', boundary_result)
    case = chain(2, budget=0)
    certificate = synthesize(case)
    try:
        check_certificate(case, certificate, max_nodes=len(certificate['nodes'])-1)
    except ResourceExhausted as error:
        quota_result = {'case': case, 'certificate': certificate, 'quota': len(certificate['nodes'])-1,
                        'status': 'unknown-resource', 'reason': str(error),
                        'full_check': check_certificate(case, certificate)}
    else:
        raise ValueError('storage quota not enforced')
    write(output / 'budget-admission.json', quota_result)
    from collections import Counter
    for relative, digest in historical.items():
        if hashlib.sha256((source / relative).read_bytes()).hexdigest() != digest:
            raise ValueError('historical evidence changed')
    summary = {'status': 'finite-semantic-recheck', 'explicit': len(explicit),
               'oracle_recomputed': oracle_count, 'two_tail_recomputed': two_tail_count,
               'world_deletions_recomputed': sum(len(x['rows']) for x in deletions),
               'abstract_games_recomputed': games, 'symbolic_configurations_recomputed': len(symbolic_rows),
               'symbolic_outcomes': dict(Counter(row['status'] for row in symbolic_rows)),
               'value_only_values_and_replays_equal': len(explicit),
               'certificate_path_cpu_seconds': sum(r['certificate_path']['cpu_seconds'] for r in explicit),
               'value_only_path_cpu_seconds': sum(r['value_only_path']['cpu_seconds'] for r in explicit),
               'oracle_common_validation_cpu_seconds': sum((r['path_oracle_cost'] or {}).get('cpu_seconds', 0) for r in explicit),
               'certificate_path_peak_python_traced_bytes': max(r['certificate_path']['peak_python_traced_bytes'] for r in explicit),
               'value_only_path_peak_python_traced_bytes': max(r['value_only_path']['peak_python_traced_bytes'] for r in explicit),
               'certificate_json_bytes': sum(r['certificate_json_bytes'] for r in explicit),
               'input_bytes_each_path': sum(r['input_bytes'] for r in explicit),
               'total_process_cpu_seconds': time.process_time()-start_cpu,
               'total_wall_seconds': time.perf_counter()-start_wall,
               'historical_files_byte_checked': len(historical),
               'source_bindings': source_bindings,
               'environment': {'python': sys.version, 'platform': platform.platform(),
                               'optimize': sys.flags.optimize, 'workers': 1,
                               'PYTHONDONTWRITEBYTECODE': os.environ.get('PYTHONDONTWRITEBYTECODE'),
                               'os_cpu_as_limits': 'not imposed by this portable command',
                               'memory_measure': 'per-path tracemalloc high-water, not RSS'},
               'guarantee': 'same exact finite optimum and attaining uniform policy under trusted semantics; only certificate path exports all-alternatives evidence',
               'cost_scope': 'each path includes input file read/strict parse, schema/reference, search, full policy replay and output serialization/write; certificate path additionally serializes/parses/checks its complete DAG; process CPU includes imports/inventory/generation/common checks; module wall precedes algorithm imports and outer command wall additionally includes interpreter startup; no external acquisition or maintenance workload'}
    write(output / 'summary.json', summary)
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
