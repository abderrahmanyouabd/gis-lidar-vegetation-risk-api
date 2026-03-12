from fastapi import FastAPI, HTTPException
import logging
import json
import uuid
from pydantic import BaseModel
from kafka import KafkaProducer
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vegetation API",
    description="Analyze LiDAR point clouds to detect powerline encroachment risks (Event-Driven).",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"], # frontend's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


producer = None
try:
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.info("Successfully connected to Kafka Broker on localhost:9092")
except Exception as e:
    logger.error(f"Failed to connect to Kafka: {e}. Is Docker running?")



class LidarJobRequest(BaseModel):
    cloud_url: str = settings.DEFAULT_COPC_URL


@app.get("/")
def health_check():
    kafka_status = "Connected" if producer else "Disconnected"
    return {"status": "Operational", "engine": "Kafka Producer Ready", "kafka": kafka_status}


@app.post("/api/v1/analyze-risk")
def analyze_risk(request: LidarJobRequest):
    """
    Lightning-fast async endpoint. 
    Drops the LiDAR job onto the Kafka queue for background processing.
    """
    logger.info(f"Received request to queue vegetation risk analysis for: {request.cloud_url}")
    
    if not producer:
        raise HTTPException(status_code=503, detail="Kafka broker is not available.")
    
    try:
        job_id = str(uuid.uuid4())
        
        kafka_message = {
            "job_id": job_id,
            "cloud_url": request.cloud_url,
            "status": "queued"
        }
        
        producer.send('lidar-jobs', kafka_message)
        producer.flush()
        
        logger.info(f"Job {job_id} successfully dropped onto Kafka queue.")
        
        return {
            "status": "success",
            "message": "Job successfully added to the processing queue.",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error(f"Failed to queue job: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal queuing error.")


@app.get("/api/v1/jobs/{job_id}")
def get_job_result(job_id: str):
    """
    Fetches the completed 3D map from MongoDB so the frontend can render it.
    """
    try:
        mongo_client = MongoClient("mongodb://localhost:27017/")
        db = mongo_client["gis_pipeline"]
        collection = db["risk_analyses"]
        
        job_data = collection.find_one({"job_id": job_id})
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found.")
            
        if job_data["status"] != "completed":
            return {"job_id": job_id, "status": job_data["status"]}
            
        del job_data["_id"]
        
        return job_data
        
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id} from database: {e}")
        raise HTTPException(status_code=500, detail="Database connection error.")