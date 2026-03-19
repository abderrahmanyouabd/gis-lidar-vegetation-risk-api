from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
import logging
import json
import uuid
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime
from pydantic import BaseModel
from kafka import KafkaProducer
from aiokafka import AIOKafkaConsumer
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from src.config import settings


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time job status updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket client connected for job: {job_id}")
    
    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
            logger.info(f"WebSocket client disconnected for job: {job_id}")
    
    async def send_message(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to client: {e}")


manager = ConnectionManager()

# Global references to keep the task alive
kafka_consumer_task: asyncio.Task = None
kafka_consumer: AIOKafkaConsumer = None
kafka_consumer_running = False


# mongo global vars
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["gis_pipeline"]
collection = db["risk_analyses"]


async def kafka_status_consumer():
    """Background task that consumes job status events from Kafka and pushes to WebSocket clients."""
    global kafka_consumer, kafka_consumer_running
    logger.info("Kafka consumer: Starting...")
    
    while kafka_consumer_running:
        try:
            logger.info("Kafka consumer: Creating connection...")
            kafka_consumer = AIOKafkaConsumer(
                'job-status-events',
                bootstrap_servers='localhost:9092',
                group_id='websocket-broadcast',
                auto_offset_reset='earliest',
            )
            logger.info("Kafka consumer: Connecting to broker...")
            await kafka_consumer.start()
            logger.info("Kafka consumer: Successfully connected! Listening on 'job-status-events' topic")
            
            async for message in kafka_consumer:
                if not kafka_consumer_running:
                    break
                try:
                    event = json.loads(message.value.decode('utf-8'))
                    job_id = event.get("job_id")
                    logger.info(f"Kafka consumer: Got message for job {job_id}: {event.get('status')}")
                    if job_id:
                        await manager.send_message(job_id, event)
                except Exception as e:
                    logger.error(f"Kafka consumer: Error processing message: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Kafka consumer: Cancelled")
            break
        except Exception as e:
            logger.error(f"Kafka consumer: Error: {e}. Reconnecting in 5 seconds...")
            if kafka_consumer_running:
                await asyncio.sleep(5)
        finally:
            if kafka_consumer:
                try:
                    await kafka_consumer.stop()
                    logger.info("Kafka consumer: Stopped")
                except Exception as e:
                    logger.error(f"Error stopping consumer: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to start/stop background tasks."""
    global kafka_consumer_task, kafka_consumer_running
    
    # StartUP
    kafka_consumer_running = True
    kafka_consumer_task = asyncio.create_task(kafka_status_consumer())
    yield  # Application runs
    
    # Shutdown
    kafka_consumer_running = False
    if kafka_consumer_task:
        kafka_consumer_task.cancel()
        try:
            await kafka_consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("Kafka consumer task stopped")

    mongo_client.close()
    logger.info("MongoDB connection closed")

app = FastAPI(
    title="Vegetation API",
    description="Analyze LiDAR point clouds to detect powerline encroachment risks (Event-Driven).",
    version="1.0.0",
    lifespan=lifespan,
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


class JobListItem(BaseModel):
    job_id: str
    cloud_url: Optional[str] = None
    status: str
    message: Optional[str] = None
    created_at: Optional[datetime] = None


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class JobListResponse(BaseModel):
    jobs: List[JobListItem]
    pagination: PaginationInfo


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
        
        status_event = {
            "job_id": job_id,
            "status": "queued",
            "message": "Job has been queued for processing"
        }
        
        producer.send('lidar-jobs', kafka_message)
        producer.send('job-status-events', status_event)
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
        job_data = collection.find_one({"job_id": job_id})
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found.")
            
        if job_data["status"] != "completed":
            return {"job_id": job_id, "status": job_data["status"]}
            
        del job_data["_id"]
        
        return job_data
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is (don't convert to 500)
        raise
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id} from database: {e}")
        raise HTTPException(status_code=500, detail="Database connection error.")


@app.get("/api/v1/jobs", response_model=JobListResponse)
def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    List all jobs with their status for the job history panel.
    Returns paginated list of jobs sorted by creation time (newest first).
    """
    try:
        total = collection.count_documents({})
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        skip = (page - 1) * limit

        cursor = collection.find(
            {},
            {"result": 0, "error": 0}
        ).sort("created_at", -1).skip(skip).limit(limit)

        jobs = []
        for job_data in cursor:
            jobs.append(JobListItem(
                job_id=job_data.get("job_id"),
                cloud_url=job_data.get("cloud_url"),
                status=job_data.get("status"),
                message=job_data.get("message"),
                created_at=job_data.get("created_at")
            ))

        return JobListResponse(
            jobs=jobs,
            pagination=PaginationInfo(
                page=page,
                limit=limit,
                total=total,
                total_pages=total_pages
            )
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail="Database connection error.")


@app.delete("/api/v1/jobs/{job_id}")
def cancel_job(job_id: str):
    """
    Cancel a running or queued job.
    Updates the job status to 'cancelled' and broadcasts the change via Kafka.
    """
    try:
        job_data = collection.find_one({"job_id": job_id})

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found.")

        current_status = job_data.get("status")

        if current_status in ("completed", "failed"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel a job that is already {current_status}."
            )

        if current_status == "cancelled":
            raise HTTPException(
                status_code=400,
                detail="Job is already cancelled."
            )

        collection.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "cancelled",
                "message": "Job cancelled by user"
            }}
        )

        status_event = {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled by user"
        }
        producer.send('job-status-events', status_event)
        producer.flush()

        logger.info(f"Job {job_id} cancelled successfully.")

        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Database connection error.")


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job status updates.
    Clients connect with their job_id to receive live progress notifications.
    """
    await manager.connect(job_id, websocket)
    
    # Send current job status immediately when client connects (catch-up for late connections)
    try:
        job_data = collection.find_one({"job_id": job_id})
        
        if job_data:
            # Send current status to the newly connected client
            catch_up_message = {
                "job_id": job_id,
                "status": job_data.get("status", "unknown"),
                "message": job_data.get("message", f"Current status: {job_data.get('status')}")
            }
            await websocket.send_json(catch_up_message)
            logger.info(f"Sent catch-up status '{job_data.get('status')}' to WebSocket client for job {job_id}")
    except Exception as e:
        logger.warning(f"Could not send catch-up status for job {job_id}: {e}")
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)