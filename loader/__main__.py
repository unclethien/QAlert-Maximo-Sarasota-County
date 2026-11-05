"""Command line: python -m loader <command>.

  inventory   read-only report of what the instance already holds (never writes)
  provision   create the org, site, persons, teams, statuses, classifications and job plans
              the load needs (dry run unless --apply)
  load        load SRs, WOs and work logs, then set statuses (dry run unless --apply)
  verify      read the loaded records back and compare them with the dataset (never writes)
"""

import argparse
import sys

from .client import MaximoClient, MaximoError
from .config import Settings, load_settings
from .load import COMMODITY_COLUMNS, FAILURE_CODE_COLUMNS
from .provision import STEPS


def make_client(settings: Settings | None = None) -> MaximoClient:
    settings = settings or load_settings()
    if not settings.verify_tls:
        print("WARNING: TLS certificate verification is off (MAXIMO_VERIFY_TLS=false).", file=sys.stderr)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return MaximoClient(settings.url, settings.api_key, settings.api_path, verify_tls=settings.verify_tls)


def _steps(value: str) -> list[str]:
    steps = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in steps if v not in STEPS]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown step(s): {', '.join(unknown)}")
    return steps


def cmd_inventory(args: argparse.Namespace) -> int:
    from .inventory import run_inventory, save_report, summarize

    report = run_inventory(make_client())
    print(summarize(report))
    print(f"\nReport saved to {save_report(report)}")
    return 1 if report["identity"]["status"] == "error" else 0


def cmd_provision(args: argparse.Namespace) -> int:
    from .provision import Provisioner

    settings = load_settings()
    return Provisioner(make_client(settings), settings, apply=args.apply).run(args.only)


def _ids(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _drop(args: argparse.Namespace) -> list[str]:
    return ([] if args.keep_failure_codes else list(FAILURE_CODE_COLUMNS)) + \
        ([] if args.keep_commodities else list(COMMODITY_COLUMNS))


def cmd_load(args: argparse.Namespace) -> int:
    from .load import Loader
    from .manifest import Manifest

    settings = load_settings()
    return Loader(make_client(settings), Manifest(instance=settings.url), apply=args.apply,
                  drop=_drop(args)).run(args.only, args.limit)


def cmd_verify(args: argparse.Namespace) -> int:
    from .manifest import Manifest
    from .verify import Verifier

    settings = load_settings()
    return Verifier(make_client(settings), Manifest(instance=settings.url, persist=False),
                    drop=_drop(args)).run(args.only, args.limit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m loader", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory", help="read-only report of what the instance already holds").set_defaults(
        func=cmd_inventory)
    prov = sub.add_parser("provision", help="create the setup records (dry run unless --apply)")
    prov.add_argument("--apply", action="store_true", help="write to Maximo; without it nothing is written")
    prov.add_argument("--only", type=_steps, help=f"comma-separated steps: {','.join(STEPS)}")
    prov.set_defaults(func=cmd_provision)
    for name, func, text in (("load", cmd_load, "load SRs, WOs and work logs (dry run unless --apply)"),
                             ("verify", cmd_verify, "read loaded records back and compare (never writes)")):
        p = sub.add_parser(name, help=text)
        if name == "load":
            p.add_argument("--apply", action="store_true", help="write to Maximo; without it nothing is written")
        p.add_argument("--only", type=_ids, help="comma-separated TICKETIDs or WONUMs; each brings its whole chain")
        p.add_argument("--limit", type=int, help="only the first N chains (an SR with its WOs, or a lone WO)")
        p.add_argument("--keep-failure-codes", action="store_true",
                       help="send FAILURECODE and PROBLEMCODE (only once they exist in Maximo)")
        p.add_argument("--keep-commodities", action="store_true",
                       help="send COMMODITYGROUP and COMMODITY (only once the service groups exist in Maximo)")
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MaximoError as e:
        print(f"Maximo error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
