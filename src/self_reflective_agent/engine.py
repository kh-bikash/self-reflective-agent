from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .llm import LLM


@dataclass(frozen=True)
class ReflectionResult:
    answer: str
    score: float
    iterations: int
    history: tuple[float, ...]


class SelfReflectiveAgent:
    def __init__(self, solver: LLM, judge: LLM, db_path: str | Path, *, threshold: float = 0.85, max_revisions: int = 2):
        self.solver, self.judge, self.db_path = solver, judge, str(db_path)
        self.threshold, self.max_revisions = threshold, max_revisions
        if not 0 <= threshold <= 1 or max_revisions < 0:
            raise ValueError("invalid evaluation settings")
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY, task TEXT, revision INTEGER, score REAL, feedback TEXT, created_at REAL)")

    def _db(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def run(self, task: str, *, constraints: list[str]) -> ReflectionResult:
        answer = self.solver.complete([{"role": "system", "content": "Solve the task within these constraints: " + json.dumps(constraints)}, {"role": "user", "content": task}])
        history: list[float] = []
        best_answer, best_score = answer, -1.0
        for revision in range(self.max_revisions + 1):
            raw = self.judge.complete([{"role": "system", "content": "Evaluate against the task and constraints. Return JSON: {\"score\":number between 0 and 1,\"feedback\":string}. Be critical and specific."}, {"role": "user", "content": json.dumps({"task": task, "constraints": constraints, "answer": answer})}])
            try:
                verdict = json.loads(raw)
                score = float(verdict["score"])
                feedback = str(verdict["feedback"])
                if not 0 <= score <= 1:
                    raise ValueError("score outside range")
            except (ValueError, KeyError, TypeError):
                score, feedback = 0.0, "Judge returned an invalid evaluation."
            history.append(score)
            with self._db() as db:
                db.execute("INSERT INTO evaluations(task,revision,score,feedback,created_at) VALUES(?,?,?,?,?)", (task, revision, score, feedback, time.time()))
            if score > best_score:
                best_answer, best_score = answer, score
            if score >= self.threshold or revision == self.max_revisions:
                break
            answer = self.solver.complete([{"role": "system", "content": "Revise the answer using specific feedback while respecting constraints."}, {"role": "user", "content": json.dumps({"task": task, "constraints": constraints, "previous_answer": answer, "feedback": feedback})}])
        return ReflectionResult(best_answer, best_score, len(history), tuple(history))

    def metrics(self) -> dict[str, float]:
        with self._db() as db:
            count, mean = db.execute("SELECT count(*),avg(score) FROM evaluations").fetchone()
        return {"evaluations": count, "mean_score": mean or 0.0}
