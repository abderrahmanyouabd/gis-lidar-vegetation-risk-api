import pdal
import json
import logging
from typing import Optional
import pyproj
import geopandas as gpd

from src.config import settings

logger = logging.getLogger(__name__)


def detect_crs_from_copc(cloud_url: str) -> Optional[str]:
    """
    Detect CRS from COPC file metadata using PDAL.
    Returns the CRS as an EPSG string (e.g., 'EPSG:4326') or None if detection fails.
    """
    try:
        pipeline_def = [{"type": "readers.copc", "filename": str(cloud_url)}]
        pipeline = pdal.Pipeline(json.dumps(pipeline_def))
        
        pipeline.execute()
        
        spatial_ref = pipeline.metadata.get("metadata", {}).get("PDAL", {}).get("spatial_ref", {})
        wkt_string = spatial_ref.get("wkt", "")
        
        if not wkt_string:
            logger.warning(f"Could not extract WKT from COPC metadata for {cloud_url}")
            return None
        
        crs_obj = pyproj.CRS.from_wkt(wkt_string)
        
        epsg = crs_obj.to_epsg()
        if epsg:
            crs_string = f"EPSG:{epsg}"
            logger.info(f"Detected CRS from COPC: {crs_string}")
            return crs_string
        
        authority_name = crs_obj.name if crs_obj.name else "Unknown"
        logger.warning(f"COPC CRS has no EPSG code: {authority_name}. WKT: {wkt_string[:100]}...")
        return None
        
    except Exception as e:
        logger.warning(f"Failed to detect CRS from COPC: {e}")
        return None


def is_projected_crs(crs_string: str) -> bool:
    """
    Check if a CRS is projected (meter-based) vs geographic (degree-based).
    Returns True if the CRS uses meters, False if degrees.
    """
    try:
        crs_obj = pyproj.CRS(crs_string)
        return crs_obj.is_projected
    except Exception as e:
        logger.warning(f"Failed to validate CRS '{crs_string}': {e}")
        return False


def get_crs_units(crs_string: str) -> str:
    """
    Get the units of a CRS (meters, degrees, feet, etc.).
    """
    try:
        crs_obj = pyproj.CRS(crs_string)
        if crs_obj.axis_info:
            unit = crs_obj.axis_info[0].unit
            if hasattr(unit, 'name'):
                return unit.name
            elif hasattr(unit, 'units'):
                return str(unit.units)
            return str(unit)
        return "unknown"
    except Exception as e:
        return "unknown"


def reproject_gdf(gdf: gpd.GeoDataFrame, target_crs: str) -> gpd.GeoDataFrame:
    """
    Reproject a GeoDataFrame to the target CRS.
    Returns a new GeoDataFrame with the target CRS.
    """
    if gdf.crs is None:
        raise ValueError("Cannot reproject GeoDataFrame with no CRS. Set CRS first.")
    
    if gdf.crs.to_string() == target_crs:
        logger.info(f"GeoDataFrame already in target CRS {target_crs}, skipping reprojection")
        return gdf
    
    logger.info(f"Reprojecting from {gdf.crs.to_string()} to {target_crs}")
    return gdf.to_crs(target_crs)


def validate_crs_for_analysis(crs_string: str, target_crs: str) -> tuple[bool, str]:
    """
    Validate that a CRS is suitable for spatial analysis (DBSCAN with meter-based eps).
    
    Returns:
        tuple: (is_valid, message)
    """
    if not is_projected_crs(crs_string):
        units = get_crs_units(crs_string)
        return False, f"CRS {crs_string} is geographic (units: {units}). Must reproject to projected CRS (e.g., {target_crs}) for accurate distance-based analysis."
    
    return True, f"CRS {crs_string} is projected and suitable for analysis."


def get_working_crs(cloud_url: str, target_crs: str = None) -> tuple[str, str, str]:
    """
    Determine the working CRS for processing.
    
    Priority:
    1. Auto-detect from COPC metadata
    2. Use configured TARGET_CRS as fallback
    
    Args:
        cloud_url: URL to COPC file
        target_crs: Target CRS to use (defaults to settings.TARGET_CRS)
    
    Returns:
        tuple: (working_crs, source_crs, source_info)
            - working_crs: The CRS to use for processing
            - source_crs: The detected CRS from COPC (or fallback)
            - source_info: Description of where the CRS came from
    """
    if target_crs is None:
        target_crs = settings.TARGET_CRS
    
    if not settings.AUTO_DETECT_CRS:
        logger.info(f"AUTO_DETECT_CRS disabled. Using TARGET_CRS: {target_crs}")
        return target_crs, target_crs, f"config:TARGET_CRS={target_crs}"
    
    detected_crs = detect_crs_from_copc(cloud_url)
    source_crs = detected_crs if detected_crs else target_crs
    
    if detected_crs:
        is_valid, message = validate_crs_for_analysis(detected_crs, target_crs)
        
        if is_valid:
            if detected_crs == target_crs:
                return detected_crs, detected_crs, f"detected:{detected_crs} (matches TARGET_CRS)"
            else:
                logger.info(f"Detected CRS {detected_crs} differs from TARGET_CRS {target_crs}. Will reproject.")
                return target_crs, detected_crs, f"detected:{detected_crs} -> reprojecting to {target_crs}"
        else:
            logger.warning(message)
            return target_crs, detected_crs, f"detected:{detected_crs} (invalid for analysis) -> using {target_crs}"
    
    logger.warning(f"Could not detect CRS from COPC. Using TARGET_CRS: {target_crs}")
    return target_crs, target_crs, f"fallback:TARGET_CRS={target_crs}"
