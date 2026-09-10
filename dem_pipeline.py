import os
import math
import requests
import rasterio
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# CONFIGURATION
# ============================================================

IMAGE_PATH = "input/image.tif"

DEM_DIR = "dem"
OUTPUT_DIR = "output"

os.makedirs(DEM_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 1. READ IMAGE GEOGRAPHIC INFORMATION
# ============================================================

def get_image_info(image_path):

    with rasterio.open(image_path) as src:

        bounds = src.bounds
        crs = src.crs
        width = src.width
        height = src.height
        resolution = src.res

        print("\n========== IMAGE INFORMATION ==========")
        print("Width       :", width)
        print("Height      :", height)
        print("CRS         :", crs)
        print("Resolution  :", resolution)

        print("\nBounds:")
        print("West        :", bounds.left)
        print("South       :", bounds.bottom)
        print("East        :", bounds.right)
        print("North       :", bounds.top)

        return bounds, crs


# ============================================================
# 2. DETERMINE COPERNICUS TILE
# ============================================================

def get_tile_coordinates(bounds):

    # DEM tiles are identified using their southwest corner.
    lon = math.floor(bounds.left)
    lat = math.floor(bounds.bottom)

    return lat, lon


def format_coordinate(value, positive_prefix, negative_prefix, width):

    if value >= 0:
        return f"{positive_prefix}{abs(value):0{width}d}"
    else:
        return f"{negative_prefix}{abs(value):0{width}d}"


def create_tile_name(lat, lon):

    lat_part = format_coordinate(
        lat,
        "N",
        "S",
        2
    )

    lon_part = format_coordinate(
        lon,
        "E",
        "W",
        3
    )

    return (
        f"Copernicus_DSM_COG_10_"
        f"{lat_part}_00_"
        f"{lon_part}_00_DEM"
    )


# ============================================================
# 3. DOWNLOAD COPERNICUS DEM
# ============================================================

def download_dem(lat, lon):

    tile_name = create_tile_name(lat, lon)

    print("\n========== DEM TILE ==========")
    print("Latitude tile :", lat)
    print("Longitude tile:", lon)
    print("Tile name     :", tile_name)

    base_url = (
        "https://copernicus-dem-30m.s3.amazonaws.com/"
    )

    filename = tile_name + ".tif"

    url = base_url + tile_name + "/" + filename

    output_path = os.path.join(
        DEM_DIR,
        filename
    )

    print("\nDEM URL:")
    print(url)

    if os.path.exists(output_path):

        print("\nDEM already exists:")
        print(output_path)

        return output_path

    print("\nDownloading DEM...")

    response = requests.get(
        url,
        stream=True,
        timeout=120
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"DEM download failed. "
            f"HTTP status: {response.status_code}"
        )

    total_size = int(
        response.headers.get(
            "content-length",
            0
        )
    )

    downloaded = 0

    with open(output_path, "wb") as f:

        for chunk in response.iter_content(
            chunk_size=1024 * 1024
        ):

            if chunk:

                f.write(chunk)

                downloaded += len(chunk)

                if total_size:

                    percent = (
                        downloaded /
                        total_size *
                        100
                    )

                    print(
                        f"\rDownloaded: {percent:.1f}%",
                        end=""
                    )

    print("\n\nDEM downloaded successfully.")
    print("Saved to:", output_path)

    return output_path


# ============================================================
# 4. INSPECT DEM
# ============================================================

def inspect_dem(dem_path):

    with rasterio.open(dem_path) as src:

        dem = src.read(1)

        print("\n========== DEM INFORMATION ==========")

        print("Width      :", src.width)
        print("Height     :", src.height)
        print("CRS        :", src.crs)
        print("Resolution :", src.res)
        print("Bounds     :", src.bounds)

        valid = dem[
            np.isfinite(dem)
        ]

        if src.nodata is not None:

            valid = valid[
                valid != src.nodata
            ]

        print("\nElevation statistics:")

        print(
            "Minimum:",
            np.min(valid),
            "m"
        )

        print(
            "Maximum:",
            np.max(valid),
            "m"
        )

        print(
            "Mean:",
            np.mean(valid),
            "m"
        )

        return dem


# ============================================================
# 5. VISUALIZE DEM
# ============================================================

def visualize_dem(dem_path):

    with rasterio.open(dem_path) as src:

        dem = src.read(1)

        if src.nodata is not None:

            dem = np.where(
                dem == src.nodata,
                np.nan,
                dem
            )

    plt.figure(
        figsize=(10, 8)
    )

    plt.imshow(
        dem,
        cmap="terrain"
    )

    plt.colorbar(
        label="Elevation (m)"
    )

    plt.title(
        "Copernicus GLO-30 DEM"
    )

    plt.xlabel("Pixel")
    plt.ylabel("Pixel")

    plt.tight_layout()

    output_path = os.path.join(
        OUTPUT_DIR,
        "dem_visualization.png"
    )

    plt.savefig(
        output_path,
        dpi=300
    )

    plt.close()

    print(
        "\nDEM visualization saved:"
    )

    print(output_path)


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "   GLACIAL LAKE DEM MODULE"
    )

    print(
        "======================================"
    )

    # Read image
    bounds, crs = get_image_info(
        IMAGE_PATH
    )

    # Determine DEM tile
    lat, lon = get_tile_coordinates(
        bounds
    )

    # Download DEM
    dem_path = download_dem(
        lat,
        lon
    )

    # Inspect DEM
    inspect_dem(
        dem_path
    )

    # Visualize DEM
    visualize_dem(
        dem_path
    )

    print(
        "\n======================================"
    )

    print(
        "DEM MODULE COMPLETED"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":

    main()