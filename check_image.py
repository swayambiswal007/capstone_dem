import rasterio

IMAGE = "input/image.tif"

with rasterio.open(IMAGE) as src:
    print("========== IMAGE INFO ==========")
    print("Width:", src.width)
    print("Height:", src.height)
    print("Bands:", src.count)
    print("CRS:", src.crs)
    print("Bounds:", src.bounds)
    print("Transform:", src.transform)
    print("Resolution:", src.res)