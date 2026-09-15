# GLOF 20-Scene Terrain Explorer

This package integrates 20 representative image/label pairs selected from the uploaded 100-scene dataset into the existing spatial dashboard concept.

## What is included
- 20 RGB GeoTIFF scenes in `data/images/`
- matching reference labels in `data/labels/`
- `scenes.json` manifest
- interactive Flask + Plotly dashboard
- scene selector with Previous/Next navigation
- RGB scene viewer
- reference-label overlay
- Copernicus GLO-30 terrain retrieval
- 3D terrain surface with the lake footprint highlighted
- elevation, slope, elevation-difference and area metrics
- lake footprint blueprint
- existing temporal GLOF predictor panel as a presentation stub

## Important scientific distinction
The uploaded ZIP contains images and labels, but not DINOv2 prediction rasters. Therefore the overlay is explicitly labelled **Reference label**. Do not present it as a DINOv2 prediction in a paper/panel until you connect your trained DINOv2 model or supply its `prediction.tif` outputs.

## DEM handling
The app first looks for a matching Copernicus GLO-30 tile in `dem/`. If it is not present, it attempts to read the public Copernicus COG directly over the internet. For a reliable offline presentation, download the required Copernicus tiles and place them in `dem/` using their official filenames, for example:

`Copernicus_DSM_COG_10_N30_00_E080_00_DEM.tif`

## Run
```bash
pip install flask rasterio numpy scipy pillow
python app.py
```
Open `http://127.0.0.1:5000`

## Why these 20
The 20 scenes are selected at approximately regular intervals through the 100-image dataset, giving a broader geographic/scene sample instead of taking only the first 20 files.
