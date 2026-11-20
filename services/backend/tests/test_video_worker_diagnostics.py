from contextlib import nullcontext
from io import BytesIO
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from asa import video_worker
from asa.config import Settings


class Connection:
    def __init__(self, status):
        self.row = {"id": uuid4(), "status": status, "model_snapshot": {"provider": "alibaba"},
                    "generation_input": {"start_image_id": str(uuid4())}, "provider_task": "task-1"}
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        if "character_image_jobs" in self.calls[-1][0]:
            image = BytesIO()
            Image.new("RGB", (240, 240)).save(image, format="PNG")
            return {"image": image.getvalue()}
        return self.row

    def transaction(self):
        return nullcontext()


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(video_worker, "provider_connection", lambda *a: ("https://example.com", {}))
    monkeypatch.setattr(video_worker, "generation_request",
                        lambda *a: ("https://example.com/submit", {}, {}))
    monkeypatch.setattr(video_worker, "lock_policy", lambda *a: None)
    monkeypatch.setattr(video_worker, "policy", lambda *a: {})
    monkeypatch.setattr(video_worker, "allowed", lambda *a: True)
    monkeypatch.setattr(video_worker, "accepting_work", lambda *a: True)
    return Settings(_env_file=None), uuid4()


@pytest.mark.parametrize("status,expected", [(401, "failed"), (408, "unknown"), (500, "unknown")])
def test_submission_failure_is_safe_and_never_retried(setup, status, expected):
    cfg, workspace = setup
    conn = Connection("queued")
    requests = []

    def respond(request):
        requests.append(request.method)
        return httpx.Response(status, json={"code": "InvalidApiKey", "request_id": "req-1",
                                           "message": "secret prompt Bearer test-secret"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert video_worker.process(conn, client, workspace, cfg)
    update = conn.calls[-1][1]
    assert update[0] == expected
    assert update[2].obj == {"stage": "submitting", "category": "http_status",
                             "http_status": status, "provider_code": "InvalidApiKey",
                             "request_id": "req-1"}
    assert requests == ["POST"]
    assert "secret" not in repr(conn.calls)


def test_poll_timeout_records_failure_without_resubmission(setup):
    cfg, workspace = setup
    conn = Connection("running")
    requests = []

    def respond(request):
        requests.append(request.method)
        raise httpx.ReadTimeout("secret signed-url", request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        video_worker.process(conn, client, workspace, cfg)
    assert requests == ["GET"]
    assert conn.calls[-1][1][0] == "poll_failed"
    assert conn.calls[-1][1][1].obj == {"stage": "polling", "category": "timeout"}
    assert "status=" not in conn.calls[-1][0]
    assert "secret" not in repr(conn.calls)


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "FAILED"])
def test_poll_persists_provider_stage_and_failure_code(setup, status):
    cfg, workspace = setup
    conn = Connection("running")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"request_id": "req-2", "output": {"task_status": status,
                    "code": "ContentRejected", "message": "private prompt"}}))) as client:
        video_worker.process(conn, client, workspace, cfg)
    progress = next(params for sql, params in conn.calls if "provider_status=%s" in sql)
    expected_stage = "provider_running" if status == "RUNNING" else "provider_pending"
    assert progress[:2] == (status, expected_stage)
    if status == "FAILED":
        assert conn.calls[-1][1][0].obj["provider_code"] == "ContentRejected"
    assert "private" not in repr(conn.calls)


@pytest.mark.parametrize("value", ["Bearer secret", "sk-secret", "https://signed", "x" * 129,
                                    {"nested": "secret"}, "prompt with spaces"])
def test_diagnostics_rejects_unsafe_identifiers(value):
    result = video_worker.safe_diagnostics("polling", response=httpx.Response(
        400, json={"code": value, "request_id": value, "message": "secret"}))
    assert result == {"stage": "polling", "category": "provider_failure", "http_status": 400}


def test_download_failure_reports_download_stage_and_reconciles_same_task(setup, monkeypatch):
    cfg, workspace = setup
    conn = Connection("running")
    requests = []

    def respond(request):
        requests.append(request.method)
        return httpx.Response(200, json={"output": {"task_status": "SUCCEEDED",
                                                    "video_url": "https://example.com/signed"}})

    def download(url):
        raise httpx.ConnectError("secret URL")

    monkeypatch.setattr(video_worker, "fetch_video", download)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        video_worker.process(conn, client, workspace, cfg)
        assert conn.calls[-1][1][0] == "download_failed"
        assert conn.calls[-1][1][1].obj == {"stage": "downloading", "category": "transport"}
        monkeypatch.setattr(video_worker, "fetch_video", lambda url: b"video")
        video_worker.process(conn, client, workspace, cfg)
    assert requests == ["GET", "GET"]
    assert "status='review'" in conn.calls[-1][0]
    assert "secret" not in repr(conn.calls)


def test_invalid_submission_json_remains_unknown(setup):
    cfg, workspace = setup
    conn = Connection("queued")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, text="private invalid response"))) as client:
        video_worker.process(conn, client, workspace, cfg)
    assert conn.calls[-1][1][:2] == ("unknown", "submission_uncertain")
    assert conn.calls[-1][1][2].obj == {"stage": "submitting", "category": "invalid_response",
                                      "http_status": 200}
    assert "private" not in repr(conn.calls)
