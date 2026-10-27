# Self Reflective Agent

Iteratively evaluate an answer against constraints, revise it, and retain the highest scoring candidate with metrics.

Supply a deterministic `validator(task, answer, constraints)` for rules that must never be left to an LLM judge. Each run records first and best scores so `metrics()` reports measured improvement across runs.

## Quick start

Requires Python 3.11 or newer. From this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
pytest -q
```

For live model calls, set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` and `OPENAI_BASE_URL` as shown in `.env.example`. The test suite uses stubs and needs no model key.

```python
from self_reflective_agent.engine import SelfReflectiveAgent
from self_reflective_agent.llm import OpenAICompatibleLLM

llm = OpenAICompatibleLLM.from_env()
agent = SelfReflectiveAgent(llm, llm, "eval.sqlite3", threshold=0.85, max_revisions=2)
result = agent.run("Write a migration checklist", constraints=["Use no more than five steps"])
print(result.answer, result.history, agent.metrics())
```

## Architecture

Task and constraints -> solver -> JSON judge verdict -> durable metric -> bounded revision -> best answer.

See [ARCHITECTURE.md](ARCHITECTURE.md) for components, state, failure behavior, and operations.

## Deployment and safety

LLM-as-judge scores are subjective and can be gamed. Use a separate judge model and a held out evaluation set before treating score changes as real quality improvement.

Install this as a library in an authenticated application or worker. Supply the LLM adapter through dependency injection. Keep secrets in environment variables, never in source control.

## Verification

`pytest -q` runs deterministic tests. GitHub Actions runs the same suite on pushes and pull requests.

## License

MIT. See [LICENSE](LICENSE).
