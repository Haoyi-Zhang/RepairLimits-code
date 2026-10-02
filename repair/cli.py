"""Bounded command-line interface. Outputs never derive paths from case identifiers."""
from __future__ import annotations
import argparse, json, resource, sys
from pathlib import Path
from .check import strict_json, check_certificate, policy_replay
from .errors import ResourceExhausted
from .model import validate
from .solve import synthesize, extract_core
from .oracle import exact_oracle
from .symbolic import classify_contract


REJECTED = (ValueError,TypeError,KeyError,IndexError,UnicodeError,OSError)


def load(path: str):
    p=Path(path)
    if p.stat().st_size > 32*1024*1024:
        raise ValueError('input file exceeds 32 MiB limit')
    return strict_json(p.read_text(encoding='utf-8'))


def report(status: str, stage: str, error: BaseException, code: int) -> int:
    print(json.dumps({'status':status,'stage':stage,'reason':str(error)},sort_keys=True),file=sys.stderr)
    return code


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('solve','oracle','core'):
        p=sub.add_parser(name);p.add_argument('case')
    p=sub.add_parser('check');p.add_argument('case');p.add_argument('certificate')
    p=sub.add_parser('symbolic');p.add_argument('input');p.add_argument('--order',choices=('interleaved','actions-first'),default='interleaved')
    args=parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(40,40))

    # Keep parsing/schema rejection separate from bounded semantic execution.
    # In particular, a valid search that reaches Python's stack limit or one of
    # the declared algorithmic caps is unknown, not a malformed input.
    try:
        if args.command=='symbolic':
            data=load(args.input)
            if type(data) is not dict or set(data)!={'specification','premise'}:
                raise ValueError('symbolic input fields')
            prepared=data
        else:
            c=load(args.case);validate(c)
            prepared=(c,load(args.certificate)) if args.command=='check' else c
    except MemoryError as error:
        return report('unknown-resource','input-loading',error,3)
    except RecursionError as error:
        return report('rejected','input-validation',error,2)
    except REJECTED as error:
        return report('rejected','input-validation',error,2)

    try:
        if args.command=='symbolic':
            result=classify_contract(prepared['specification'],prepared['premise'],order=args.order)
        elif args.command=='solve': result=synthesize(prepared)
        elif args.command=='oracle': result=exact_oracle(prepared)
        elif args.command=='core':
            result={'kind':'inclusion-minimal-not-minimum','worlds':extract_core(prepared,prepared['budget'])}
        else:
            c,cert=prepared
            result={'check':check_certificate(c,cert),'replay':policy_replay(c,cert)}
    except (ResourceExhausted,MemoryError,RecursionError) as error:
        return report('unknown-resource','semantic-search',error,3)
    except REJECTED as error:
        return report('rejected','semantic-validation',error,2)

    print(json.dumps(result,sort_keys=True,separators=(',',':')))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
