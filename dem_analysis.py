import rasterio
import numpy as np
import matplotlib.pyplot as plt

from rasterio.warp import reproject, Resampling
from rasterio.transform import xy


# ============================================================
# FILE PATHS
# ============================================================

from pathlib import Path

# ============================================================
# FILE PATHS
# ============================================================

DEM_FOLDER = Path("dem")
PREDICTION_PATH = Path("input/prediction.tif")
OUTPUT_FIGURE = Path("output/dem_analysis.png")


# Automatically find the DEM GeoTIFF
dem_files = list(DEM_FOLDER.glob("*.tif"))

if len(dem_files) == 0:
    raise FileNotFoundError(
        "No DEM .tif file found inside the dem folder."
    )

if len(dem_files) > 1:
    print("Multiple DEM files found:")
    for f in dem_files:
        print("  ", f)

DEM_PATH = dem_files[0]

print("Using DEM:")
print(DEM_PATH)




# ============================================================
# 1. LOAD DEM
# ============================================================

print("\nLoading DEM...")

with rasterio.open(DEM_PATH) as dem_src:

    dem = dem_src.read(1).astype(np.float32)

    dem_transform = dem_src.transform
    dem_crs = dem_src.crs

    dem_width = dem_src.width
    dem_height = dem_src.height

    dem_nodata = dem_src.nodata


print("DEM dimensions:", dem_width, "x", dem_height)
print("DEM CRS:", dem_crs)
print("DEM nodata:", dem_nodata)


# Replace nodata with NaN
if dem_nodata is not None:
    dem[dem == dem_nodata] = np.nan


print(
    "DEM elevation:",
    np.nanmin(dem),
    "to",
    np.nanmax(dem),
    "m"
)


# ============================================================
# 2. LOAD DINOV2 PREDICTION
# ============================================================

print("\nLoading DINOv2 prediction...")

with rasterio.open(PREDICTION_PATH) as pred_src:

    prediction = pred_src.read(1)

    pred_transform = pred_src.transform
    pred_crs = pred_src.crs

    pred_width = pred_src.width
    pred_height = pred_src.height


print("Prediction dimensions:",
      pred_width, "x", pred_height)

print("Prediction CRS:", pred_crs)

print(
    "Prediction unique values:",
    np.unique(prediction)[:20]
)


# ============================================================
# 3. ALIGN PREDICTION WITH DEM
# ============================================================

print("\nAligning DINOv2 prediction with DEM...")


aligned_prediction = np.zeros(
    (dem_height, dem_width),
    dtype=np.float32
)


reproject(

    source=prediction,

    destination=aligned_prediction,

    src_transform=pred_transform,
    src_crs=pred_crs,

    dst_transform=dem_transform,
    dst_crs=dem_crs,

    resampling=Resampling.nearest
)


# ============================================================
# 4. CREATE BINARY LAKE MASK
# ============================================================

# Assuming DINOv2 output:
# 0 = background
# 1 = lake

lake_mask = aligned_prediction > 0.5


lake_pixels = np.sum(lake_mask)

print("\nLake pixels:", lake_pixels)

print(
    "Lake coverage:",
    round(
        lake_pixels / lake_mask.size * 100,
        3
    ),
    "%"
)


# ============================================================
# 5. EXTRACT LAKE ELEVATION
# ============================================================

lake_elevation = dem[lake_mask]

lake_elevation = lake_elevation[
    np.isfinite(lake_elevation)
]


if len(lake_elevation) == 0:

    raise ValueError(
        "No valid DEM elevation values found inside lake mask."
    )


mean_lake_elevation = np.mean(lake_elevation)

min_lake_elevation = np.min(lake_elevation)

max_lake_elevation = np.max(lake_elevation)

elevation_range = (
    max_lake_elevation -
    min_lake_elevation
)


# ============================================================
# 6. CALCULATE TERRAIN SLOPE
# ============================================================

print("\nCalculating terrain slope...")


# DEM resolution in degrees
pixel_x = abs(dem_transform.a)
pixel_y = abs(dem_transform.e)


# Approximate conversion from degrees to metres
# around Himalayan latitude (~30 degrees)

latitude_reference = 30.0

meters_per_degree_lat = 111320

meters_per_degree_lon = (
    111320 *
    np.cos(
        np.radians(latitude_reference)
    )
)


pixel_width_m = (
    pixel_x *
    meters_per_degree_lon
)

