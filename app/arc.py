from __future__ import annotations
import requests, json
from typing import Dict, Any, Tuple

def _arcgis_query(service_url: str, layer_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{service_url}/{int(layer_id)}/query"
    base = {"f":"geojson","outFields":"*","outSR":4326}
    q = base.copy(); q.update(params or {})
    r = requests.get(url, params=q, timeout=60)
    r.raise_for_status()
    return r.json()

def fetch_parcel_by_lotplan(service_url: str, layer_id: int, lotplan: str,
                            lotplan_field: str|None, lot_field: str|None, plan_field: str|None) -> Dict[str, Any]:
    lp = lotplan.strip().upper()
    if lotplan_field:
        fc = _arcgis_query(service_url, layer_id, {"where": f"UPPER({lotplan_field})='{lp}'"})
        if fc.get("features"): return fc
    if lot_field and plan_field:
        lot, plan = _split_lotplan(lp)
        if lot and plan:
            fc = _arcgis_query(service_url, layer_id, {"where": f"UPPER({lot_field})='{lot}' AND UPPER({plan_field})='{plan}'"})
            if fc.get("features"): return fc
    return {"type":"FeatureCollection","features": []}

def _split_lotplan(lp: str) -> Tuple[str|None, str|None]:
    for i, ch in enumerate(lp):
        if ch.isalpha():
            return lp[:i], lp[i:]
    return None, None

def fetch_layer_intersection(service_url: str, layer_id: int, parcel_fc: Dict[str, Any]) -> Dict[str, Any]:
    feats = parcel_fc.get("features", [])
    if not feats:
        return {"type":"FeatureCollection","features": []}
    geom = feats[0].get("geometry")
    params = {"where":"1=1","geometry": json.dumps(geom),"geometryType":"esriGeometryPolygon","spatialRel":"esriSpatialRelIntersects"}
    return _arcgis_query(service_url, layer_id, params)
