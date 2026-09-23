"""Command-line interface for Dossier."""

from __future__ import annotations

import argparse
import json
import sys

from .agent import DossierAgent, DossierError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dossier",
        description="Research a question with live sources and fact-checking safeguards.",
    )
    parser.add_argument("question", nargs="+", help="Question or claim to research")
    parser.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="Output format (default: human)",
    )
    parser.add_argument(
        "--depth",
        choices=("surface", "deep", "phd", "soul_shattering"),
        default="deep",
        help="Depth of research (surface, deep, phd, soul_shattering; default: deep)",
    )
    parser.add_argument("--model", help="OpenAI model; defaults to DOSSIER_MODEL or gpt-5.5")
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable live web search; useful for offline tests",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        agent = DossierAgent(model=args.model, live_web=not args.no_web)
        result = agent.research(" ".join(args.question), output_format=args.format, depth=args.depth)
        if args.format == "json":
            print(json.dumps(result.as_json(), ensure_ascii=False, separators=(",", ":")))
        else:
            print(result.text)
    except (DossierError, ValueError) as exc:
        print(f"dossier: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
