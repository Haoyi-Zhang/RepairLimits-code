"""Pure finite diagonal-cache controls, explicit in CI; no resource shim.

The scalar reference below enumerates owned small worlds/action words directly.
It does not import BDD operations, production interpreters or historical code.
"""
import copy
import itertools
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repair.cases import guarded_spec, observed_guarded_spec
from repair.errors import ResourceExhausted
from repair.symbolic import BDD, classify_contract, check_obstruction


def scalar_execute(spec, world, word=None, policy=None, ideal=False):
    """Direct one-bit literal-address VM with actual predecision visibility."""
    d = spec['world_family']['dimensions']
    memory = list(world) + [0] * d
    registers = [0] * spec['registers']
    trace, observations, decisions = [], [], 0
    faults = set(spec['world_family']['faults'])
    branch = None
    chosen = []
    def value(expression):
        return expression if type(expression) is int else registers[int(expression[1:])]
    for pc, ins in enumerate(spec['program']):
        op = ins[0]
        if op == 'load' and pc in faults and not ideal:
            obs = (pc, tuple(registers), tuple(trace))
            observations.append(obs)
            if policy is not None:
                if decisions == policy['decision']:
                    if pc != policy['pc']:
                        raise AssertionError('wrong policy decision location')
                    components = registers if policy['component_kind'] == 'register' else trace
                    bit = components[policy['component_index']]
                    branch = 'second_word' if bit == policy['first_diagonal_bit'] else 'first_word'
                action = policy[branch or 'first_word'][decisions]
            else:
                action = word[decisions]
            if action not in (0, 1):
                raise AssertionError('nonbinary action')
            chosen.append(action)
            registers[ins[1]] = action
            decisions += 1
        elif op == 'load':
            registers[ins[1]] = memory[ins[2]]
        elif op == 'store':
            memory[ins[1]] = value(ins[2]) % 2
        elif op in ('const', 'copy'):
            registers[ins[1]] = value(ins[2]) % 2
        elif op in ('xor', 'add', 'eq', 'lt'):
            a, b = value(ins[2]), value(ins[3])
            if op == 'xor': result = a ^ b
            elif op == 'add': result = a + b
            elif op == 'eq': result = int(a == b)
            else: result = int(a < b)
            registers[ins[1]] = result % 2
        elif op == 'emit':
            trace.append(value(ins[1]) % 2)
        else:
            raise AssertionError('reference admits only the tested straight-line fragment')
    if not ideal and decisions != d:
        raise AssertionError('wrong reference decision count')
    return tuple(trace), observations, chosen


def affine_image(premise, word):
    return tuple((constant + sum(word[j] for j in row)) % 2
                 for row, constant in zip(premise['rows'], premise['offset']))


def independent_classification(spec, premise):
    """Full small truth tables plus equal-prefix observation comparisons."""
    d = spec['world_family']['dimensions']
    if d > 4:
        raise AssertionError('finite reference is explicitly capped at four dimensions')
    words = list(itertools.product((0, 1), repeat=d))
    diagonals = []
    images = {affine_image(premise, word) for word in words}
    if len(images) != len(words):
        raise AssertionError('nonbijective reference premise')
    for world in words:
        if scalar_execute(spec, world, ideal=True)[0] != (0,):
            raise AssertionError('reference is not zero')
    for word in words:
        image = affine_image(premise, word)
        for world in words:
            output, observations, _ = scalar_execute(spec, world, word)
            if output != (int(world == image),):
                raise AssertionError('actual continuation does not match the premise')
            if world == image:
                diagonals.append((word, observations))
    for i in range(d):
        values = {}
        for word, observations in diagonals:
            prefix = word[:i]
            observation = observations[i]
            if prefix in values and values[prefix] != observation:
                return 'repairable'
            values[prefix] = observation
    return 'obstruction'


def tiny_cases():
    for d in range(1, 4):
        for mixed in (False, True):
            yield observed_guarded_spec(d, mixed)
            for i, j in itertools.product(range(d), repeat=2):
                yield observed_guarded_spec(d, mixed, ((i, j),))


def visibility_cases():
    for mixed in (False, True):
        for leaks, retained in ((((1, 2), (1, 0)), False),
                                (((1, 0), (1, 2)), False),
                                (((1, 2), (1, 0)), True)):
            spec, premise = observed_guarded_spec(3, mixed, leaks)
            if retained:
                position = spec['world_family']['faults'][1] - 1
                spec['program'].insert(position, ['copy', 2, 'r1'])
                spec['world_family']['faults'] = [pc + (pc >= position)
                                                  for pc in spec['world_family']['faults']]
            yield spec, premise, retained


