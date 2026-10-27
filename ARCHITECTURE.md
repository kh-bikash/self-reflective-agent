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
3. Persist SQLite files on durable storage and back them up; migrate to a managed database for high write volume or multiple replicas.
4. Run `pytest -q` in CI before deployment.
5. Define workload specific evaluation cases, latency objectives, and rollback criteria before serving real users.
