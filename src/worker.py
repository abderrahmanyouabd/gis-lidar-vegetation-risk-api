import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from pymongo import MongoClient

from src.engine import extract_tree_canopies
from src.spatial_math import evaluate_vegetation_risk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

status_producer = None
try:
    status_producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.info("Worker: Connected to Kafka for status events")
except Exception as e:
    logger.error(f"Worker: Failed to connect status producer: {e}")


def publish_status(job_id: str, status: str, message: str = ""):
    """Publish job status event to Kafka for WebSocket broadcast."""
    if not status_producer:
        return
    
    event = {
        "job_id": job_id,
        "status": status,
        "message": message
    }
    
    status_producer.send('job-status-events', event)
    status_producer.flush()
    logger.info(f"Worker: Published status '{status}' for job {job_id}")

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
            # Save job to MongoDB at START so late WebSocket connections can see current status
            collection.insert_one({
                "job_id": job_id,
                "cloud_url": cloud_url,
                "status": "processing",
                "message": "Job started processing"
            })
            logger.info(f"Worker: Created MongoDB entry for job {job_id} with status 'processing'")
            
            publish_status(job_id, "processing", "Downloading and filtering LiDAR data...")
            
            trees_gdf = extract_tree_canopies(cloud_url)
            publish_status(job_id, "processing", "Running ML clustering to identify trees...")
            
            result_payload = evaluate_vegetation_risk(trees_gdf)
            publish_status(job_id, "processing", "Calculating vegetation risk...")
            
            db_document = {
                "job_id": job_id,
                "cloud_url": cloud_url,
                "status": "completed",
                "result": result_payload
            }
            
            collection.insert_one(db_document)
            publish_status(job_id, "completed", "Job completed successfully!")
            logger.info(f"Successfully saved Job {job_id} to MongoDB!")
            
        except Exception as e:
            logger.error(f"Failed to process Job {job_id}: {e}")
            collection.insert_one({
                "job_id": job_id,
                "status": "failed",
                "error": str(e)
            })
            publish_status(job_id, "failed", f"Error: {str(e)}")

if __name__ == "__main__":
    start_worker()