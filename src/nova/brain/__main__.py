"""One-shot CLI: ask the brain one question and print the answer.

python -m nova.brain "what is the capital of France"
python -m nova.brain --session demo-session "and tomorrow?"
"""

from __future__ import annotations

import argparse
import sys

from nova.brain import BrainError, build_brain
from nova.brain.types import Message
from nova.config import Config
from nova.logging_setup import setup_logging
from nova.store import build_store, open_session


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="nova.brain", description="Ask Nova one question.")
    parser.add_argument("question", help="the question to ask")
    parser.add_argument(
        "--session",
        metavar="ID",
        help="persist the turn in this session and load its history (creates it if new)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    setup_logging()
    try:
        config = Config.load()
    except ValueError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    brain = build_brain(config.llm)
    try:
        if args.session is None:
            messages = [
                Message(role="system", content=config.brain.system_prompt),
                Message(role="user", content=args.question),
            ]
            print(brain.chat(messages).text)
        else:
            store = build_store(config.store)
            try:
                session = open_session(store, brain, config.brain.system_prompt, args.session)
                print(session.ask(args.question))
            finally:
                store.close()
    except BrainError as exc:
        print(f"brain error: {exc}", file=sys.stderr)
        return 1
    finally:
        brain.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
