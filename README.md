# GLOF Frontend V8 — endpoint + NaN fixed

The reported HTTP 404 happened because the browser requested `/api/terrain`
while the backend version exposed a different route.

V8:
- dashboard.js uses `/api/scene`
- app.py also exposes `/api/terrain` and `/api/blueprint` compatibility routes
- NaN/Infinity values are converted to JSON-safe null
- actual prediction.tif is aligned to the Copernicus DEM
- actual DINOv2 mask is used for the blueprint

Install:
pip install flask rasterio numpy

Run:
python app.py

Then hard refresh:
Ctrl + F5

Expected:
GET /api/scene 200
