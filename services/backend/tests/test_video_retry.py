from uuid import uuid4

import pytest

from asa.registry.schemas import RegistryError
from asa.registry.video_retry import RetryConfirmation, retry_reason


@pytest.mark.parametrize('status', ['failed', 'unknown'])
def test_retry_only_without_existing_provider_task(status):
    row = dict(status=status, provider_task=None, video=None, superseded_by=None)
    assert retry_reason(row) is None
    row['provider_task'] = 'existing-task'
    assert retry_reason(row) == 'video_retry_recovery_required'

@pytest.mark.parametrize('state', ['queued','running','submitting','review','approved'])
def test_active_or_successful_job_cannot_retry(state):
    assert retry_reason(dict(status=state, provider_task=None, video=None, superseded_by=None))

def test_only_unknown_requires_acknowledgment():
    body = RetryConfirmation(expected_target='a' * 64, id=uuid4())
    body.validate_status('failed')
    with pytest.raises(RegistryError):
        body.validate_status('unknown')
    body.acknowledge_unknown = True
    body.validate_status('unknown')
    assert body.audit_evidence == 'unknown_result_acknowledged'
