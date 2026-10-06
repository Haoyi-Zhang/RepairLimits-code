"""Bounded regressions for complete, sequential deletion partitioning."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from repair import campaign


class SlicedCampaignTests(unittest.TestCase):
    def test_deletion_partition_matches_unsliced(self):
        expected=campaign.guarded_deletions(2,0,4)
        actual=campaign.guarded_deletions(2,0,2)+campaign.guarded_deletions(2,2,4)
        self.assertEqual(expected,actual)
        self.assertEqual(len({r['removed'] for r in actual}),4)

    def test_invalid_bounds_rejected(self):
        for begin,end in [(-1,1),(0,0),(0,5),(3,2)]:
            with self.subTest(begin=begin,end=end),self.assertRaises(ValueError):
                campaign.guarded_deletions(2,begin,end)

    def test_child_failure_propagates(self):
        failed=type('Child',(),{'returncode':9,'stderr':'bounded test','stdout':''})()
        with patch.object(campaign.subprocess,'run',return_value=failed):
            with self.assertRaisesRegex(RuntimeError,'exit 9'):
                campaign.guarded_sliced(8)

    def test_sliced_complete_small_case(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)
            original=campaign.write_json
            with patch.object(campaign,'write_json',
                              side_effect=lambda p,d:original(target/p,d)):
                expected=campaign.run_guarded(2)
            # Run the same reviewed computations through a mock child transport;
            # actual POSIX process limits are exercised by the complete workflow.
            def child(command,**kwargs):
                index=int(command[5]);kind=command[7]
                begin=int(command[9]);end=int(command[11])
                with patch.object(campaign,'write_json',
                                  side_effect=lambda p,d:original(target/p,d)):
                    result=(campaign.guarded_base(index) if kind=='base' else
                            campaign.guarded_deletions(index,begin,end))
                payload={'chunk':index,'part':kind,'begin':begin,'end':end,
                         'results':result,'cpu_seconds':0,'wall_seconds':0,'peak_rss_kib':1}
                return type('Child',(),{'returncode':0,'stderr':'',
                             'stdout':campaign.json.dumps(payload)})()
            with patch.object(campaign.subprocess,'run',side_effect=child):
                actual,parts=campaign.guarded_sliced(2)
            for row in expected+actual: row.pop('cpu_seconds')
            self.assertEqual(expected,actual)
            self.assertEqual([p['part'] for p in parts],['base','deletions'])
