import pdal
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from sklearn.cluster import DBSCAN
from scipy.spatial import cKDTree
import pyproj
import logging
from src.config import settings
from src.crs_utils import get_working_crs, reproject_gdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_ground_and_conductor_pipeline(cloud_url: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Second lightweight pipeline — pulls only ground (class 2) and
    wire conductor (class 14) points. These are small point sets
    so the download is fast.
    """
    pipeline_def = [
    {"type": "readers.copc", "filename": str(cloud_url)},

    {"type": "filters.range", "limits": "Classification[2:2]"},
    ]
    pipeline = pdal.Pipeline(json.dumps(pipeline_def))
    pipeline.execute()
    ground_pts = pipeline.arrays[0] if pipeline.arrays else np.array([])

    pipeline_def[1] = {"type": "filters.range", "limits": "Classification[14:14]"}
    pipeline = pdal.Pipeline(json.dumps(pipeline_def))
    pipeline.execute()
    conductor_pts = pipeline.arrays[0] if pipeline.arrays else np.array([])

    return ground_pts, conductor_pts


def extract_tree_canopies(cloud_url: str = None, progress_callback=None) -> gpd.GeoDataFrame:
    def report(msg):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    if cloud_url is None:
        cloud_url = settings.DEFAULT_COPC_URL

    logger.info(f"Streaming LiDAR directly from cloud URL: {cloud_url}")

    working_crs, source_crs, crs_source = get_working_crs(cloud_url)
    logger.info(f"CRS determined for processing: {working_crs} (source: {crs_source})")
    report(f"Using CRS: {working_crs}")

    report("Stage 1/4: Downloading and filtering LiDAR data")

    pipeline_def = [
        {"type": "readers.copc", "filename": str(cloud_url)},
        {"type": "filters.smrf"},
        {"type": "filters.hag_nn"},
        {"type": "filters.range",
         "limits": f"HeightAboveGround[{settings.MIN_TREE_HEIGHT_M}:300]"}
    ]
    pipeline = pdal.Pipeline(json.dumps(pipeline_def))
    point_count = pipeline.execute()

    if point_count == 0:
        logger.warning("No vegetation points found.")
        return gpd.GeoDataFrame()

    veg_points = pipeline.arrays[0]

    # Pull ground + conductor
    ground_pts, conductor_pts = _run_ground_and_conductor_pipeline(cloud_url)

    ground_tree = None
    if len(ground_pts) > 0:
        ground_xy = np.vstack((ground_pts['X'], ground_pts['Y'])).T
        ground_z  = ground_pts['Z']
        ground_tree = cKDTree(ground_xy)
        logger.info(f"Ground surface: {len(ground_pts):,} points loaded for elevation sampling")
    else:
        logger.warning("No ground (class 2) points found — ground_z_m will be 0")

    report("Stage 2/4: Running ML clustering to identify trees")

    coords = np.vstack((veg_points['X'], veg_points['Y'], veg_points['Z'])).T
    clustering = DBSCAN(
        eps=settings.CLUSTER_EPSILON,
        min_samples=settings.CLUSTER_MIN_SAMPLES
    ).fit(coords)

    df = pd.DataFrame({
        'X':   veg_points['X'],
        'Y':   veg_points['Y'],
        'Z':   veg_points['Z'],
        'HAG': veg_points['HeightAboveGround'],
        'Tree_ID': clustering.labels_
    })
    df = df[df['Tree_ID'] != -1]

    if df.empty:
        logger.warning("Clustering produced no distinct trees.")
        return gpd.GeoDataFrame()

    report("Stage 3/4: Vectorizing 3D clusters into 2D map polygons")

    tree_canopies = []

    for tree_id, group in df.groupby('Tree_ID'):
        canopy_polygon = MultiPoint(
            [Point(x, y) for x, y in zip(group['X'], group['Y'])]
        ).convex_hull

        cx, cy = canopy_polygon.centroid.x, canopy_polygon.centroid.y
        ground_z_m = 0.0
        if ground_tree is not None:
            _, idx = ground_tree.query([cx, cy])
            ground_z_m = float(ground_z[idx])

        hag_max    = round(float(group['HAG'].max()), 2)
        top_z_m    = round(ground_z_m + hag_max, 2)

        tree_canopies.append({
            'Tree_ID':      int(tree_id),
            'Max_Height_m': hag_max,
            'ground_z_m':   round(ground_z_m, 2),
            'top_z_m':      top_z_m,
            'Point_Count':  len(group),
            'geometry':     canopy_polygon
        })

    gdf_trees = gpd.GeoDataFrame(tree_canopies, crs=source_crs)

    if source_crs != working_crs:
        logger.info(f"Reprojecting from {source_crs} to {working_crs} for analysis")
        gdf_trees = reproject_gdf(gdf_trees, working_crs)

    gdf_trees.attrs['conductor_pts'] = conductor_pts
    gdf_trees.attrs['source_crs'] = source_crs
    gdf_trees.attrs['working_crs'] = working_crs

    logger.info(f"Extraction complete. Found {len(gdf_trees)} distinct tree canopies.")
    return gdf_trees