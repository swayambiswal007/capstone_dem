
from flask import Flask, render_template, jsonify
from pathlib import Path
import math
import numpy as np

app = Flask(__name__)

BASE = Path(__file__).resolve().parent
DEM_DIR = BASE / "dem"
INPUT_DIR = BASE / "input"

try:
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.features import shapes
except ImportError:
    rasterio = None


def clean_value(v):
    """Convert numpy/NaN/Inf values into JSON-safe Python values."""
    if v is None:
        return None
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def clean_matrix(arr):
    arr = np.asarray(arr, dtype="float64")
    return [
        [clean_value(v) for v in row]
        for row in arr
    ]


def clean_list(arr):
    return [clean_value(v) for v in np.asarray(arr).ravel()]


def find_dem():
    preferred = DEM_DIR / "Copernicus_DSM_COG_10_N30_00_E080_00_DEM.tif"
    if preferred.exists():
        return preferred

    files = sorted(DEM_DIR.glob("*.tif"))
    # Ignore a mistakenly placed prediction.tif if present.
    files = [f for f in files if f.name.lower() != "prediction.tif"]
    return files[0] if files else None


def load_scene():
    if rasterio is None:
        raise RuntimeError(
            "rasterio is not installed. Run: pip install rasterio numpy flask"
        )

    dem_path = find_dem()
    pred_path = INPUT_DIR / "prediction.tif"

    if dem_path is None:
        raise FileNotFoundError(
            "No Copernicus DEM .tif found inside the dem folder."
        )

    if not pred_path.exists():
        raise FileNotFoundError(
            "input/prediction.tif was not found. Put the DINOv2 prediction here."
        )

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype("float32")
        dem_transform = src.transform
        dem_crs = src.crs
        nodata = src.nodata

    with rasterio.open(pred_path) as src:
        prediction = src.read(1).astype("float32")
        pred_transform = src.transform
        pred_crs = src.crs

    aligned = np.zeros(dem.shape, dtype="float32")

    reproject(
        source=prediction,
        destination=aligned,
        src_transform=pred_transform,
        src_crs=pred_crs,
        dst_transform=dem_transform,
        dst_crs=dem_crs,
        resampling=Resampling.nearest,
    )

    valid = np.isfinite(dem)
    if nodata is not None:
        valid &= dem != nodata

    lake = (aligned > 0.5) & valid

    if not np.any(lake):
        raise ValueError(
            "No lake pixels were found after aligning prediction.tif with the DEM."
        )

    return dem, lake, dem_transform, dem_crs, dem_path.name


def pixel_xy(transform, rows, cols):
    xs, ys = rasterio.transform.xy(
        transform, rows, cols, offset="center"
    )
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