class SymbolicCacheRegression(unittest.TestCase):
    def test_independent_small_truth_tables(self):
        cases = list(tiny_cases())
        self.assertEqual(len(cases), 34)
        for spec, premise in cases:
            expected = independent_classification(spec, premise)
            for order in ('interleaved', 'actions-first'):
                result = classify_contract(spec, premise, order)
                self.assertEqual(result['classification'], expected)
                self.assertEqual(result['uniform_optimum'], int(expected == 'obstruction'))
                if expected == 'obstruction':
                    self.assertEqual(result['minimum_core'], 2**spec['world_family']['dimensions'])

    def test_actual_two_tail_witness_replay(self):
        positive = 0
        for spec, premise in tiny_cases():
            result = classify_contract(spec, premise)
            if result['classification'] != 'repairable':
                continue
            policy = result['policy']; i = policy['decision']
            self.assertEqual(policy['first_word'][:i], policy['second_word'][:i])
            self.assertNotEqual(policy['first_diagonal_bit'], policy['second_diagonal_bit'])
            for key, bit in (('first_word', 'first_diagonal_bit'), ('second_word', 'second_diagonal_bit')):
                word = policy[key]
                _, observations, _ = scalar_execute(spec, affine_image(premise, word), word)
                pc, registers, trace = observations[i]
                self.assertEqual(pc, policy['pc'])
                components = registers if policy['component_kind'] == 'register' else trace
                self.assertEqual(components[policy['component_index']], policy[bit])
            for world in itertools.product((0, 1), repeat=spec['world_family']['dimensions']):
                self.assertEqual(scalar_execute(spec, world, policy=policy)[0], (0,))
            positive += 1
        self.assertGreater(positive, 0)

    def test_overwrite_and_all_register_visibility(self):
        for spec, premise, retained in visibility_cases():
            expected = independent_classification(spec, premise)
            result = classify_contract(spec, premise)
            self.assertEqual(result['classification'], expected)
            if retained:
                self.assertEqual(expected, 'repairable')
                self.assertEqual(result['policy']['component_index'], 2)
            if expected == 'repairable':
                for world in itertools.product((0, 1), repeat=3):
                    self.assertEqual(scalar_execute(spec, world, policy=result['policy'])[0], (0,))

    def test_call_local_maps_and_variable_orders(self):
        sequence = [(3, False, ((1, 0),)), (3, True, ((1, 2),)),
                    (2, True, ()), (3, False, ((0, 2),))]
        snapshots = []
        for d, mixed, leaks in sequence:
            spec, premise = observed_guarded_spec(d, mixed, leaks)
            expected = independent_classification(spec, premise)
            for order in ('interleaved', 'actions-first'):
                result = classify_contract(spec, premise, order)
                self.assertEqual(result['classification'], expected)
                snapshots.append((spec, premise, order, result))
        for spec, premise, order, result in reversed(snapshots):
            self.assertEqual(classify_contract(spec, premise, order), result)

    def test_repeated_roots_compose_once_without_skipping_components(self):
        spec, premise = guarded_spec(4, True)
        spec['registers'] = 64
        calls = []
        original = BDD.compose
        def counted(bdd, root, replacements):
            calls.append((root, tuple(sorted(replacements.items()))))
            return original(bdd, root, replacements)
        with patch.object(BDD, 'compose', counted):
            result = classify_contract(spec, premise)
        self.assertEqual(result['classification'], independent_classification(spec, premise))
        # Blind program: only diagonal composition occurs. All64 registers at
        # each of four decisions remain visible; repeated formulas share results.
        self.assertEqual(len(calls), len(set(calls)))
        self.assertLess(len(calls), 64 * 4)
        self.assertEqual(classify_contract(spec, premise), result)

    def test_caps_and_invalid_premises_remain_distinct(self):
        spec, premise = guarded_spec(3)
        full = classify_contract(spec, premise)
        limit = full['allocated_bdd_nodes']
        self.assertEqual(classify_contract(spec, premise, node_limit=limit), full)
        for cap in (2, limit - 1):
            with self.assertRaisesRegex(ResourceExhausted, '^BDD node budget exceeded$'):
                classify_contract(spec, premise, node_limit=cap)
        for cap in (True, 1, 200001):
            with self.assertRaises(ValueError):
                classify_contract(spec, premise, node_limit=cap)
        bad = copy.deepcopy(premise); bad['rows'][1] = list(bad['rows'][0])
        with self.assertRaisesRegex(ValueError, '^affine map is not bijective$'):
            classify_contract(spec, bad)
        bad = copy.deepcopy(spec); bad['program'][-1] = ['emit', 1]
        with self.assertRaisesRegex(ValueError, '^reference is not constantly zero$'):
            classify_contract(bad, premise)
        bad = copy.deepcopy(spec); bad['program'][-1] = ['emit', 0]
        with self.assertRaisesRegex(ValueError, '^output is not the certified affine equality$'):
            classify_contract(bad, premise)
        visible, p = observed_guarded_spec(3, False, ((0, 0),))
        with self.assertRaisesRegex(ValueError, '^hidden input observed before a choice$'):
            check_obstruction(visible, p)
        self.assertEqual(classify_contract(visible, p)['classification'], 'repairable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
