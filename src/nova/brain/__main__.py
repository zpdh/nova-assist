"""One-shot CLI: ask the brain one question and print the answer.

python -m nova.brain "what is the capital of France"
"""

from __future__ import annotations

import argparse
import sys

from nova.brain import BrainError, build_brain
from nova.config import Config
from nova.logging_setup import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nova.brain", description="Ask Nova one question.")
    parser.add_argument("question", help="the question to ask")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        config = Config.load()
    except ValueError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    brain = build_brain(config.llm)
    try:
        print(brain.ask(args.question))
    except BrainError as exc:
        print(f"brain error: {exc}", file=sys.stderr)
        return 1
    finally:
        brain.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
