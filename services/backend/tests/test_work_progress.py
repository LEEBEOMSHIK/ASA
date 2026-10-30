from asa.registry.work_progress import character_progress, combine_progress, summarize


def test_generic_progress_can_describe_non_image_work():
    result = summarize("voice", "음성", 2, [{"id": "a", "name": "내레이션", "state": "review"}])
    assert result["status"] == "review"
    assert result["counts"]["review"] == 1
    assert result["kind"] == "voice"


def test_all_review_groups_must_finish_before_completion():
    answer = summarize('answer', '답변 검토', 1, [{'id':'answer','name':'답변','state':'review'}])
    images = summarize('character_images', '캐릭터 이미지', 1,
                       [{'id':'hana','name':'하나','state':'approved'}])
    combined = combine_progress([answer, images])
    assert combined['status'] == 'review'
    assert combined['resume_anchor'] == 'followup-answer'
    assert combined['counts']['approved'] == 1
    assert len(combined['groups']) == 2


def test_character_progress_tracks_all_required_items_and_regeneration():
    characters = [{"id": c, "name": c} for c in "abcd"]
    jobs = [{"id": "a1", "character_id": "a", "version": 1, "status": "succeeded"},
            {"id": "b1", "character_id": "b", "version": 1, "status": "succeeded"},
            {"id": "c1", "character_id": "c", "version": 1, "status": "running"}]
    result = character_progress(1, characters, jobs, {"a": "a1"}, set())
    assert result["counts"] == dict(pending=1, queued=0, running=1, review=1,
                                    approved=1, excluded=0, failed=0, unknown=0)
    assert result["status"] == "running"
    jobs.append({"id": "a2", "character_id": "a", "version": 2, "status": "succeeded"})
    assert character_progress(1, characters, jobs, {"a": "a1"}, set())["counts"]["review"] == 2


def test_completion_exclusion_and_unconfirmed_errors():
    chars = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    jobs = [{"id": "a1", "character_id": "a", "version": 1, "status": "succeeded"}]
    assert character_progress(1, chars, jobs, {"a": "a1"}, {"b"})["status"] == "complete"
    assert character_progress(1, chars, jobs, {}, {"b"})["status"] == "review"
    assert character_progress(1, chars, jobs, {"a": "a1"}, {"a", "b"})["status"] == "not_required"
    jobs.append({"id": "a2", "character_id": "a", "version": 2, "status": "unknown"})
    assert character_progress(1, chars, jobs, {"a": "a1"}, {"b"})["status"] == "attention"
