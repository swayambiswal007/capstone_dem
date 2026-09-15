from flask import Flask, jsonify, render_template, send_file, abort
import os, json, io, math
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from PIL import Image
from scipy import ndimage

app = Flask(__name__)
BASE=os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE,'scenes.json')) as f: SCENES=json.load(f)
IMG_DIR=os.path.join(BASE,'data','images'); LAB_DIR=os.path.join(BASE,'data','labels'); DEM_DIR=os.path.join(BASE,'dem')

# Public Copernicus GLO-30 COG URL template. If a tile is already placed in dem/, it is used first.
DEM_URL='https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif'


def scene_by_id(sid):
    return next((s for s in SCENES if s['id']==sid), None)

def safe(a):
    a=np.asarray(a,dtype=float)
    a[~np.isfinite(a)]=np.nan
    return a

def local_dem_path(tile_lat,tile_lon):
    fn=f'Copernicus_DSM_COG_10_N{tile_lat:02d}_00_E{tile_lon:03d}_00_DEM.tif'
    return os.path.join(DEM_DIR,fn)

def dem_source(bounds):
    lat=math.floor(bounds[1]); lon=math.floor(bounds[0])
    local=local_dem_path(lat,lon)
    if os.path.exists(local): return local, 'Local Copernicus GLO-30 tile'
    return '/vsicurl/'+DEM_URL.format(lat=lat,lon=lon), 'Copernicus GLO-30 (public COG)'

def read_image(scene):
    with rasterio.open(os.path.join(IMG_DIR,scene['file'])) as src:
        arr=src.read()
        profile=src.profile
    if arr.shape[0]>=3:
        rgb=np.moveaxis(arr[:3],0,-1).astype(float)
    else:
        rgb=np.repeat(arr[0][...,None],3,axis=2).astype(float)
    out=np.zeros_like(rgb,dtype=np.uint8)
    for c in range(3):
        band=rgb[...,c]; lo,hi=np.nanpercentile(band,[2,98])
        out[...,c]=np.clip((band-lo)/(hi-lo+1e-9)*255,0,255)
    return out, profile

def read_label(scene):
    with rasterio.open(os.path.join(LAB_DIR,scene['label_file'])) as src:
        a=src.read(1)
        profile=src.profile
    # Dataset labels may be 0/1 or 0/255.
    return (a>0).astype(np.uint8), profile

def aligned_mask_and_dem(scene):
    mask, mprof=read_label(scene)
    with rasterio.open(os.path.join(IMG_DIR,scene['file'])) as img:
        ibounds=img.bounds; icrs=img.crs; ih,iw=img.height,img.width
    src_path, source_name=dem_source([ibounds.left,ibounds.bottom,ibounds.right,ibounds.top])
    with rasterio.open(src_path) as dem:
        # Read only a small window around the scene, with padding.
        padx=(ibounds.right-ibounds.left)*0.25; pady=(ibounds.top-ibounds.bottom)*0.25
        win=from_bounds(ibounds.left-padx,ibounds.bottom-pady,ibounds.right+padx,ibounds.top+pady,dem.transform)
        win=win.round_offsets().round_lengths()
        data=dem.read(1,window=win,boundless=True,fill_value=np.nan).astype('float32')
        tr=dem.window_transform(win); crs=dem.crs
    # Reproject DEM to image grid so each lake pixel gets terrain value.
    aligned=np.full((ih,iw),np.nan,dtype='float32')
    reproject(data,aligned,src_transform=tr,src_crs=crs,dst_transform=mprof['transform'],dst_crs=icrs,resampling=Resampling.bilinear,src_nodata=np.nan,dst_nodata=np.nan)
    return mask,aligned,source_name

def terrain_metrics(scene, mask, dem):
    valid=np.isfinite(dem); lake=mask.astype(bool)&valid
    if not lake.any(): raise RuntimeError('No valid DEM cells overlap the reference lake mask.')
    elev=dem[lake]
    # Gradient in geographic coordinates; converted approximately to metres for a presentation metric.
    with rasterio.open(os.path.join(IMG_DIR,scene['file'])) as src:
        px=abs(src.transform.a)*111320*np.cos(np.deg2rad(np.nanmean(dem[lake])*0+30))
        py=abs(src.transform.e)*111320
    gy,gx=np.gradient(dem,py,px)
    slope=np.degrees(np.arctan(np.sqrt(gx*gx+gy*gy)))
    # Surrounding terrain: ~8 image pixels, roughly 240 m at 30m data scale.
    dil=ndimage.binary_dilation(mask.astype(bool),iterations=8)
    ring=dil & (~mask.astype(bool)) & valid
    mean_sur=float(np.nanmean(dem[ring])) if ring.any() else float(np.nanmean(dem[valid]))
    mean_lake=float(np.nanmean(elev)); diff=abs(mean_sur-mean_lake)
    area=float(lake.sum()*900.0)  # approx 30m x 30m
    return {'mean_elevation':mean_lake,'min_elevation':float(np.nanmin(elev)),'max_elevation':float(np.nanmax(elev)),
            'mean_slope':float(np.nanmean(slope[lake])),'surrounding_elevation':mean_sur,
            'elevation_difference':diff,'lake_pixels':int(lake.sum()),'area_m2':area,
            'coverage_pct':float(lake.sum()/(mask.shape[0]*mask.shape[1])*100)}

