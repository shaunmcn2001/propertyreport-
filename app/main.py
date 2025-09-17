from __future__ import annotations
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.services import list_profiles, get_profile
from app.arc import fetch_parcel_by_lotplan, fetch_layer_intersecting_geometry
import io, zipfile, simplekml, datetime as dt

app = FastAPI(title="PropertySales KMZ Export")
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

class ExportRequest(BaseModel):
    service_profile: Optional[str] = Field(None, description="Name of services profile from services.json")
    lotplans: List[str] = Field(..., description="Lot/Plan values (e.g., 2RP53435, 13SP181800)")

@app.get('/health')
def health():
    return {"ok": True}

@app.get('/services')
def services():
    return {"profiles": list_profiles()}

@app.post('/export_kmz')
def export_kmz(payload: ExportRequest):
    if not payload.lotplans:
        raise HTTPException(400, "Provide at least one lotplan.")
    prof_name = payload.service_profile
    prof = get_profile(prof_name) if prof_name else None
    if not prof:
        raise HTTPException(400, f"Unknown or missing service_profile: {prof_name}")

    parcel_cfg = prof.get('parcel') or {}
    p_url = parcel_cfg.get('service_url'); p_layer = parcel_cfg.get('layer_id')
    p_lpf = parcel_cfg.get('lotplan_field'); p_lot = parcel_cfg.get('lot_field'); p_plan = parcel_cfg.get('plan_field')
    if not p_url or p_layer is None:
        raise HTTPException(500, "Parcel service not configured in profile.")

    # Create KML
    kml = simplekml.Kml()
    folder_root = kml.newfolder(name=f"Export {dt.datetime.utcnow().isoformat(timespec='seconds')}Z")

    for lp in payload.lotplans:
        # Fetch parcel geometry
        parcel_fc = fetch_parcel_by_lotplan(p_url, int(p_layer), lp, p_lpf, p_lot, p_plan)
        feats = parcel_fc.get('features', [])
        if not feats:
            continue
        parcel_folder = folder_root.newfolder(name=f"Parcel {lp}")

        # Add parcel polygon(s)
        for feat in feats:
            geom = feat.get('geometry', {})
            _add_geojson_polygon_to_kml(parcel_folder, geom, f"Parcel {lp}")

        # For each optional additional layer in profile, intersect and add
        for section in ('landtypes', 'vegetation'):
            cfg = prof.get(section) or {}
            s_url = cfg.get('service_url'); s_layer = cfg.get('layer_id')
            if not s_url or s_layer is None:
                continue
            inter_fc = fetch_layer_intersecting_geometry(s_url, int(s_layer), parcel_fc)
            for feat in inter_fc.get('features', []):
                geom = feat.get('geometry', {})
                name = _best_name(feat.get('properties', {}), cfg)
                _add_geojson_polygon_to_kml(parcel_folder, geom, f"{section}: {name}")

    # Package as KMZ
    buf = io.BytesIO()
    kml_str = kml.kml()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml', kml_str)
    data = buf.getvalue()
    return Response(content=data, media_type='application/vnd.google-earth.kmz', headers={
        'Content-Disposition': 'attachment; filename="export.kmz"'
    })

def _best_name(props: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    # Prefer name_field then code_field, else a generic id
    name_field = cfg.get('name_field'); code_field = cfg.get('code_field')
    if name_field and props.get(name_field): return str(props.get(name_field))
    if code_field and props.get(code_field): return str(props.get(code_field))
    return str(props.get('OBJECTID', 'feature'))

def _add_geojson_polygon_to_kml(folder, geometry: Dict[str, Any], name: str):
    # Handles Polygon and MultiPolygon
    gtype = geometry.get('type')
    coords = geometry.get('coordinates', [])
    if gtype == 'Polygon':
        _poly_to_kml(folder, coords, name)
    elif gtype == 'MultiPolygon':
        for part in coords:
            _poly_to_kml(folder, part, name)
    else:
        # ignore non-polygons
        pass

def _poly_to_kml(folder, rings, name: str):
    if not rings: return
    outer = rings[0]
    inner = rings[1:] if len(rings) > 1 else []
    p = folder.newpolygon(name=name, outerboundaryis=[(x, y) for x, y in outer], innerboundaryis=[[(x, y) for x, y in r] for r in inner])
    p.extrude = 0
    p.altitudemode = simplekml.AltitudeMode.clamptoground

# Serve UI
app.mount('/', StaticFiles(directory='static', html=True), name='static')
