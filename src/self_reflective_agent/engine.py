from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .llm import LLM


@dataclass(frozen=True)
class ReflectionResult:
    answer: str
    score: float
    iterations: int
    history: tuple[float, ...]
    improvement: float


class SelfReflectiveAgent:
    def __init__(
        self,
        solver: LLM,
        judge: LLM,
        db_path: str | Path,
        *,
        threshold: float = 0.85,
        max_revisions: int = 2,
        validator: Callable[[str, str, list[str]], list[str]] | None = None,
    ):
        self.solver, self.judge, self.db_path = solver, judge, str(db_path)
        self.threshold, self.max_revisions = threshold, max_revisions
        self.validator = validator
        if not 0 <= threshold <= 1 or max_revisions < 0:
            raise ValueError("invalid evaluation settings")
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY, task TEXT, revision INTEGER, score REAL, feedback TEXT, created_at REAL)"
            )
            if "run_id" not in {
                row[1] for row in db.execute("PRAGMA table_info(evaluations)")
            }:
                db.execute("ALTER TABLE evaluations ADD COLUMN run_id TEXT")

    def _db(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def run(self, task: str, *, constraints: list[str]) -> ReflectionResult:
        answer = self.solver.complete(
            [
                {
                    "role": "system",
                    "content": "Solve the task within these constraints: "
                    + json.dumps(constraints),
                },
                {"role": "user", "content": task},
            ]
        )
        run_id = uuid.uuid4().hex
        history: list[float] = []
        best_answer, best_score = answer, -1.0
        for revision in range(self.max_revisions + 1):
            raw = self.judge.complete(
                [
                    {
                        "role": "system",
                        "content": 'Evaluate against the task and constraints. Return JSON: {"score":number between 0 and 1,"feedback":string}. Be critical and specific.',
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"task": task, "constraints": constraints, "answer": answer}
                        ),
                    },
                ]
            )
            try:
                verdict = json.loads(raw)
                score = float(verdict["score"])
                feedback = str(verdict["feedback"])
                if not 0 <= score <= 1:
                    raise ValueError("score outside range")
            except (ValueError, KeyError, TypeError):
                score, feedback = 0.0, "Judge returned an invalid evaluation."
            if self.validator:
                violations = self.validator(task, answer, constraints)
                if violations:
                    score = 0.0
                    feedback += " Deterministic constraint violations: " + "; ".join(
                        violations
                    )
            history.append(score)
            with self._db() as db:
                db.execute(
                    "INSERT INTO evaluations(task,revision,score,feedback,created_at,run_id) VALUES(?,?,?,?,?,?)",
                    (task, revision, score, feedback, time.time(), run_id),
                )
            if score > best_score:
                best_answer, best_score = answer, score
            if score >= self.threshold or revision == self.max_revisions:
                break
            answer = self.solver.complete(
                [
                    {
                        "role": "system",
                        "content": "Revise the answer using specific feedback while respecting constraints.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "task": task,
                                "constraints": constraints,
                                "previous_answer": answer,
                                "feedback": feedback,
                            }
                        ),
                    },
                ]
            )
        return ReflectionResult(
            best_answer,
            best_score,
            len(history),
            tuple(history),
            best_score - history[0],
        )

    def metrics(self) -> dict[str, float]:
        with self._db() as db:
            count, mean = db.execute(
                "SELECT count(*),avg(score) FROM evaluations"
            ).fetchone()
            rows = db.execute(
                "SELECT run_id,revision,score FROM evaluations WHERE run_id IS NOT NULL ORDER BY id"
            ).fetchall()
        runs: dict[str, list[tuple[int, float]]] = {}
        for run_id, revision, score in rows:
            runs.setdefault(run_id, []).append((revision, score))
        gains = [
            max(score for _, score in values) - values[0][1] for values in runs.values()
        ]
        return {
            "evaluations": count,
            "mean_score": mean or 0.0,
            "runs": len(runs),
            "mean_improvement": sum(gains) / len(gains) if gains else 0.0,
        }
