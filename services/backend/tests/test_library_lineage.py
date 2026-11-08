from asa.registry.library_lineage import production_roots


def test_full_content_links_chain_but_not_titles_or_ambiguous_sources():
    body = "동화 원문입니다. " * 30
    scene = "장면 전체 내용입니다. " * 30
    rows = [
        {"id": "a", "input": {}},
        {"id": "b", "input": {"script": body}},
        {"id": "c", "input": {"scenes": scene}},
        {"id": "d", "input": {"title": "같은 제목"}},
    ]
    answers = [
        {"request_id": "a", "answer": {"result": body}},
        {"request_id": "b", "answer": {"result": scene}},
    ]
    assert production_roots(rows, answers) == {"a": "a", "b": "a", "c": "a", "d": "d"}
    rows.append({"id": "duplicate", "input": {}})
    answers.append({"request_id": "duplicate", "answer": {"result": body}})
    assert production_roots(rows, answers)["b"] is None
    assert production_roots(rows, answers)["c"] is None


def test_shared_references_do_not_merge_works_and_source_retries_stay_together():
    a, b = "첫 작품 " * 50, "둘째 작품 " * 50
    rows = [
        {"id": "a", "input": {}},
        {"id": "b", "input": {}},
        {"id": "retry", "source_id": "a", "input": {}},
        {"id": "mixed", "input": {"script": a, "scenes": b}},
        {"id": "valid", "input": {"script": a, "characters": {"source_request_id": "b"}}},
    ]
    answers = [{"request_id": "a", "answer": a}, {"request_id": "b", "answer": b}]
    roots = production_roots(rows, answers)
    assert roots["retry"] == "a"
    assert roots["mixed"] is None
    assert roots["valid"] == "a"


def test_retry_using_a_different_story_follows_current_production_inputs():
    a, b = "원래 작품 원문 " * 30, "새로운 작품 원문 " * 30
    rows = [{"id": "a", "input": {}}, {"id": "b", "input": {}},
            {"id": "first", "input": {"script": a}},
            {"id": "retry", "source_id": "first", "input": {"script": b}}]
    roots = production_roots(rows, [{"request_id": "a", "answer": a},
                                   {"request_id": "b", "answer": b}])
    assert roots["first"] == "a"
    assert roots["retry"] == "b"
