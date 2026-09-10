import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.warp import reproject, Resampling
from mpl_toolkits.mplot3d import Axes3D


# --------------------------------------------------
# FILES
# --------------------------------------------------

dem_path = "dem/dem.tif"
prediction_path = "input/prediction.tif"


# --------------------------------------------------
# LOAD DEM
# --------------------------------------------------

with rasterio.open(dem_path) as dem_src:

    dem = dem_src.read(1).astype(np.float32)

    dem_transform = dem_src.transform
    dem_crs = dem_src.crs

    height, width = dem.shape

    print("DEM size:", width, "x", height)
    print("DEM CRS:", dem_crs)

    valid = np.isfinite(dem)

    print(
        "Elevation range:",
        np.nanmin(dem[valid]),
        "-",
        np.nanmax(dem[valid]),
        "m"
    )


# --------------------------------------------------
# LOAD DINOv2 PREDICTION
# --------------------------------------------------

with rasterio.open(prediction_path) as pred_src:

    prediction = pred_src.read(1)

    print("\nPrediction size:",
          pred_src.width,
          "x",
          pred_src.height)

    print("Prediction CRS:", pred_src.crs)

    print("Prediction values:",
          np.unique(prediction)[:20])


# --------------------------------------------------
# ALIGN PREDICTION TO DEM
# --------------------------------------------------

aligned_prediction = np.zeros(
    (height, width),
    dtype=np.float32
)


reproject(
    source=prediction,
    destination=aligned_prediction,

    src_transform=pred_src.transform,
    src_crs=pred_src.crs,

    dst_transform=dem_transform,
    dst_crs=dem_crs,

    resampling=Resampling.nearest
)


# --------------------------------------------------
# CONVERT TO BINARY LAKE MASK
# --------------------------------------------------

# If prediction is already 0/1
lake_mask = aligned_prediction > 0.5


print("\nLake pixels:", np.sum(lake_mask))
print(
    "Lake percentage:",
    np.sum(lake_mask) / lake_mask.size * 100,
    "%"
)


# --------------------------------------------------
# CREATE REAL LONGITUDE / LATITUDE GRID
# --------------------------------------------------

rows, cols = np.indices((height, width))

xs, ys = rasterio.transform.xy(
    dem_transform,
    rows,
    cols
)

X = np.asarray(xs)
Y = np.asarray(ys)


# --------------------------------------------------
# PLOT 3D DEM
# --------------------------------------------------

fig = plt.figure(figsize=(12, 9))

ax = fig.add_subplot(
    111,
    projection="3d"
)


# Downsample for faster rendering
step = max(1, min(height, width) // 200)

X_plot = X[::step, ::step]
Y_plot = Y[::step, ::step]
Z_plot = dem[::step, ::step]


# DEM surface
surface = ax.plot_surface(
    X_plot,
    Y_plot,
    Z_plot,

    cmap="terrain",

    linewidth=0,

    antialiased=True,

    alpha=0.9
)


# --------------------------------------------------
# LAKE OVERLAY
# --------------------------------------------------

lake = lake_mask[::step, ::step]

# Put lake slightly above DEM surface
lake_z = Z_plot.copy()

lake_z[~lake] = np.nan

lake_z += 5


ax.plot_surface(
    X_plot,
    Y_plot,
    lake_z,

    color="blue",

    alpha=0.8,

    linewidth=0
)


# --------------------------------------------------
# LABELS
# --------------------------------------------------

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_zlabel("Elevation (m)")

ax.set_title(
    "3D Copernicus DEM with DINOv2 Glacial Lake Prediction"
)


fig.colorbar(
    surface,
    ax=ax,
    shrink=0.6,
    label="Elevation (m)"
)


# --------------------------------------------------
# SAVE
# --------------------------------------------------

plt.tight_layout()

plt.savefig(
    "output/3d_dem_lake.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print("\n3D visualization saved to:")
print("output/3d_dem_lake.png")