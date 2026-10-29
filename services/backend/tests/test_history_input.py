from asa.registry.history import valid_input
from asa.registry.service import normalize_schema


def test_request_input_checks_nested_types_required_fields_and_bounds():
    schema = normalize_schema({
        "type": "object", "required": ["items", "count"],
        "properties": {
            "items": {"type": "array", "maxItems": 1,
                      "items": {"type": "string", "maxLength": 3}},
            "count": {"type": "integer", "minimum": 1, "maximum": 3},
            "flag": {"type": "boolean"},
        },
    })
    assert valid_input({"items": ["abc"], "count": 2, "flag": False}, schema)
    for invalid in [
        {}, {"items": ["abcd"], "count": 2}, {"items": ["a", "b"], "count": 2},
        {"items": ["a"], "count": True}, {"items": [], "count": 1.5},
        {"items": [], "count": 4}, {"items": [], "count": 2, "extra": "x"},
        {"items": [], "count": 2, "flag": "false"},
    ]:
        assert not valid_input(invalid, schema)
