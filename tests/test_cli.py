from self_reflective_agent.__main__ import execute


def test_product_reflects_and_reports_metrics(tmp_path, monkeypatch):
    class FakeLLM:
        def __init__(self, key, base_url, model):
            self.model = model

        def complete(self, messages, *, model=None):
            if self.model == "judge":
                return '{"score":0.9,"feedback":"clear"}'
            return "The next steps are to investigate and report."

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr("self_reflective_agent.__main__.OpenAICompatibleLLM", FakeLLM)
    db = str(tmp_path / "evaluation.sqlite3")
    result = execute(
        "reflect",
        {
            "task": "Summarize",
            "constraints": "Include next steps",
            "must_include": "next steps",
        },
        db=db,
        solver_model="solver",
        judge_model="judge",
    )
    assert result["score"] == 0.9
    assert (
        execute("metrics", {}, db=db, solver_model="solver", judge_model="judge")[
            "runs"
        ]
        == 1
    )
