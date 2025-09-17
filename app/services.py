from __future__ import annotations
import os, json
from pathlib import Path
from typing import TypedDict, Dict, Any, List, Optional
class LayerConfig(TypedDict, total=False):
    name: str
    service_url: str
    layer_id: int
    name_field: str
    code_field: str
class ParcelConfig(TypedDict, total=False):
    service_url: str
    layer_id: int
    lotplan_field: str
    lot_field: str
    plan_field: str
    name_field: str
    code_field: str
class Profile(TypedDict, total=False):
    parcel: ParcelConfig
    layers: List[LayerConfig]
DEFAULT_SERVICES_FILE = "services.json"
def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"profiles": {}}
    except Exception:
        return {"profiles": {}}
def _resolve_services_file() -> Path:
    env = os.environ.get("ARCGIS_SERVICES_FILE")
    if env:
        p = Path(env)
        if p.exists():
            return p
    return Path(__file__).resolve().parent.parent / DEFAULT_SERVICES_FILE
def list_profiles() -> Dict[str, Profile]:
    data = _load_json(_resolve_services_file())
    ps = data.get("profiles") or {}
    out: Dict[str, Profile] = {}
    for k, v in ps.items():
        if isinstance(k, str) and isinstance(v, dict):
            out[k] = v  # type: ignore
    return out
def get_profile(name: str) -> Optional[Profile]:
    return list_profiles().get(name)