pixel_height_m = (
    pixel_y *
    meters_per_degree_lat
)


dz_dy, dz_dx = np.gradient(
    dem,
    pixel_height_m,
    pixel_width_m
)


slope_radians = np.arctan(
    np.sqrt(
        dz_dx ** 2 +
        dz_dy ** 2
    )
)


slope_degrees = np.degrees(
    slope_radians
)


lake_slope = slope_degrees[lake_mask]

lake_slope = lake_slope[
    np.isfinite(lake_slope)
]


mean_lake_slope = np.mean(lake_slope)


# ============================================================
# 7. SURROUNDING TERRAIN
# ============================================================

print("\nAnalyzing surrounding terrain...")


# Simple surrounding region:
# expand lake mask using pixel dilation

from scipy.ndimage import binary_dilation


surrounding_region = binary_dilation(
    lake_mask,
    iterations=8
)


# Remove lake itself
surrounding_region = (
    surrounding_region &
    ~lake_mask
)


surrounding_elevation = dem[
    surrounding_region
]


surrounding_elevation = surrounding_elevation[
    np.isfinite(surrounding_elevation)
]


if len(surrounding_elevation) > 0:

    mean_surrounding_elevation = np.mean(
        surrounding_elevation
    )

else:

    mean_surrounding_elevation = np.nan


# ============================================================
# 8. ELEVATION DIFFERENCE
# ============================================================

elevation_difference = (
    mean_surrounding_elevation -
    mean_lake_elevation
)


# ============================================================
# 9. PRINT RESULTS
# ============================================================

print("\n")
print("=" * 55)
print("          DEM + DINOv2 ANALYSIS")
print("=" * 55)

print(
    f"Mean Lake Elevation      : "
    f"{mean_lake_elevation:.2f} m"
)

print(
    f"Minimum Lake Elevation   : "
    f"{min_lake_elevation:.2f} m"
)

print(
    f"Maximum Lake Elevation   : "
    f"{max_lake_elevation:.2f} m"
)

print(
    f"Lake Elevation Range     : "
    f"{elevation_range:.2f} m"
)

print(
    f"Mean Lake Slope          : "
    f"{mean_lake_slope:.2f} degrees"
)

print(
    f"Mean Surrounding Elev.   : "
    f"{mean_surrounding_elevation:.2f} m"
)

print(
    f"Elevation Difference     : "
    f"{elevation_difference:.2f} m"
)

print("=" * 55)


# ============================================================
# 10. CREATE DEM + LAKE VISUALIZATION
# ============================================================

print("\nCreating visualization...")


fig, axes = plt.subplots(
    1,
    3,
    figsize=(18, 6)
)


# ------------------------------------------------------------
# DEM
# ------------------------------------------------------------

ax = axes[0]

dem_plot = ax.imshow(
    dem,
    cmap="terrain"
)

ax.set_title(
    "Copernicus DEM"
)

ax.set_xlabel("Pixel X")
ax.set_ylabel("Pixel Y")

plt.colorbar(
    dem_plot,
    ax=ax,
    label="Elevation (m)"
)


# ------------------------------------------------------------
# LAKE MASK
# ------------------------------------------------------------

ax = axes[1]

ax.imshow(
    lake_mask,
    cmap="Blues"
)

ax.set_title(
    "DINOv2 Predicted Lake"
)

ax.set_xlabel("Pixel X")
ax.set_ylabel("Pixel Y")


# ------------------------------------------------------------
# DEM + LAKE
# ------------------------------------------------------------

ax = axes[2]

ax.imshow(
    dem,
    cmap="terrain"
)

# Transparent lake overlay

lake_overlay = np.ma.masked_where(
    ~lake_mask,
    lake_mask
)

ax.imshow(
    lake_overlay,
    cmap="Blues",
    alpha=0.65
)

ax.set_title(
    "DEM + DINOv2 Lake Overlay"
)

ax.set_xlabel("Pixel X")
ax.set_ylabel("Pixel Y")


plt.suptitle(
    "Glacial Lake Terrain Analysis using DINOv2 + DEM",
    fontsize=16
)


plt.tight_layout()


# ============================================================
# 11. SAVE FIGURE
# ============================================================

plt.savefig(
    OUTPUT_FIGURE,
    dpi=300,
    bbox_inches="tight"
)


plt.show()


print(
    "\nFigure saved to:",
    OUTPUT_FIGURE
)