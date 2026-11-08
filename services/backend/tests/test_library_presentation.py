from copy import deepcopy

from asa.registry.library_presentation import annotate, visible_items


def item(key, **extra):
    return {"id": key, "kind": "scene", "work_id": "work", **extra}


def test_same_run_duplicates_keep_originals_and_plan_links_to_canonical_scene():
    story = "장면 원문입니다. " * 20
    rows = [item("automation:run:2"), item("automation:run:3"),
            item("answer:plan:1", request_id="plan", answer_version=1)]
    bodies = {rows[0]["id"]: story, rows[1]["id"]: story,
              rows[2]["id"]: {"shots": [{"description": "그림 계획"}]}}
    saved = deepcopy(bodies)
    annotate(rows, bodies, [{"id": "plan", "input": {"scenes": story}}], set())
    assert len(rows) == 3
    assert bodies == saved
    assert [i["id"] for i in visible_items(rows)] == ["automation:run:2"]
    assert rows[1]["duplicate_of"] == rows[0]["id"]
    assert rows[2]["parent_scene_id"] == rows[0]["id"]
    assert rows[0]["related_count"] == 1
    assert rows[0]["duplicate_count"] == 2


def test_distinct_runs_and_ambiguous_or_different_work_scene_inputs_stay_separate():
    story = "동일하지만 서로 다른 실행의 장면입니다. " * 10
    rows = [item("automation:a:1"), item("automation:b:1"),
            item("answer:plan:1", request_id="plan", answer_version=1)]
    bodies = {rows[0]["id"]: story, rows[1]["id"]: story, rows[2]["id"]: {"shots": []}}
    requests = [{"id": "plan", "input": {"scenes": story}}]
    annotate(rows, bodies, requests, set())
    assert len(visible_items(rows)) == 3
    assert rows[2]["is_scene_plan"]
    assert not rows[2].get("parent_scene_id")
    rows[1]["work_id"] = "other"
    annotate(rows, bodies, requests, set())
    assert rows[2]["parent_scene_id"] == rows[0]["id"]


def test_different_outputs_and_regular_scene_contract_are_not_folded():
    rows = [item("automation:a:1"), item("automation:a:2"),
            item("answer:scene:1", request_id="scene", answer_version=1)]
    bodies = {rows[0]["id"]: "first", rows[1]["id"]: "second",
              rows[2]["id"]: {"scenes": ["일반 장면 구성"]}}
    annotate(rows, bodies, [{"id": "scene", "input": {"script": "대본"}}], set())
    assert len(visible_items(rows)) == 3
    assert not rows[2].get("is_scene_plan")
