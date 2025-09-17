# PropertySales – Plug-and-Play KMZ Export

A minimal FastAPI app that:
- Reads ArcGIS REST *profiles* from `services.json` (or a file pointed to by `ARCGIS_SERVICES_FILE`).
- Lets you enter Lot/Plan IDs and returns a KMZ containing:
  - Parcel boundary
  - Intersecting layers (e.g., Land Types, Vegetation) configured in the selected profile
- Includes a tiny web UI at `/` and an API at `/export_kmz`.

## Deploy on Render
1. Create a new repo named `propertysales` and push these files.
2. In Render: **New → Web Service → Connect repo**.
3. Keep the defaults (Docker). Ensure env var `PORT=8000` if needed.
4. Deploy and open the web URL. The UI is at `/`.

### Configure ArcGIS endpoints
Edit `services.json` in the repo (redeploy) **or** point `ARCGIS_SERVICES_FILE` to a mounted path. Example structure:

```json
{
  "profiles": {
    "qld_cadastre_default": {
      "parcel": {
        "service_url": "https://example.com/arcgis/rest/services/PlanningCadastre/LandParcelPropertyFramework/MapServer",
        "layer_id": 4,
        "lotplan_field": "lotplan",
        "lot_field": "lot",
        "plan_field": "plan"
      },
      "landtypes": {
        "service_url": "https://example.com/arcgis/rest/services/Environment/LandTypes/MapServer",
        "layer_id": 1,
        "name_field": "LAND_TYPE",
        "code_field": "LANDCODE"
      },
      "vegetation": {
        "service_url": "https://example.com/arcgis/rest/services/Environment/Vegetation/MapServer",
        "layer_id": 0,
        "name_field": "CLASSNAME",
        "code_field": "CLASSCODE"
      }
    }
  }
}
```

## API
- `GET /health` → `{ "ok": true }`
- `GET /services` → Lists available profiles.
- `POST /export_kmz` with JSON:
```json
{
  "service_profile": "qld_cadastre_default",
  "lotplans": ["2RP53435", "13SP181800"]
}
```

Returns `application/vnd.google-earth.kmz`.
