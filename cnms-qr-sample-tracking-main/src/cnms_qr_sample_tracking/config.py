import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
import os, sys

# Moved to non-hidden directory for now
CONFIG_DIR = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "printer": {
        "name": "EPSON LW-PX750",
    },
    "datafed": {
        "context": "p/cnms",
        "repo_id": "",
    },
    "globus": {
        "endpoint_path": str(Path.home() / "Documents"),
        "src_collection": "",
    },
    "user": {
        "name": "",
        "phone": "",
        "email": "",
        "project_number": "",
    },
    "provenance": {
        "orginization": "",
        "sub-orginization": "",
        "instrument": "",
        "seaid_role": "None",
    },
}


def _merge_dict(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class AppConfig:
    def __init__(self, config_path: Path = CONFIG_FILE) -> None:
        self.config_path = config_path
        self.data = self.load()
        # Force new config file creation if non existant
        self.save()

    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return deepcopy(DEFAULT_CONFIG)

        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return deepcopy(DEFAULT_CONFIG)

        if not isinstance(raw, dict):
            return deepcopy(DEFAULT_CONFIG)

        return _merge_dict(DEFAULT_CONFIG, raw)

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
