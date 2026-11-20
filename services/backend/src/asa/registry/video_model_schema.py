"""Runtime compatibility for saved WAN model selectors; stored contracts stay immutable."""
from copy import deepcopy
from typing import Any


def model_choices(schema: dict[str, Any]) -> list[Any] | None:
    choices = schema.get('enum')
    if not isinstance(choices, list):
        return None
    if (schema.get('x-video-model') is True and schema.get('type') == 'string'
            and ('wan3' in choices or 'hf-wan3' in choices)):
        from asa.higgsfield_models import EXTRA_MODELS, RESOLUTION_RATES
        bases = {'hf-wan3': 'alibaba/wan-3.0',
                 **{key: value[0] for key, value in EXTRA_MODELS.items()}}
        variants = [f'{key}-{resolution}' for key, name in bases.items()
                    for resolution in RESOLUTION_RATES[name] if resolution != '720p']
        return list(dict.fromkeys([*choices, *bases, *variants]))
    return choices


def runtime_input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Add the alternate WAN provider only where the saved selector already permits WAN."""
    result = deepcopy(schema)

    def visit(node: dict[str, Any]) -> None:
        choices = model_choices(node)
        if choices is not None:
            node['enum'] = choices
        for child in node.get('properties', {}).values():
            if isinstance(child, dict):
                visit(child)
        if isinstance(node.get('items'), dict):
            visit(node['items'])

    visit(result)
    return result
