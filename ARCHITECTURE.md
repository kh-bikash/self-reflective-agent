# Architecture

## Goal

Iteratively evaluate an answer against constraints, revise it, and retain the highest scoring candidate with metrics.

## Request path

Task and constraints -> solver -> JSON judge verdict -> durable metric -> bounded revision -> best answer.

## Components

- `src/self_reflective_agent/engine.py`: policy and state transitions for this project.
- `src/self_reflective_agent/llm.py`: injected model protocol and HTTPS OpenAI-compatible adapter with timeouts and retry for transient transport failures.
- `tests/test_engine.py`: deterministic behavior and failure tests.
- `.github/workflows/ci.yml`: install and test gate.


## State and failure behavior

LLM-as-judge scores are subjective and can be gamed. Use a separate judge model and a held out evaluation set before treating score changes as real quality improvement.

The LLM adapter times out after 30 seconds and retries transient HTTP failures twice. Model output is untrusted input and is parsed or validated at the project boundary.

## Operations checklist

1. Set secrets through a secret manager and rotate them regularly.
2. Put the service or integrating application behind TLS and authentication.
3. Persist and back up the SQLite evaluation ledger. Keep a separate held out evaluation set outside this run history.
4. Run `pytest -q` in CI before deployment.
5. Define workload specific evaluation cases, latency objectives, and rollback criteria before serving real users.

## Evaluation loop

The solver drafts a response to the task and constraints. A separate judge prompt must return JSON with a 0..1 score and specific feedback. An optional deterministic validator checks hard constraints and overrides the score to zero on violations. Scores, feedback, revision number, and run ID are persisted in SQLite. The solver sees the feedback for a bounded number of revisions; the returned answer is the best scored candidate, so a worse revision does not replace it.

`metrics()` reports evaluation count, mean score, run count, and mean best-over-first improvement. Treat those as internal diagnostics. A held out task set, independent graders, and human review are needed before claiming real quality gains. Invalid judge output scores zero and triggers a bounded revision.

## Product interfaces and trust boundary

The installed console command and local browser call the same product operation in `src/*/__main__.py`; the browser does not replace the engine's validation or state transitions. `src/*/web.py` serves HTML and a JSON action endpoint with a one-megabyte request limit and a per-process CSRF token. It binds to loopback by default. A non-loopback bind requires `AGENT_WEB_TOKEN` of at least 16 characters, checked on every action request. The page never embeds the access token; an operator enters it in the browser. Treat the browser as an operator interface and place TLS plus identity-aware access control in front of any public endpoint. The non-root container is described in `DEPLOYMENT.md`.