def build_payload():
    dem, lake, transform, crs, dem_name = load_scene()

    # ---------------- TERRAIN ----------------
    h, w = dem.shape
    lake_rows, lake_cols = np.where(lake)

    # Crop around the actual predicted lake so the terrain is relevant.
    pad = 90
    r0 = max(0, int(lake_rows.min()) - pad)
    r1 = min(h, int(lake_rows.max()) + pad + 1)
    c0 = max(0, int(lake_cols.min()) - pad)
    c1 = min(w, int(lake_cols.max()) + pad + 1)

    crop = dem[r0:r1, c0:c1]

    max_side = 180
    step = max(1, math.ceil(max(crop.shape) / max_side))

    terrain_z = crop[::step, ::step].copy()
    terrain_valid = np.isfinite(terrain_z)

    if not np.any(terrain_valid):
        raise ValueError("The selected DEM crop contains no valid elevation.")

    terrain_fill = float(np.nanmedian(terrain_z[terrain_valid]))
    terrain_z[~terrain_valid] = terrain_fill

    rr = np.arange(r0, r1, step)
    cc = np.arange(c0, c1, step)

    terrain_x, _ = rasterio.transform.xy(
        transform, np.full_like(cc, r0), cc, offset="center"
    )
    _, terrain_y = rasterio.transform.xy(
        transform, rr, np.full_like(rr, c0), offset="center"
    )

    # Actual lake pixels, not invented geometry.
    lx, ly = pixel_xy(transform, lake_rows, lake_cols)
    lz = dem[lake_rows, lake_cols]

    finite = np.isfinite(lz)
    lx, ly, lz = lx[finite], ly[finite], lz[finite]

    lake_points = [
        {"x": clean_value(x), "y": clean_value(y), "z": clean_value(z)}
        for x, y, z in zip(lx, ly, lz)
        if clean_value(x) is not None
        and clean_value(y) is not None
        and clean_value(z) is not None
    ]

    # ---------------- ACTUAL MASK BLUEPRINT ----------------
    # Work in the same crop. The blueprint surface is literally the DEM
    # elevation only where the DINOv2 prediction is 1.
    mask_crop = lake[r0:r1, c0:c1]
    dem_crop = dem[r0:r1, c0:c1]

    bp_step = max(1, math.ceil(max(mask_crop.shape) / 180))
    bp_z_abs = dem_crop[::bp_step, ::bp_step].copy()
    bp_mask = mask_crop[::bp_step, ::bp_step]

    # Preserve the actual binary footprint. Outside the mask = JSON null.
    bp_z_abs[~bp_mask] = np.nan

    bp_valid = np.isfinite(bp_z_abs)
    mean_elevation = (
        float(np.nanmean(bp_z_abs))
        if np.any(bp_valid) else 0.0
    )

    # Relative elevation makes the blueprint readable without changing
    # the true elevation statistic above.
    bp_z_rel = bp_z_abs - mean_elevation

    bp_rows = np.arange(r0, r1, bp_step)
    bp_cols = np.arange(c0, c1, bp_step)

    bp_x_geo, _ = rasterio.transform.xy(
        transform, np.full_like(bp_cols, r0), bp_cols, offset="center"
    )
    _, bp_y_geo = rasterio.transform.xy(
        transform, bp_rows, np.full_like(bp_rows, c0), offset="center"
    )

    bp_x_geo = np.asarray(bp_x_geo, dtype=float)
    bp_y_geo = np.asarray(bp_y_geo, dtype=float)

    if len(lx):
        cx = float(np.mean(lx))
        cy = float(np.mean(ly))
    else:
        cx = float(np.mean(bp_x_geo))
        cy = float(np.mean(bp_y_geo))

    lat_rad = math.radians(cy)
    meters_per_deg_x = 111320.0 * math.cos(lat_rad)
    meters_per_deg_y = 110540.0

    bp_x_local = (bp_x_geo - cx) * meters_per_deg_x
    bp_y_local = (bp_y_geo - cy) * meters_per_deg_y

    # Estimate actual dimensions from mask pixels.
    if len(lx):
        width_m = float((lx.max() - lx.min()) * meters_per_deg_x)
        length_m = float((ly.max() - ly.min()) * meters_per_deg_y)
    else:
        width_m = length_m = 0.0

    area_m2 = float(np.sum(lake) * abs(transform.a * transform.e))

    blueprint = {
        "x": clean_list(bp_x_local),
        "y": clean_list(bp_y_local),
        "z": clean_matrix(bp_z_rel),
        "absolute_z": clean_matrix(bp_z_abs),
        "center_elevation": clean_value(mean_elevation),
        "width_m": clean_value(width_m),
        "length_m": clean_value(length_m),
        "area_m2": clean_value(area_m2),
    }

    return {
        "terrain": {
            "x": clean_list(terrain_x),
            "y": clean_list(terrain_y),
            "z": clean_matrix(terrain_z),
        },
        "lake_points": lake_points,
        "lake_pixel_count": int(len(lake_points)),
        "blueprint": blueprint,
        "source": {
            "dem": dem_name,
            "prediction": "prediction.tif",
            "crs": str(crs),
        }
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scene")
def scene():
    try:
        return jsonify(build_payload())
    except Exception as exc:
        app.logger.exception("Scene processing failed")
        return jsonify({"error": str(exc)}), 500


# Compatibility endpoints used by the frontend.
# Both return the same single, JSON-safe scene payload so older/newer
# dashboard.js versions can work with this backend.
@app.route("/api/terrain")
def terrain():
    try:
        return jsonify(build_payload())
    except Exception as exc:
        app.logger.exception("Terrain processing failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/blueprint")
def blueprint():
    try:
        payload = build_payload()
        return jsonify(payload.get("blueprint"))
    except Exception as exc:
        app.logger.exception("Blueprint processing failed")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
