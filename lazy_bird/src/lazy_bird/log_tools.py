from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence

from lazy_bird.log_parser import LogParseError
from lazy_bird.log_render import color_enabled, entry_to_dict, json_output, render_search_results
from lazy_bird.log_search import LogSearchError, search_logs
from lazy_bird.log_tree import node_to_dict, render_call_tree, render_raw_tree, trace_call_trees, trace_function_calls


def parse_date_argument(value: str, *, until: bool = False) -> datetime:
    """Parse ISO dates/timestamps and relative durations such as ``15m``."""
    relative = re.fullmatch(r"(?P<amount>\d+(?:\.\d+)?)(?P<unit>[mhd])", value.strip().lower())
    if relative:
        amount = float(relative.group("amount"))
        unit = {"m": "minutes", "h": "hours", "d": "days"}[relative.group("unit")]
        return datetime.now() - timedelta(**{unit: amount})
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed_date = date.fromisoformat(value)
            return datetime.combine(parsed_date, time.max if until else time.min)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Date invalide: {value}. Utilisez ISO 8601 ou 15m/2h/1d.") from exc


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--since", type=lambda value: parse_date_argument(value), help="Date ISO ou durée relative (ex. 15m).")
    parser.add_argument("--until", type=lambda value: parse_date_argument(value, until=True), help="Borne de date incluse.")
    parser.add_argument("--last-n", type=int, help="Conserver les N résultats les plus récents.")
    parser.add_argument("--log-file", type=Path, default=Path("logs.txt"), help="Fichier de logs (défaut: logs.txt).")
    parser.add_argument("--json", action="store_true", help="Sortie JSON stable pour un agent.")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto", help="Couleur: auto, always ou never.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m lazy_bird.log_tools", description="Recherche dans logs.txt et reconstruction d'arbres d'appels.")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Rechercher des entrées de log.", epilog="Exemple: search createAPIKey --mode bm25 --last-n 5")
    search.add_argument("query", nargs="?", help="Texte ou expression régulière.")
    search.add_argument("--mode", choices=("bm25", "regex"), default="bm25")
    search.add_argument("--case-sensitive", dest="ignore_case", action="store_false")
    search.add_argument("--ignore-case", dest="ignore_case", action="store_true", default=True)
    _add_common_options(search)
    trace = commands.add_parser("trace", help="Afficher le sous-arbre d'une fonction.", epilog="Exemple: trace create_api_key --module lazy_bird.api.endpoints.api_key")
    trace.add_argument("function_name", help="Nom exact de la fonction.")
    trace.add_argument("--module", dest="module_name", help="Module exact (optionnel).")
    trace.add_argument("--raw", action="store_true", help="Afficher les lignes brutes numérotées.")
    _add_common_options(trace)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "search":
            entries = search_logs(args.query, since=args.since, until=args.until, last_n=args.last_n, mode=args.mode, ignore_case=args.ignore_case, log_file=args.log_file)
            if not entries:
                if args.json:
                    print(json_output("search", []))
                return 1
            if args.json:
                print(json_output("search", [entry_to_dict(entry) for entry in entries]))
            else:
                print(render_search_results(entries, query=args.query, color=color_enabled(args.color)))
            return 0
        nodes = trace_call_trees(args.function_name, args.module_name, since=args.since, until=args.until, last_n=args.last_n, log_file=args.log_file)
        if not nodes:
            message = f"Aucune correspondance pour {args.function_name}."
            print(json_output("trace", [], error=message) if args.json else message)
            return 1
        if args.json:
            print(json_output("trace", [node_to_dict(node) for node in nodes]))
        elif args.raw:
            print(render_raw_tree(nodes, color=color_enabled(args.color)))
        else:
            print(render_call_tree(nodes, color=color_enabled(args.color)))
        return 0
    except LogParseError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (LogSearchError, argparse.ArgumentTypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())