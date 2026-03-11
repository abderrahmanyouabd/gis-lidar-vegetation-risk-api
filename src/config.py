from pydantic import BaseModel
from pathlib import Path

class PipelineConfig(BaseModel):
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    OUTPUT_DIR: Path = BASE_DIR / "output"

    DEFAULT_LAS_FILE: Path = DATA_DIR / "autzen.laz"

    # Geospatial business rules
    MIN_TREE_HEIGHT_M: float = 10.0  # only consider trees taller than this (in meters)

    # ML Clustering Parameters
    CLUSTER_EPSILON: float = 2.5 # How close points need to be to be considered the same tree
    
    CLUSTER_MIN_SAMPLES: int = 20 # Minimum LiDAR points required to confirm it's actually a tree, not something else.
    
    # Risk Thresholds
    CRITICAL_CLEARANCE_M: float = 5.0 # If a tree is within this distance to a powerline, flag it as CRITICAL



settings = PipelineConfig()

settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)