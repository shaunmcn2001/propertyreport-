from __future__ import annotations
import os, json
from pathlib import Path
from typing import TypedDict, Optional, Dict, Any

class ServiceProfile(TypedDict, total=False):
    parcel: Dict[str, Any]
    landtypes: Dict[str, Any]
    vegetation: Dict[str, Any]

class ServicesConfig(TypedDict):
    profiles: Dict[str, ServiceProfile]

DEFAULT_SERVICES_FILE = "services.json"

def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"profiles": {}}
    except Exception:
        return {"profiles": {}}

def resolve_services_file() -> Path:
    env = os.environ.get("ARCGIS_SERVICES_FILE")
    if env:
        p = Path(env)
        if p.exists():
            return p
    return Path(__file__).resolve().parent.parent / DEFAULT_SERVICES_FILE

def list_profiles() -> Dict[str, ServiceProfile]:
    data = _load_json(resolve_services_file())
    profs = data.get("profiles") or {}
    out: Dict[str, ServiceProfile] = {}
    for k, v in profs.items():
        if isinstance(k, str) and isinstance(v, dict):
            out[k] = v  # type: ignore
    return out

def get_profile(name: str) -> Optional[ServiceProfile]:
    return list_profiles().get(name)
