from asa.registry.answer_sources import work_summary


def test_scene_summary_uses_work_title_or_script_excerpt_instead_of_section_heading():
    answer = '# A. 전체 구성 요약\n\n- **제목:** 미제공'
    script = '[씬 1] 00:00~00:10 — 노크\n어두운 원룸.'
    expected = '대본 발췌 · ' + script.splitlines()[0]
    assert work_summary(answer, '', {'script': script})['title'] == expected
    assert work_summary(answer, '', {'script': '**제목:** 새벽의 노크'})['title'] == '새벽의 노크'
    named = answer.replace('미제공', '문밖의 목소리')
    assert work_summary(named, '', {})['title'] == '문밖의 목소리'
    result = {'result': '**제목: 고양이의 오후**\n본문'}
    assert work_summary(result, '', {})['title'] == '고양이의 오후'


def test_work_summary_uses_saved_title_and_limits_request_preview():
    result = work_summary({'title': '고양이 이야기'}, '', {'topic': '상자' * 200})
    assert result['title'] == '고양이 이야기'
    assert len(result['request_preview']) == 240


def test_work_summary_markdown_and_untitled_work():
    assert work_summary('# 하나의 모험\n\n장면1', '', {})['title'] == '하나의 모험'
    assert work_summary('본문', '', {'topic': '새 대본'})['title'] == '새 대본'
    assert work_summary(None, None, {'image': {'id': 'private'}}) == {
        'title': '제목 없는 작업', 'request_preview': ''}
