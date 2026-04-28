from typing import Any, Dict
from datetime import datetime

def to_json_safe(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for key, value in data.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value

    return result