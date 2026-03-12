import json
import logging
from kafka import KafkaConsumer
from pymongo import MongoClient

from src.engine import extract_tree_canopies
from src.spatial_math import evaluate_vegetation_risk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_worker():
    logger.info("Starting Background LiDAR Worker...")

    try:
        mongo_client = MongoClient("mongodb://localhost:27017/")
        db = mongo_client["gis_pipeline"]
        collection = db["risk_analyses"]
        logger.info("Connected to MongoDB.")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return

    try:
        consumer = KafkaConsumer(
            'lidar-jobs',
            bootstrap_servers=['localhost:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id='lidar-workers',
            max_poll_interval_ms=3600000,
            session_timeout_ms=60000,
            heartbeat_interval_ms=20000,
        )
        logger.info("Connected to Kafka. Listening for jobs on 'lidar-jobs' topic...")
    except Exception as e:
        logger.error(f"Kafka connection failed: {e}")
        return

    for message in consumer:
        job_data = message.value
        job_id = job_data.get("job_id")
        cloud_url = job_data.get("cloud_url")
        
        logger.info(f"Picked up Job {job_id} from the queue. Processing URL: {cloud_url}")
        
        try:
            trees_gdf = extract_tree_canopies(cloud_url)
            
            result_payload = evaluate_vegetation_risk(trees_gdf)
            
            db_document = {
                "job_id": job_id,
                "cloud_url": cloud_url,
                "status": "completed",
                "result": result_payload
            }
            
            collection.insert_one(db_document)
            logger.info(f"Successfully saved Job {job_id} to MongoDB!")
            
        except Exception as e:
            logger.error(f"Failed to process Job {job_id}: {e}")
            collection.insert_one({
                "job_id": job_id,
                "status": "failed",
                "error": str(e)
            })

if __name__ == "__main__":
    start_worker()