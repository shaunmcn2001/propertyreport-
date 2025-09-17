from __future__ import annotations
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import io, zipfile, simplekml, datetime as dt

from app.services import list_profiles, get_profile
from app.arc import fetch_parcel_by_lotplan, fetch_layer_intersection, esri_polygon_to_rings_xy, esri_geom_type

app = FastAPI(title="PropertyReport – KMZ Export")
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

class ExportRequest(BaseModel):
    service_profile: str = Field(..., description="Name of services profile from services.json")
    lotplans: List[str] = Field(..., description="Lot/Plan values (e.g., 2RP53435, 13SP181800)")

@app.get('/health')
def health():
    return {"ok": True}

@app.get('/services')
def services():
    return {"profiles": list_profiles()}

@app.post('/export_kmz')
def export_kmz(payload: ExportRequest):
    prof = get_profile(payload.service_profile)
    if not prof:
        raise HTTPException(400, f"Unknown service_profile: {payload.service_profile}")

    parcel_cfg = (prof or {}).get('parcel') or {}
    p_url = parcel_cfg.get('service_url'); p_layer = parcel_cfg.get('layer_id')
    p_lpf = parcel_cfg.get('lotplan_field'); p_lot = parcel_cfg.get('lot_field'); p_plan = parcel_cfg.get('plan_field')
    if not p_url or p_layer is None:
        raise HTTPException(500, "Parcel service not configured in profile.")

    layers = (prof or {}).get('layers') or []

    # Build KML
    kml = simplekml.Kml()
    folder_root = kml.newfolder(name=f"Export {dt.datetime.utcnow().isoformat(timespec='seconds')}Z")

    for lp in payload.lotplans:
        # Fetch parcel
        parcel_fc = fetch_parcel_by_lotplan(p_url, int(p_layer), lp, p_lpf, p_lot, p_plan)
        p_feats = parcel_fc.get('features', [])
        if not p_feats:
            folder_root.newfolder(name=f"Parcel {lp} (not found)")
            continue

        parcel_folder = folder_root.newfolder(name=f"Parcel {lp}")

        # Add parcel polygons
        for feat in p_feats:
            geom = feat.get('geometry', {})
            if esri_geom_type(geom) == 'Polygon':
                _rings_to_kml(parcel_folder, esri_polygon_to_rings_xy(geom), f"Parcel {lp}")

        # Intersect with all configured layers
        for layer in layers:
            s_url = layer.get('service_url'); s_layer = layer.get('layer_id')
            lname = layer.get('name') or f"Layer {s_layer}"
            if not s_url or s_layer is None:
                continue
            inter_fc = fetch_layer_intersection(s_url, int(s_layer), parcel_fc)
            for feat in inter_fc.get('features', []):
                geom = feat.get('geometry', {})
                if esri_geom_type(geom) != 'Polygon':
                    continue
                props = feat.get('attributes') or feat.get('properties') or {}
                name = _best_name(props, layer, lname)
                _rings_to_kml(parcel_folder, esri_polygon_to_rings_xy(geom), f"{lname}: {name}")

    # KMZ
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml', kml.kml())
    data = buf.getvalue()
    return Response(content=data, media_type='application/vnd.google-earth.kmz',
                    headers={'Content-Disposition': 'attachment; filename="export.kmz"'})

def _best_name(props: Dict[str, Any], layer_cfg: Dict[str, Any], default_name: str) -> str:
    name_field = layer_cfg.get('name_field'); code_field = layer_cfg.get('code_field')
    if name_field and props.get(name_field): return str(props.get(name_field))
    if code_field and props.get(code_field): return str(props.get(code_field))
    return str(props.get('OBJECTID', default_name))

def _rings_to_kml(folder, rings_xy: List[List[tuple]], name: str):
    if not rings_xy: return
    outer = rings_xy[0]
    inner = rings_xy[1:] if len(rings_xy) > 1 else []
    p = folder.newpolygon(name=name, outerboundaryis=outer, innerboundaryis=inner)
    p.extrude = 0
    p.altitudemode = simplekml.AltitudeMode.clamptoground

# Serve UI
app.mount('/', StaticFiles(directory='static', html=True), name='static')
