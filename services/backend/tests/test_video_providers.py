import base64

import pytest
from pydantic import SecretStr

from asa.config import Settings
from asa.video_providers import connection_state, generation_request, task_result


def settings():
    return Settings(
        _env_file=None,
        wan_api_key=SecretStr("test-wan"),
        wan_workspace_id="ws-test",
        video_ai_enabled=True,
    )


def spec(**changes):
    return {
        "prompt": "A fox walks",
        "duration_seconds": 15,
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "audio": False,
        **changes,
    }


def test_wan_request_uses_correct_credentials_and_preserves_prompt():
    cfg = settings()
    model = cfg.video_model_profiles["wan3"].model_dump()
    url, headers, body = generation_request(cfg, model, spec(), b"png")
    assert (
        url
        == "https://ws-test.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    )
    assert headers == {"Authorization": "Bearer test-wan", "X-DashScope-Async": "enable"}
    assert body["model"] == "wan3.0-video"
    assert body["input"] == {
        "prompt": "A fox walks",
        "media": [
            {
                "type": "first_frame",
                "url": "data:image/png;base64," + base64.b64encode(b"png").decode(),
            }
        ],
    }
    assert body["parameters"] == {
        "resolution": "720P",
        "ratio": "9:16",
        "duration": 15,
        "audio": False,
        "prompt_extend": False,
    }


@pytest.mark.parametrize(
    "changes", [{"duration_seconds": 31}, {"resolution": "2K"}, {"aspect_ratio": "5:2"}]
)
def test_reject_unsupported_wan_input_before_call(changes):
    cfg = settings()
    with pytest.raises(ValueError):
        generation_request(
            cfg, cfg.video_model_profiles["wan3"].model_dump(), spec(**changes), b"x"
        )


def test_credentials_and_endpoint_are_independent_and_pinned():
    cfg = settings()
    assert connection_state(cfg, "runway") == "missing_key"
    assert connection_state(cfg, "alibaba") == "configured"
    cfg.wan_workspace_id = ""
    assert connection_state(cfg, "alibaba") == "missing_workspace"
    cfg.wan_workspace_id = "ws-new"
    model = {
        **cfg.video_model_profiles["wan3"].model_dump(),
        "provider_endpoint": "https://ws-old.ap-southeast-1.maas.aliyuncs.com/api/v1",
    }
    with pytest.raises(ValueError, match="endpoint_changed"):
        generation_request(cfg, model, spec(), b"x")


def test_task_status_and_output_are_provider_specific():
    assert task_result(
        "alibaba",
        {"output": {"task_status": "SUCCEEDED", "video_url": "https://example.com/v.mp4"}},
    ) == ("SUCCEEDED", "https://example.com/v.mp4")
    assert task_result("alibaba", {"output": {"task_status": "UNKNOWN"}}) == ("UNKNOWN", None)
    assert task_result(
        "runway", {"status": "SUCCEEDED", "output": ["https://example.com/r.mp4"]}
    ) == ("SUCCEEDED", "https://example.com/r.mp4")
    with pytest.raises(ValueError):
        task_result("alibaba", {"output": {"task_status": "NEW_STATUS"}})


def test_runway_request_unchanged():
    cfg = settings()
    cfg.runway_api_key = SecretStr("test-runway")
    url, headers, body = generation_request(
        cfg, cfg.video_model_profiles["runway-gen45"].model_dump(), spec(duration_seconds=5), b"x"
    )
    assert url.endswith("/image_to_video")
    assert headers["Authorization"] == "Bearer test-runway"
    assert "X-DashScope-Async" not in headers
    assert body["ratio"] == "720:1280"
    assert body["model"] == "gen4.5"
