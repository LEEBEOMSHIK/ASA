import pytest
from pydantic import ValidationError

from asa.auth.access import RoleEdit, password_hash, password_matches
from asa.auth.permissions import ALL_PERMISSIONS, MEMBER_PERMISSIONS, can_request


@pytest.mark.parametrize(
    "method,path,permission",
    [
        ("POST", "/api/v1/video-clips/request/1", "home.generate"),
        ("POST", "/api/v1/work-requests/request/script/rewrite", "home.generate"),
        ("POST", "/api/v1/characters/projects/project/images/batch", "home.generate"),
        ("POST", "/api/v1/video-clips/jobs/job/reviews", "home.review"),
        ("POST", "/api/v1/video-clips/request/1/plan-approve", "home.approve"),
        ("POST", "/api/v1/audio/request/1/select-voice", "home.approve"),
        ("PUT", "/api/v1/admin/models", "models.edit"),
        ("POST", "/api/v1/agent-worker/video/start", "workers.edit"),
        ("POST", "/api/v1/video-planning/provider-connection/alibaba", "video-management.edit"),
        ("PUT", "/api/v1/admin/access/roles/id", "access.edit"),
        ("POST", "/api/v1/admin/work-history/id/delete", "work-history.delete"),
    ],
)
def test_operation_needs_function_and_menu_permission(method, path, permission):
    menu = permission.split(".")[0] + ".view"
    assert not can_request((menu,), method, path)
    assert not can_request((permission,), method, path)
    assert can_request((menu, permission), method, path)


def test_unknown_route_denied_and_disabled_menu_cannot_execute():
    assert not can_request(tuple(ALL_PERMISSIONS), "POST", "/api/v1/future-endpoint")
    assert not can_request(("home.generate",), "POST", "/api/v1/work-requests/x/script/start")
    assert can_request(("home.view",), "GET", "/api/v1/work-requests")
    assert not can_request(("home.view",), "GET", "/api/v1/admin/access")
    assert not can_request(
        ("automations.view", "automations.edit"), "PUT", "/api/v1/automations/a/schedule"
    )


def test_comparison_menu_grants_audio_catalog_only():
    permissions = ("video-comparison.view",)
    assert can_request(permissions, "GET", "/api/v1/audio/catalog")
    assert not can_request(permissions, "GET", "/api/v1/audio/assets")
    assert not can_request(permissions, "GET", "/api/v1/audio/assets/id/media")
    assert not can_request(permissions, "POST", "/api/v1/audio/work/id/1/speech")


def test_role_payload_cannot_grant_owner_or_unlisted_permissions():
    for permissions in [["*"], ["owner"], ["home.generate"], ["home.view", "invalid.edit"]]:
        with pytest.raises(ValidationError):
            RoleEdit(name="role", permissions=permissions)


def test_password_hash_is_salted_and_verifies_without_plaintext():
    password = "test-only-password-123"
    first, second = password_hash(password), password_hash(password)
    assert first != second and password not in first
    assert password_matches(password, first)
    assert not password_matches("wrong", first)
    assert not password_matches(password, "malformed")

def test_design_system_is_an_independent_read_only_menu_permission():
    assert {permission for permission in ALL_PERMISSIONS
            if permission.startswith("design-system.")} == {"design-system.view"}
    assert "design-system.view" not in MEMBER_PERMISSIONS
    assert RoleEdit(name="디자인 검토", permissions=["design-system.view"]).permissions == [
        "design-system.view"
    ]