def json_grid(a):
    a=np.asarray(a)
    return [[None if not np.isfinite(v) else float(v) for v in row] for row in a]

def crop_terrain(scene,dem,mask):
    valid=np.isfinite(dem)
    ys,xs=np.where(mask.astype(bool)&valid)
    if len(xs)==0: ys,xs=np.where(valid)
    y0=max(0,int(ys.min())-70); y1=min(dem.shape[0],int(ys.max())+71)
    x0=max(0,int(xs.min())-70); x1=min(dem.shape[1],int(xs.max())+71)
    d=dem[y0:y1,x0:x1]; m=mask[y0:y1,x0:x1].astype(bool)
    # downsample for browser payload
    maxside=170; sy=max(1,int(np.ceil(max(d.shape)/maxside)))
    d=d[::sy,::sy]; m=m[::sy,::sy]
    h,w=d.shape
    yy,xx=np.mgrid[0:h,0:w]
    z=d.copy(); z[~np.isfinite(z)]=np.nan
    lakez=np.where(m,z,np.nan)
    return {'x':xx.tolist(),'y':yy.tolist(),'z':json_grid(z),'lake_z':json_grid(lakez)}

def img_data_uri(arr):
    im=Image.fromarray(arr,'RGB'); bio=io.BytesIO(); im.save(bio,'PNG',optimize=True)
    import base64
    return 'data:image/png;base64,'+base64.b64encode(bio.getvalue()).decode()

def overlay(arr,mask):
    out=arr.copy().astype(np.uint8)
    edge=ndimage.binary_dilation(mask,iterations=1)^ndimage.binary_erosion(mask,iterations=1)
    out[edge]=[0,255,230]
    return out

@app.route('/')
def index(): return render_template('index.html')
@app.route('/api/scenes')
def scenes(): return jsonify(SCENES)
@app.route('/api/image/<sid>')
def image(sid):
    s=scene_by_id(sid)
    if not s: abort(404)
    arr,_=read_image(s); return jsonify({'image':img_data_uri(arr)})

@app.route('/api/scene/<sid>')
def scene(sid):
    s=scene_by_id(sid)
    if not s: abort(404)
    try:
        rgb,_=read_image(s); mask,_=read_label(s); mask,dem,source=aligned_mask_and_dem(s)
        met=terrain_metrics(s,mask,dem); terr=crop_terrain(s,dem,mask)
        # Blueprint is the actual reference mask footprint, not a fabricated shape.
        by,bx=np.where(mask.astype(bool))
        if len(bx):
            minx,maxx,miny,maxy=bx.min(),bx.max(),by.min(),by.max()
            bp={'width_px':int(maxx-minx+1),'length_px':int(maxy-miny+1),'mask_pixels':int(mask.sum())}
        else: bp={'width_px':0,'length_px':0,'mask_pixels':0}
        return jsonify({'scene':s,'source':source,'metrics':met,'image':img_data_uri(rgb),
                        'reference_overlay':img_data_uri(overlay(rgb,mask)),
                        'terrain':terr,'blueprint':bp,'prediction_status':'Reference label loaded — replace with DINOv2 output when prediction.tif is available.'})
    except Exception as e:
        return jsonify({'error':str(e),'scene':s,'hint':'Place the matching Copernicus DEM tile in dem/ or run with internet access so the public COG can be read.'}),503

@app.route('/api/blueprint/<sid>')
def blueprint(sid):
    # compatibility endpoint
    r=scene(sid); return r

@app.route('/api/predict')
def predict():
    return jsonify({'status':'demo','score':72,'level':'Moderate–High','message':'Temporal predictor UI is connected as a presentation stub. Connect your trained temporal model here.'})

if __name__=='__main__': app.run(host='0.0.0.0',port=5000,debug=True)
