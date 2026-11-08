from asa.registry.library import answer_kind, family_roots


def test_library_does_not_merge_titles_and_handles_missing_parents_and_cycles():
    assert family_roots(
        [
            {"id": "a", "source_id": None},
            {"id": "b", "source_id": "a"},
            {"id": "c", "source_id": "missing"},
        ]
    ) == {"a": "a", "b": "a", "c": "c"}
    assert family_roots([{"id": "b", "source_id": "a"}, {"id": "a", "source_id": "b"}]) == {
        "a": "a",
        "b": "a",
    }


def test_library_classifies_contracts_not_agent_names():
    assert answer_kind({"scenes": []}) == "scene"
    assert answer_kind({"characters": []}) == "character"
    assert answer_kind({"clips": []}) == "prompt"
    assert answer_kind({"script": "hello"}) == "script"
    assert answer_kind({"arbitrary": "hello"}) == "document"


def test_legacy_text_uses_saved_role_only_when_contract_is_unstructured():
    assert answer_kind({}, "무서운 쇼츠 대본 작가") == "script"
    assert answer_kind({"result": "text"}, "장면 구성 에이전트") == "scene"
    assert answer_kind({"characters": []}, "대본 작가") == "character"
    assert answer_kind({}, "일반 분석가") == "document"
