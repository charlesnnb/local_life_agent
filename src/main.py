"""CLI entry point.

Usage:
    python src/main.py "今天下午想带老婆孩子出去玩几个小时，别太远，孩子5岁，老婆最近在减肥"
"""

import argparse
import json
from pathlib import Path
import sys


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.planner_agent import PlannerAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local activity plan.")
    parser.add_argument("query", help="Natural-language planning request")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only print the structured JSON response",
    )
    args = parser.parse_args()

    result = PlannerAgent().plan(args.query)
    if not args.json_only:
        print(result.natural_language)
        print("\n结构化结果：")
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
