"""Server-only regional profiles and workspace selection; jobs keep their endpoint."""
from typing import Any, Literal
from uuid import UUID

from pydantic import SecretStr

from asa.config import Settings

WanRegion = Literal['ap-southeast-1', 'ap-northeast-1']
REGIONS = {'ap-southeast-1': '싱가포르', 'ap-northeast-1': '도쿄'}


def regional_settings(settings: Settings, region: str) -> Settings:
    prefix = {'ap-southeast-1': 'wan_singapore', 'ap-northeast-1': 'wan_tokyo'}.get(region)
    key = getattr(settings, f'{prefix}_api_key') if prefix else SecretStr('')
    workspace = getattr(settings, f'{prefix}_workspace_id') if prefix else ''
    # A partial new profile must not borrow another profile's credential or workspace.
    if not key.get_secret_value() and not workspace and region == settings.wan_region:
        key, workspace = settings.wan_api_key, settings.wan_workspace_id
    return settings.model_copy(update={'wan_region': region, 'wan_api_key': key,
                                       'wan_workspace_id': workspace})


def selection(conn: Any, settings: Settings, workspace: UUID) -> dict[str, Any]:
    row = conn.execute('SELECT active_region,revision FROM wan_region_controls '
                       'WHERE workspace_id=%s', (workspace,)).fetchone()
    return dict(row) if row else {'active_region': settings.wan_region, 'revision': 0}


def active_settings(conn: Any, settings: Settings, workspace: UUID) -> Settings:
    return regional_settings(settings, selection(conn, settings, workspace)['active_region'])


def status(conn: Any, settings: Settings, workspace: UUID) -> dict[str, Any]:
    from asa.video_connection import current
    from asa.video_providers import connection_state

    return {**selection(conn, settings, workspace), 'regions': [
        {'region': region, 'label': label,
         'connection_state': connection_state(regional_settings(settings, region), 'alibaba'),
         'connection_check': current(regional_settings(settings, region), workspace, 'alibaba')}
        for region, label in REGIONS.items()]}
