from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from asa.models import Script
from asa.workflow import build_graph


@pytest.mark.parametrize("approved, expected", [(True, "approved"), (False, "rejected")])
def test_waits_for_review_and_resumes_without_regenerating(approved, expected):
    calls = []

    def generate(prompt):
        calls.append(prompt)
        return Script(title="우주 고양이", narration="고양이가 달에 도착했습니다.")

    graph = build_graph(generate, InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = graph.invoke({"prompt": "고양이의 우주여행"}, config)
    assert result["__interrupt__"]
    assert result["status"] == "waiting_approval"
    result = graph.invoke(Command(resume={"approved": approved}), config)
    assert result["status"] == expected
    assert calls == ["고양이의 우주여행"]


def test_invalid_approval_is_not_silently_accepted():
    graph = build_graph(lambda _: Script(title="제목", narration="본문"), InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    graph.invoke({"prompt": "고양이"}, config)
    with pytest.raises(ValidationError):
        graph.invoke(Command(resume={"approved": "false"}), config)


@pytest.mark.parametrize("prompt", ["", "   ", "x" * 4001])
def test_invalid_prompt_never_reaches_provider(prompt):
    def forbidden(_):
        pytest.fail("invalid prompt reached external provider")

    graph = build_graph(forbidden, InMemorySaver())
    with pytest.raises(ValidationError):
        graph.invoke({"prompt": prompt}, {"configurable": {"thread_id": str(uuid4())}})
