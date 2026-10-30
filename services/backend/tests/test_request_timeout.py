import httpx
import pytest

from asa.registry.script_stage import execute_attempt, is_timeout


def test_timeout_classification():
    assert is_timeout(TimeoutError())
    assert is_timeout(httpx.ReadTimeout("private message must not be stored"))
    assert not is_timeout(ValueError("timeout mentioned in output"))
    outer = RuntimeError()
    outer.__cause__ = httpx.ConnectTimeout("connection")
    assert is_timeout(outer)


@pytest.mark.parametrize("error,code", [(TimeoutError(), "ai_timeout"), (ValueError(), None)])
def test_execute_records_uncertain_result_without_retry(error, code):
    class Repository:
        finished = []

        def claim(self, *args):
            return {"id": "attempt", "prompt": "{}"}

        def finish(self, request_id, attempt, result):
            self.finished.append((attempt.get("error_code"), result))

    calls = []

    def generate(prompt):
        calls.append(prompt)
        raise error

    repo = Repository()
    assert execute_attempt(repo, "request", "attempt", generate)
    assert calls == ["{}"]
    assert repo.finished == [(code, None)]
