from asa.registry.library_excerpt import excerpt


def test_excerpt_reads_nested_scene_text_without_serializing_structure():
    data = {"scenes": [{"title": "골목", "description": "아이가 발자국을 발견한다."},
                       {"narration": "누가 지나갔을까?"}]}
    assert excerpt(data) == "골목 · 아이가 발자국을 발견한다. · 누가 지나갔을까?"
    assert data["scenes"][0]["title"] == "골목"


def test_excerpt_is_bounded_and_ignores_metadata_and_links():
    assert excerpt({"id": "secret-id", "url": "https://example.com", "result": "본문"}) == "본문"
    assert len(excerpt({"script": "가" * 2000})) <= 320
    assert excerpt(None) == ""
    assert excerpt({"result": "첫 줄\n\n다음 줄"}) == "첫 줄 다음 줄"
    assert excerpt({"script": "# 제목\n**설명:** 장면\n---\n다음"}) == "제목 설명: 장면 다음"
