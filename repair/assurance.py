"""Run the finite assurance suite with bounded resources and a result record."""
import json,resource,time,unittest
from pathlib import Path
from .campaign import write_json

def main():
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))
    cpu,wall=time.process_time(),time.monotonic()
    suite=unittest.defaultTestLoader.discover('tests')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    data={'tests':result.testsRun,'successful':result.wasSuccessful(),
          'failures':[(str(t),reason) for t,reason in result.failures],
          'errors':[(str(t),reason) for t,reason in result.errors],
          'skipped':[(str(t),reason) for t,reason in result.skipped],
          'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,
          'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    write_json('results/assurance.json',data)
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
