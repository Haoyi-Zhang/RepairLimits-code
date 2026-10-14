"""Finite resource/admission controls; no resource-controller impersonation."""
import copy
import unittest
from unittest.mock import patch
from repair.cases import chain, mechanism_cases
from repair.check import check_certificate, policy_replay
from repair.errors import ResourceExhausted
from repair.solve import synthesize
from repair.value_only import solve_value, replay_value_policy


class BudgetAdmissionTests(unittest.TestCase):
    def test_smaller_storage_quota_is_unknown(self):
        case = chain(2, budget=0)
        certificate = synthesize(case)
        count = len(certificate['nodes'])
        with self.assertRaisesRegex(ResourceExhausted, 'storage budget'):
            check_certificate(case, certificate, max_nodes=count - 1)
        self.assertEqual(check_certificate(case, certificate, max_nodes=count)['value'], 2)
        self.assertFalse(check_certificate(case, certificate)['feasible'])

    def test_malformed_and_boolean_fields_still_rejected(self):
        case = chain(2)
        good = synthesize(case)
        for nodes in ({}, [], {str(i): {} for i in range(200001)}):
            bad = copy.deepcopy(good)
            bad['nodes'] = nodes
            with self.assertRaises(ValueError):
                check_certificate(case, bad)
        for quota in (True, False, 0, 200001):
            with self.assertRaises(ValueError):
                check_certificate(case, good, max_nodes=quota)
        bad = copy.deepcopy(good)
        bad['value'] = True
        with self.assertRaises(ValueError):
            check_certificate(case, bad)

    def test_no_certificate_control_same_information(self):
        for case in [chain(3, k) for k in range(4)] + list(mechanism_cases()):
            with self.subTest(case=case['id']):
                certificate = synthesize(case)
                expected = check_certificate(case, certificate)['value']
                solution = solve_value(case)
                self.assertEqual((solution.value, solution.states),
                                 (expected, len(certificate['nodes'])))
                self.assertEqual(replay_value_policy(case, solution),
                                 policy_replay(case, certificate))

    def test_value_control_caps_reference_and_correlation(self):
        case = chain(2, words=[(0, 0), (1, 1)])
        self.assertEqual(solve_value(case).value, 1)
        with self.assertRaises(ResourceExhausted):
            solve_value(case, state_limit=1)
        for cap in (True, 0, 200001):
            with self.assertRaises(ValueError):
                solve_value(case, state_limit=cap)
        case['program'][0] = ['load', 0, 2]
        with self.assertRaises(ValueError):
            solve_value(case)

    def test_oracle_comparison_not_disabled_by_optimization(self):
        # Exercise the existing differential helper under both Python modes.
        from test_assurance import complete
        with patch('test_assurance.exact_oracle', return_value={'value': 99}):
            with self.assertRaisesRegex(AssertionError, 'oracle disagreement'):
                complete(chain(1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
