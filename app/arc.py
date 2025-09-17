from __future__ import annotations
import requests, json
from typing import Dict, Any, Tuple, List

def _arcgis_query(service_url: str, layer_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{service_url}/{int(layer_id)}/query"
    base = {
        "f": "json",          # use EsriJSON (more widely supported than GeoJSON)
        "outFields": "*",
        "outSR": 4326,
        "returnGeometry": "true"
    }
    q = base.copy()
    q.update(params or {})
    r = requests.get(url, params=q, timeout=60)
    r.raise_for_status()
    return r.json()

def fetch_parcel_by_lotplan(service_url: str, layer_id: int, lotplan: str,
                            lotplan_field: str|None, lot_field: str|None, plan_field: str|None) -> Dict[str, Any]:
    lp = lotplan.strip().upper()
    common = {"outFields": "*", "outSR": 4326, "returnGeometry": "true"}

    # Try combined LOTPLAN field first
    if lotplan_field:
        fc = _arcgis_query(service_url, layer_id, {**common, "where": f"UPPER({lotplan_field})='{lp}'"})
        if fc.get("features"): return fc

    # Fallback split fields
    if lot_field and plan_field:
        lot, plan = _split_lotplan(lp)
        if lot and plan:
            fc = _arcgis_query(service_url, layer_id, {**common, "where": f"UPPER({lot_field})='{lot}' AND UPPER({plan_field})='{plan}'"})
            if fc.get("features"): return fc

    return {"features": []}

def _split_lotplan(lp: str) -> Tuple[str|None, str|None]:
    # e.g., 2RP53435 or 13SP181800
    for i, ch in enumerate(lp):
        if ch.isalpha():
            return lp[:i], lp[i:]
    return None, None

def fetch_layer_intersection(service_url: str, layer_id: int, parcel_fc: Dict[str, Any]) -> Dict[str, Any]:
    feats = parcel_fc.get("features", [])
    if not feats:
        return {"features": []}

    geom = _merge_polygon_geometries(feats)
    if not geom:
        return {"features": []}

    params = {
        "where": "1=1",
        "geometry": json.dumps(geom),
        "geometryType": "esriGeometryPolygon",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": 4326,
        "outSR": 4326,
        "returnGeometry": "true",
    }
    return _arcgis_query(service_url, layer_id, params)


def _merge_polygon_geometries(features: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    rings: List[List[List[float]]] = []
    sr: Dict[str, Any] | None = None

    for feat in features:
        geom = feat.get("geometry") or {}
        if "rings" not in geom:
            continue
        feat_rings = geom.get("rings") or []
        if isinstance(feat_rings, list):
            for ring in feat_rings:
                if isinstance(ring, list) and ring:
                    rings.append(ring)
        if not sr and isinstance(geom.get("spatialReference"), dict):
            sr = geom.get("spatialReference")

    if not rings:
        return None

    merged: Dict[str, Any] = {"rings": rings}
    if sr:
        merged["spatialReference"] = sr
    else:
        merged["spatialReference"] = {"wkid": 4326}
    return merged

def esri_polygon_to_rings_xy(geom: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
    """Return list of linear rings (outer first) as [(x,y), ...] in WGS84."""
    if not geom: return []
    rings = geom.get("rings") or []
    out = []
    for ring in rings:
        out.append([(float(x), float(y)) for x, y in ring])
    return out

def esri_geom_type(geom: Dict[str, Any]) -> str:
    if not geom: return ""
    if "rings" in geom: return "Polygon"
    if "paths" in geom: return "Polyline"
    if {k for k in geom if k in ("x","y")}:
        return "Point"
    return ""
