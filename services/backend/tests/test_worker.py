import json
from contextlib import nullcontext
from uuid import UUID

import pytest
from langsmith.utils import tracing_is_enabled

from asa import worker


def test_worker_disables_inherited_remote_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")

    monkeypatch.setenv("ASA_DATABASE_URL", "postgresql://unused")
    monkeypatch.setattr("sys.argv", [
        "asa.worker", "draft", "--prompt", "고양이", "--allow-paid-call"
    ])
    monkeypatch.setattr(worker.PostgresSaver, "from_conn_string", lambda _: nullcontext(object()))

    class InspectingGraph:
        def invoke(self, *args):
            assert not tracing_is_enabled()
            return {"status": "waiting_approval"}

    monkeypatch.setattr(worker, "build_graph", lambda *args: InspectingGraph())
    assert worker.main() == 0


def test_draft_prints_run_id_before_a_failure(monkeypatch, capsys):
    monkeypatch.setenv("ASA_DATABASE_URL", "postgresql://unused")
    monkeypatch.setattr("sys.argv", [
        "asa.worker", "draft", "--prompt", "고양이", "--allow-paid-call"
    ])
    monkeypatch.setattr(worker.PostgresSaver, "from_conn_string", lambda _: nullcontext(object()))

    class FailingGraph:
        def invoke(self, *args):
            raise RuntimeError("external outcome unknown")

    monkeypatch.setattr(worker, "build_graph", lambda *args: FailingGraph())
    with pytest.raises(RuntimeError):
        worker.main()
    output = capsys.readouterr().out
    assert output, "run ID must be available even when generation fails"
    event = json.loads(output.splitlines()[0])
    assert event["status"] == "starting"
    assert str(UUID(event["run_id"])) == event["run_id"]
