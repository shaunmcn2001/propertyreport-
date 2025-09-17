from __future__ import annotations
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import io, zipfile, simplekml
from app.services import list_profiles, get_profile
from app.arc import fetch_parcel_by_lotplan, fetch_layer_intersection

app = FastAPI(title="PropertyReport")
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

class ExportRequest(BaseModel):
    service_profile: str
    lotplans: List[str]

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
        raise HTTPException(400, "Unknown service_profile")
    parcel_cfg = (prof or {}).get('parcel') or {}
    p_url = parcel_cfg.get('service_url'); p_layer = parcel_cfg.get('layer_id')
    p_lpf = parcel_cfg.get('lotplan_field'); p_lot = parcel_cfg.get('lot_field'); p_plan = parcel_cfg.get('plan_field')
    if not p_url or p_layer is None:
        raise HTTPException(500, "Parcel service not configured")
    layers = (prof or {}).get('layers') or []
    kml = simplekml.Kml()
    fold = kml.newfolder(name='Export')
    for lp in payload.lotplans:
        parcel_fc = fetch_parcel_by_lotplan(p_url, int(p_layer), lp, p_lpf, p_lot, p_plan)
        p_feats = parcel_fc.get('features', [])
        pf = fold.newfolder(name=f'Parcel {lp}')
        for feat in p_feats:
            geom = feat.get('geometry', {})
            _add_geojson_polygon(pf, geom, f'Parcel {lp}')
        for layer in layers:
            s_url = layer.get('service_url'); s_layer = layer.get('layer_id')
            lname = layer.get('name') or f'Layer {s_layer}'
            if not s_url or s_layer is None: continue
            inter_fc = fetch_layer_intersection(s_url, int(s_layer), parcel_fc)
            for feat in inter_fc.get('features', []):
                geom = feat.get('geometry', {})
                _add_geojson_polygon(pf, geom, f'{lname}')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml', kml.kml())
    return Response(content=buf.getvalue(), media_type='application/vnd.google-earth.kmz', headers={'Content-Disposition':'attachment; filename="export.kmz"'})

def _add_geojson_polygon(folder, geometry, name: str):
    gtype = geometry.get('type'); coords = geometry.get('coordinates', [])
    if gtype == 'Polygon':
        _poly(folder, coords, name)
    elif gtype == 'MultiPolygon':
        for part in coords:
            _poly(folder, part, name)

def _poly(folder, rings, name):
    if not rings: return
    outer = rings[0]
    inner = rings[1:] if len(rings) > 1 else []
    p = folder.newpolygon(name=name, outerboundaryis=[(x,y) for x,y in outer], innerboundaryis=[[(x,y) for x,y in r] for r in inner])

app.mount('/', StaticFiles(directory='static', html=True), name='static')
