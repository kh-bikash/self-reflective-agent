from self_reflective_agent.engine import SelfReflectiveAgent


class Stub:
    def __init__(self, replies):
        self.replies = iter(replies)

    def complete(self, messages, *, model=None):
        return next(self.replies)


def test_improves_and_logs(tmp_path):
    agent = SelfReflectiveAgent(Stub(["first", "revised"]), Stub(['{"score":0.2,"feedback":"missing detail"}', '{"score":0.9,"feedback":"good"}']), tmp_path / "eval.db")
    result = agent.run("Explain", constraints=["concise"])
    assert result.answer == "revised" and result.history == (0.2, 0.9)
    assert agent.metrics()["evaluations"] == 2
    assert agent.metrics()["mean_improvement"] == 0.7


def test_deterministic_constraint_overrides_judge(tmp_path):
    agent = SelfReflectiveAgent(Stub(["too long", "short"]), Stub(['{"score":1,"feedback":"good"}', '{"score":0.9,"feedback":"good"}']),
                                tmp_path / "eval.db", validator=lambda task, answer, constraints: ["too long"] if len(answer) > 5 else [])
    result = agent.run("Write briefly", constraints=["five chars or fewer"])
    assert result.answer == "short" and result.history == (0.0, 0.9)
