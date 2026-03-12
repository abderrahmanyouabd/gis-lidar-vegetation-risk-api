import pdal
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from sklearn.cluster import DBSCAN
import logging
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_tree_canopies(cloud_url: str = None) -> gpd.GeoDataFrame:
    """
    Ingests a LiDAR file via pure cloud streaming (COPC), extracts high vegetation, 
    groups points into individual trees using ML, and returns a GeoDataFrame.
    """
    if cloud_url is None:
        cloud_url = settings.DEFAULT_COPC_URL

    logger.info(f"Streaming LiDAR directly from cloud URL: {cloud_url}")
    
    pipeline_def = [
        {"type": "readers.copc", "filename": str(cloud_url)},
        
        {"type": "filters.smrf"},
        {"type": "filters.hag_nn"}, 

        # (ignore birds/noise > 300)
        {"type": "filters.range", "limits": f"HeightAboveGround[{settings.MIN_TREE_HEIGHT_M}:300]"}
    ]
    
    logger.info("Executing PDAL pipeline (Filtering & Height Calculation)...")
    pipeline = pdal.Pipeline(json.dumps(pipeline_def))
    

    point_count = pipeline.execute()
    
    if point_count == 0:
        logger.warning("No trees found matching the height criteria in this file.")
        return gpd.GeoDataFrame()

    points = pipeline.arrays[0]

    # DBSCAN Clustering
    logger.info("Running DBSCAN ML clustering to identify individual trees...")
    coords = np.vstack((points['X'], points['Y'], points['Z'])).transpose()
    
    clustering = DBSCAN(
        eps=settings.CLUSTER_EPSILON, 
        min_samples=settings.CLUSTER_MIN_SAMPLES
    ).fit(coords)
    
    df = pd.DataFrame({
        'X': points['X'], 
        'Y': points['Y'], 
        'HAG': points['HeightAboveGround'], 
        'Tree_ID': clustering.labels_
    })
    
    # Remove noise
    df = df[df['Tree_ID'] != -1]

    if df.empty:
         logger.warning("Clustering finished, but no distinct trees were formed.")
         return gpd.GeoDataFrame()


    logger.info("Vectorizing 3D clusters into 2D map polygons...")
    tree_canopies = []
    
    for tree_id, group in df.groupby('Tree_ID'):
        tree_points = [Point(x, y) for x, y in zip(group['X'], group['Y'])]
        

        canopy_polygon = MultiPoint(tree_points).convex_hull
        
        tree_canopies.append({
            'Tree_ID': int(tree_id),
            'Max_Height_m': round(group['HAG'].max(), 2),
            'geometry': canopy_polygon
        })


    gdf_trees = gpd.GeoDataFrame(tree_canopies, crs="EPSG:3857")
    
    logger.info(f"Extraction complete. Found {len(gdf_trees)} distinct tree canopies.")
    return gdf_trees