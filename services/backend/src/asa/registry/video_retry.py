"""Explicit administrator attestation; authentication is never generation evidence."""
import hashlib
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from asa.auth.session import Principal
from asa.registry.schemas import RegistryError


class RetryConfirmation(BaseModel):
    expected_target: str = Field(pattern=r"^[a-f0-9]{64}$")
    id: UUID
    confirmation: Literal['not_generated'] | None = None
    evidence: str = Field(default='', max_length=2000)
    acknowledge_unknown: bool = False

    @property
    def audit_evidence(self) -> str:
        return self.evidence.strip() or (
            'unknown_result_acknowledged' if self.acknowledge_unknown
            else 'failed_request_retry')

    def validate_status(self, status: str) -> None:
        legacy_confirmation = (self.confirmation == 'not_generated'
                               and len(self.evidence.strip()) >= 20)
        if status == 'unknown' and not (self.acknowledge_unknown or legacy_confirmation):
            raise RegistryError(409, 'video_retry_acknowledgment_required')


def require_admin(principal: Principal) -> None:
    if not principal.can('video-management.edit'):
        raise RegistryError(403, 'video_management_forbidden')


def retry_reason(row: dict[str, Any]) -> str | None:
    if row.get('superseded_by'):
        return 'video_retry_superseded'
    if row['status'] not in {'failed', 'unknown'} or row.get('video'):
        return 'video_retry_not_eligible'
    if row.get('provider_task'):
        return 'video_retry_recovery_required'
    return None


def original_metadata(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: row.get(key) for key in (
        'id', 'clip_id', 'status', 'provider_task', 'provider_status',
        'created_at', 'updated_at', 'error_code')}
    result.update({key: row['model_snapshot'].get(key)
                   for key in ('provider', 'model', 'provider_endpoint')})
    return result


def target_fingerprint(model: dict[str, Any], controls: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({'model': model, 'controls': controls},
                                    sort_keys=True, default=str).encode()).hexdigest()
