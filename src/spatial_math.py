import geopandas as gpd
from shapely.geometry import LineString
import json
import logging

from src.config import settings

logger = logging.getLogger(__name__)

def create_simulated_powerline(trees_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Creates a dummy powerline that diagonally crosses the bounding box 
    of our detected trees, so we have an asset to test against.
    """
    if trees_gdf.empty:
        return gpd.GeoDataFrame()

    bounds = trees_gdf.total_bounds 
    
    powerline_geom = LineString([
        (bounds[0], bounds[1]), 
        (bounds[2], bounds[3])
    ])
    
    powerline_gdf = gpd.GeoDataFrame(
        {'Asset_ID': ['LINE-001'], 'Type': ['High Voltage 100kV']}, 
        geometry=[powerline_geom], 
        crs=trees_gdf.crs
    )
    return powerline_gdf

def evaluate_vegetation_risk(trees_gdf: gpd.GeoDataFrame) -> dict:
    """
    Calculates the spatial distance from every tree to the powerline.
    Returns a dictionary containing both the trees and the line as GeoJSON.
    """
    logger.info("Evaluating vegetation encroachment risk...")
    
    if trees_gdf.empty:
        return {"trees": {}, "powerline": {}}

    powerline_gdf = create_simulated_powerline(trees_gdf)
    powerline_geom = powerline_gdf.geometry.iloc[0]

    trees_gdf['Distance_to_Line_m'] = trees_gdf.geometry.distance(powerline_geom).round(2)

    trees_gdf['Risk_Level'] = trees_gdf['Distance_to_Line_m'].apply(
        lambda dist: 'CRITICAL' if dist <= settings.CRITICAL_CLEARANCE_M else 'SAFE'
    )

    critical_count = len(trees_gdf[trees_gdf['Risk_Level'] == 'CRITICAL'])
    logger.info(f"Risk evaluation complete. Found {critical_count} CRITICAL trees.")

    trees_gdf_web = trees_gdf.to_crs("EPSG:4326")
    powerline_gdf_web = powerline_gdf.to_crs("EPSG:4326")

    powerline_gdf_web['stroke'] = '#ff0000'
    powerline_gdf_web['stroke-width'] = 4

    trees_gdf_web['fill'] = trees_gdf_web['Risk_Level'].apply(
        lambda risk: '#ff0000' if risk == 'CRITICAL' else '#00b300'
    )
    trees_gdf_web['stroke'] = trees_gdf_web['Risk_Level'].apply(
        lambda risk: '#cc0000' if risk == 'CRITICAL' else '#008000'
    )
    trees_gdf_web['fill-opacity'] = 0.6

    map_output_path = settings.OUTPUT_DIR / "final_risk_map.geojson"
    
    combined_gdf = gpd.pd.concat([trees_gdf_web, powerline_gdf_web])
    combined_gdf.to_file(map_output_path, driver="GeoJSON")
    logger.info(f" Saved styled web map to: {map_output_path}")

    return {
        "powerline": json.loads(powerline_gdf_web.to_json()),
        "trees": json.loads(trees_gdf_web.to_json())
    }