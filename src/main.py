from fastapi import FastAPI, HTTPException
import logging

from src.config import settings
from src.engine import extract_tree_canopies
from src.spatial_math import evaluate_vegetation_risk


logger = logging.getLogger(__name__)


app = FastAPI(
    title="Vegetation API",
    description="Analyze LiDAR point clouds to detect powerline encroachment risks.",
    version="1.0.0",
)

@app.get("/")
def health_check():
    return {"status": "Operational", "engine": "Ready for LiDAR processing"}


@app.post("/api/v1/analyze-risk")
def analyze_risk():
    """
    Triggers the end-to-end LiDAR processing pipeline.
    Extracts trees from COPC cloud URL, simulates a powerline, calculates spatial risk, 
    and returns a web-ready GeoJSON payload.
    """
    logger.info("Received request to analyze vegetation risk.")
    
    try:
        trees_gdf = extract_tree_canopies(settings.DEFAULT_COPC_URL)
        
        result_payload = evaluate_vegetation_risk(trees_gdf)
        
        return {
            "status": "success",
            "message": "Vegetation encroachment analysis complete.",
            "data": result_payload
        }
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal processing error.")