from asa.registry.work_titles import describe_work


def describe(answer=None, inputs=None, schema=None, custom=None, linked=None):
    return describe_work(
        answer, "", inputs or {}, schema or {}, "사용자 정의 에이전트", custom, linked
    )


def test_title_precedence_and_markdown():
    assert describe("**제목:** 이루리", custom="내 작업")["display_title"] == "내 작업"
    assert describe("**제목:** 이루리", linked="이전 작품")["display_title"] == "이루리"
    assert describe(linked="이전 작품")["title_source"] == "linked"
    assert describe({"title": "캐릭터 작품"})["display_title"] == "캐릭터 작품"
    for name in ("미정", "없음", "Untitled", "*내 이름*"):
        assert describe("제목: 자동 이름", custom=name)["display_title"] == name


def test_missing_titles_do_not_use_generic_headings_age_or_instructions():
    result = describe(
        "# 전체 구성 요약\n내용",
        {"topic": "3~5세", "avoid": "뱀"},
        {"properties": {"topic": {"type": "string", "enum": ["3~5세"]}}},
    )
    assert result["display_title"] == "사용자 정의 에이전트"
    assert result["title_source"] == "agent"
    assert describe({"title": "미제공"})["title_source"] == "agent"


def test_previous_answer_title_and_generic_input_excerpt():
    result = describe(
        inputs={"field_1": "제목: 같은 작품\n원문"},
        schema={"properties": {"field_1": {"x-previous-answer": True}}},
    )
    assert result["display_title"] == "같은 작품"
    assert describe(inputs={"goal": "경쟁 제품의 차이 비교"})["title_source"] == "input"
    assert describe(inputs={"goal": "https://example.com/?token=secret"})["title_source"] == "agent"


def test_metadata_is_only_derived_from_declared_fields():
    result = describe(
        inputs={"field_03": "30초", "video_style": "animation_2d"},
        schema={
            "properties": {
                "field_03": {"description": "이야기 길이"},
                "video_style": {"description": "영상 스타일"},
            }
        },
    )
    assert result["context"] == "30초 · 2D 애니메이션"
