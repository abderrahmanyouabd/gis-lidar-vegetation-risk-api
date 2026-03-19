import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point
import numpy as np
import json
import logging

from src.config import settings

logger = logging.getLogger(__name__)


def _build_powerline_from_conductors(conductor_pts: np.ndarray,
                                      crs: str) -> gpd.GeoDataFrame:
    """
    Builds a real 3D LineString from ASPRS class 14 wire conductor points.
    Points are sorted by X to form a coherent line.
    Returns a GeoDataFrame in the same CRS as the trees.
    """
    if len(conductor_pts) == 0:
        return gpd.GeoDataFrame()


    sorted_idx = np.argsort(conductor_pts['X'])
    xs = conductor_pts['X'][sorted_idx]
    ys = conductor_pts['Y'][sorted_idx]
    zs = conductor_pts['Z'][sorted_idx]


    step = max(1, len(xs) // 500)
    wire_coords = list(zip(xs[::step].tolist(),
                           ys[::step].tolist(),
                           zs[::step].tolist()))

    if len(wire_coords) < 2:
        return gpd.GeoDataFrame()

    powerline_gdf = gpd.GeoDataFrame(
        {'Asset_ID': ['LINE-001'], 'Type': ['Conductor (class 14)'],
         'source': ['lidar_class_14']},
        geometry=[LineString(wire_coords)],
        crs=crs
    )
    logger.info(f"Built real powerline from {len(wire_coords)} conductor points")
    return powerline_gdf


def _build_simulated_powerline(trees_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fallback: diagonal line across the tree bounding box at fixed Z=35m.
    Only used when no class 14 conductor points exist in the scan.
    """
    bounds = trees_gdf.total_bounds
    avg_ground_z = trees_gdf['ground_z_m'].mean() if 'ground_z_m' in trees_gdf.columns else 0.0
    # wire_z = avg_ground_z + 35.0  # 35m above average ground
    wire_z = 35.0  # since I will use basemap not terrain


    powerline_gdf = gpd.GeoDataFrame(
        {'Asset_ID': ['LINE-001'], 'Type': ['Simulated 100kV'],
         'source': ['simulated']},
        geometry=[LineString([
            (bounds[0], bounds[1], wire_z),
            (bounds[2], bounds[3], wire_z)
        ])],
        crs=trees_gdf.crs
    )
    logger.warning("No conductor points found — using simulated powerline")
    return powerline_gdf


def evaluate_vegetation_risk(trees_gdf: gpd.GeoDataFrame, progress_callback=None) -> dict:
    if progress_callback:
        progress_callback("Stage 4/4: Calculating vegetation encroachment risk")

    logger.info("Evaluating vegetation encroachment risk...")
    
    if trees_gdf.empty:
        return {"trees": {}, "powerline": {}}

    # Build powerline from real conductors or fall back
    conductor_pts = trees_gdf.attrs.get('conductor_pts', np.array([]))

    if len(conductor_pts) > 0:
        powerline_gdf = _build_powerline_from_conductors(conductor_pts, trees_gdf.crs)
    else:
        powerline_gdf = gpd.GeoDataFrame()

    if powerline_gdf.empty:
        powerline_gdf = _build_simulated_powerline(trees_gdf)

    powerline_geom_2d = powerline_gdf.geometry.iloc[0]


    # 2D distance (XY only) with vertical clearance handled separately
    trees_gdf['Distance_to_Line_m'] = trees_gdf.geometry.distance(
        powerline_geom_2d
    ).round(2)

    trees_gdf['Risk_Level'] = trees_gdf['Distance_to_Line_m'].apply(
        lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                  else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                  else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                  else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                  else 'SAFE'
    )

    critical_count = len(trees_gdf[trees_gdf['Risk_Level'] == 'CRITICAL'])
    logger.info(f"Risk evaluation complete. Found {critical_count} CRITICAL trees.")

    # Reproject to WGS84 for frontend
    trees_web      = trees_gdf.to_crs("EPSG:4326")
    powerline_web  = powerline_gdf.to_crs("EPSG:4326")

    # Save combined GeoJSON
    map_output_path = settings.OUTPUT_DIR / "final_risk_map.geojson"
    combined = gpd.pd.concat([trees_web, powerline_web])
    combined.to_file(map_output_path, driver="GeoJSON")
    logger.info(f"Saved styled web map to: {map_output_path}")

    # Build metadata block for the frontend
    source_crs = trees_gdf.attrs.get('source_crs', 'unknown')
    working_crs = trees_gdf.attrs.get('working_crs', 'unknown')
    
    metadata = {
        "horizontal_crs": "EPSG:4326",
        "vertical_datum": "HAG (Height Above Ground, SMRF-derived)",
        "powerline_source": powerline_gdf['source'].iloc[0],
        "units": "meters",
        "processing_crs": working_crs,
        "source_crs": source_crs
    }

    return {
        "powerline": json.loads(powerline_web.to_json()),
        "trees":     json.loads(trees_web.to_json()),
        "metadata":  metadata
    }