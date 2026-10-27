"""Bounded draft, judge, and revision product interface."""

from __future__ import annotations

import argparse
import json
import os

from .engine import SelfReflectiveAgent
from .llm import OpenAICompatibleLLM
from .web import serve

WEB_ACTIONS = {
    "reflect": [
        ("task", "Task", "textarea", True),
        ("constraints", "Constraints, one per line", "textarea", False),
        ("must_include", "Required phrases, one per line", "textarea", False),
    ],
    "metrics": [],
}


class _OfflineLLM:
    def complete(self, messages, *, model=None):
        raise RuntimeError("Set OPENAI_API_KEY before reflecting")


def _lines(value):
    return (
        value
        if isinstance(value, list)
        else [line.strip() for line in value.splitlines() if line.strip()]
    )


def execute(
    action: str, values: dict, *, db: str, solver_model: str, judge_model: str
) -> object:
    if action == "reflect":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("Set OPENAI_API_KEY before reflecting")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        solver = OpenAICompatibleLLM(key, base_url, solver_model)
        judge = OpenAICompatibleLLM(key, base_url, judge_model)
    elif action == "metrics":
        solver = judge = _OfflineLLM()
    else:
        raise ValueError("unknown action")
    required = _lines(values.get("must_include", []))

    def validate(_task: str, answer: str, _constraints: list[str]) -> list[str]:
        return [
            f"missing phrase: {term}"
            for term in required
            if term.lower() not in answer.lower()
        ]

    agent = SelfReflectiveAgent(solver, judge, db, validator=validate)
    if action == "metrics":
        return agent.metrics()
    result = agent.run(
        values["task"], constraints=_lines(values.get("constraints", []))
    )
    return {**result.__dict__, "required_phrases": required}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluation-guided agent")
    parser.add_argument("--db", default="evaluations.sqlite3")
    parser.add_argument(
        "--solver-model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    )
    parser.add_argument(
        "--judge-model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    reflect = commands.add_parser("reflect")
    reflect.add_argument("task")
    reflect.add_argument(
        "--constraint", dest="constraints", action="append", default=[]
    )
    reflect.add_argument("--must-include", action="append", default=[])
    commands.add_parser("metrics")
    browser = commands.add_parser("serve")
    browser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(
            "Self Reflective Agent",
            WEB_ACTIONS,
            lambda action, values: execute(
                action,
                values,
                db=args.db,
                solver_model=args.solver_model,
                judge_model=args.judge_model,
            ),
            port=args.port,
        )
    else:
        print(
            json.dumps(
                execute(
                    args.command,
                    vars(args),
                    db=args.db,
                    solver_model=args.solver_model,
                    judge_model=args.judge_model,
                ),
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
