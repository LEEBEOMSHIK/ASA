from asa.registry.answer_sources import work_summary


def test_work_summary_uses_saved_title_and_limits_request_preview():
    result = work_summary({'title': '고양이 이야기'}, '', {'topic': '상자' * 200})
    assert result['title'] == '고양이 이야기'
    assert len(result['request_preview']) == 240


def test_work_summary_markdown_and_untitled_work():
    assert work_summary('# 하나의 모험\n\n장면1', '', {})['title'] == '하나의 모험'
    assert work_summary('본문', '', {'topic': '새 대본'})['title'] == '새 대본'
    assert work_summary(None, None, {'image': {'id': 'private'}}) == {
        'title': '제목 없는 작업', 'request_preview': ''}
