"""One allow-list for UI menus and authenticated API operations. Unknown routes fail closed."""

from typing import Any

CATALOG: list[dict[str, Any]] = [
    {
        "id": "home",
        "label": "작업 공간",
        "actions": ["view", "edit", "generate", "review", "approve"],
    },
    {"id": "agents", "label": "에이전트", "actions": ["view"]},
    {"id": "tools", "label": "도구 라이브러리", "actions": ["view"]},
    {"id": "characters", "label": "보관함", "actions": ["view", "edit"]},
    {
        "id": "automations",
        "label": "자동화 빌더",
        "actions": ["view", "edit", "generate", "approve", "delete"],
    },
    {"id": "video-comparison", "label": "영상·음성 AI 비교", "actions": ["view"]},
    {"id": "admin-agents", "label": "에이전트 관리", "actions": ["view", "edit"]},
    {"id": "work-history", "label": "작업 관리", "actions": ["view", "delete"]},
    {"id": "models", "label": "AI 모델 관리", "actions": ["view", "edit"]},
    {"id": "monitoring", "label": "AI 사용량·비용", "actions": ["view"]},
    {"id": "branding", "label": "브랜드 설정", "actions": ["view", "edit"]},
    {"id": "design-system", "label": "디자인 시스템", "actions": ["view"]},
    {"id": "workers", "label": "백그라운드 작업 관리", "actions": ["view", "edit"]},
    {"id": "video-management", "label": "영상 생성 관리", "actions": ["view", "edit"]},
    {"id": "access", "label": "사용자·권한 관리", "actions": ["view", "edit"]},
]
ALL_PERMISSIONS = frozenset(f"{row['id']}.{a}" for row in CATALOG for a in row["actions"])
MEMBER_PERMISSIONS = [f"{row['id']}.{a}" for row in CATALOG[:4] for a in row["actions"]]


def allowed(permissions: tuple[str, ...] | list[str], permission: str) -> bool:
    return "*" in permissions or (
        permission in permissions and permission.split(".")[0] + ".view" in permissions
    )


def requirements(method: str, path: str) -> tuple[tuple[str, ...], ...]:
    """AND groups of OR permissions; () is session-only, unknown is never granted."""
    p = path.removeprefix("/api/v1/").strip("/")
    parts = p.split("/")
    root, tail = parts[0], parts[-1]
    read = method in {"GET", "HEAD", "OPTIONS"}

    def need(menu: str, action: str = "view") -> tuple[tuple[str, ...], ...]:
        return ((f"{menu}.{action}",),)

    if root in {"session", "profile"}:
        return ()
    if p.startswith("admin/access"):
        return need("access", "view" if read else "edit")
    if root == "admin":
        menu = {"models": "models", "ai-usage": "monitoring", "work-history": "work-history"}.get(
            parts[1] if len(parts) > 1 else "", ""
        )
        return need(menu, "view" if read else "delete" if menu == "work-history" else "edit")
    if root == "video-management":
        return need(root, "view" if read else "edit")
    if root == "agent-worker":
        return need("workers", "view" if read else "edit")
    if root == "branding":
        return () if read else need("branding", "edit")
    if root == "agents":
        return (("agents.view", "admin-agents.view"),) if read else need("admin-agents", "edit")
    if root == "tools":
        return (
            ("home.view", "agents.view", "tools.view", "admin-agents.view", "automations.view"),
        )
    if root in {"ai-models", "model-profiles", "review-connection", "art-style-catalog"}:
        return (
            (("home.view", "admin-agents.view", "automations.view", "characters.view"),)
            if read
            else need("admin-agents", "edit")
        )
    if root in {"agent-categories", "automation-categories"}:
        if read or "favorites" in parts:
            return (("home.view", "agents.view", "admin-agents.view", "automations.view"),)
        return need("admin-agents" if root == "agent-categories" else "automations", "edit")
    if root in {"automations", "automation-runtime", "automation-runs"}:
        action = (
            "view"
            if read
            else "delete"
            if method == "DELETE"
            else "generate"
            if tail == "runs"
            else "approve"
            if tail == "approve"
            else "edit"
        )
        if tail == "schedule" and not read:
            return (("automations.edit",), ("automations.generate",))
        return need("automations", action)
    if root == "editing":
        return need("home", "view" if read else "approve" if tail == "approve" else "generate")
    if root == "library":
        return need("characters", "view" if read else "edit")
    if root == "video-planning":
        if "connection" in tail or "provider-connection" in parts:
            return need("video-management", "edit")
        if read or tail in {"estimate", "durations"}:
            return (("home.view", "video-management.view", "video-comparison.view"),)
        return need("home", "view" if read or tail in {"estimate", "durations"} else "edit")
    if p == "audio/catalog" and read:
        return (("home.view", "characters.view", "video-comparison.view"),)
    if root in {"work-requests", "characters", "video-clips", "audio", "video-references"}:
        if read:
            return (
                (("home.view", "characters.view"),)
                if root in {"characters", "audio"}
                else need("home")
            )
        if tail in {"selection", "resolve"}:
            return (("home.view", "characters.view"),)
        action = "edit"
        if tail in {"approve", "plan-approve", "plan-revoke", "select-voice"}:
            action = "approve"
        elif tail == "reviews":
            action = "review"
        elif tail in {
            "generate",
            "start",
            "retry",
            "rewrite",
            "revise-clip",
            "images",
            "batch",
            "speech",
            "sample",
            "compose",
        } or (root == "video-clips" and len(parts) == 3):
            action = "generate"
        return need("home", action)
    return (("__unregistered__",),)


def can_request(permissions: tuple[str, ...], method: str, path: str) -> bool:
    return "*" in permissions or all(
        any(allowed(permissions, p) for p in group) for group in requirements(method, path)
    )
