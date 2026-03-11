# 🌍 3D LiDAR Vegetation Risk API

An open-source, full-stack geospatial microservice built to process raw 3D LiDAR point clouds (`.laz`), perform automated feature extraction using Machine Learning, and serve lightweight 2D vector data for vegetation encroachment analysis. 

I built this project to explore the intersection of raw 3D spatial data, unsupervised machine learning, and modern web APIs. The goal was to take heavy, unclassified point clouds and distill them into actionable, web-ready intelligence.

## The Motivation
Raw LiDAR data is massive and difficult to work with in a web browser. I wanted to build an end-to-end pipeline that acts as a bridge between heavy 3D point clouds and lightweight web mapping. This API automatically identifies individual tree canopies and calculates their exact spatial risk to a simulated high-voltage powerline, returning a styled GeoJSON payload that can be rendered instantly on any map.

## System Architecture

This service is broken down into modular components:

1. **The Ingestion & Filtering Engine (`pdal`)**: 
   - Dynamically applies the **Simple Morphological Filter (SMRF)** to raw, unclassified point clouds to mathematically generate a bare-earth terrain model.
   - Calculates the **Height Above Ground (HAG)** for every point to isolate high vegetation, discarding ground and noise points.
2. **The Machine Learning Extractor (`scikit-learn`)**:
   - Uses **DBSCAN (Density-Based Spatial Clustering of Applications with Noise)** to group millions of individual laser returns into distinct "Tree Objects".
3. **The Vectorization & Spatial Math (`geopandas`, `shapely`)**:
   - Converts 3D point clusters into 2D polygon boundaries (Convex Hulls).
   - Simulates a infrastructure asset (powerline) and calculates the exact spatial intersection distance between every tree canopy and the line using optimized C-libraries.
   - Reprojects coordinate systems from local meters (`EPSG:3857`) to web-standard latitude/longitude (`EPSG:4326`).
4. **The REST API (`FastAPI`)**:
   - Wraps the entire processing engine in a fast, self-documenting web endpoint, returning styled GeoJSON payloads ready for frontend visualization (e.g., Mapbox, Leaflet, geojson.io).

## Project Structure

```text
spatial_risk_api/
├── data/                   # Raw LiDAR input (.laz files)
├── output/                 # Generated risk maps (.geojson)
├── src/                    
│   ├── main.py             # FastAPI entry point & route definitions
│   ├── config.py           # Pydantic configuration & spatial thresholds
│   ├── engine.py           # PDAL processing & DBSCAN ML clustering
│   └── spatial_math.py     # GeoPandas vector math & risk evaluation
├── environment.yml         # Conda dependency tracker
└── README.md

```

## Local Setup & Installation

To avoid C++ compilation errors common with geospatial libraries (GDAL/PDAL), this project uses `conda` for reliable dependency management.

1. **Clone the repository**
2. **Build the environment:**
```bash
conda env create -f environment.yml

```


3. **Activate the environment:**
```bash
conda activate geo_api_env

```


4. **Ensure Data exists:** Place a sample LiDAR file (e.g., `autzen.laz`) inside the `data/` directory.

## Usage

Start the FastAPI server:

```bash
uvicorn src.main:app --reload

```

Navigate to the interactive API documentation at:
**`http://127.0.0.1:8000/docs`**

Execute the `POST /api/v1/analyze-risk` endpoint to trigger the pipeline. The API will process the point cloud and return a styled GeoJSON payload containing the powerline and color-coded tree canopies (Red = CRITICAL, Green = SAFE). You can drag and drop the output file from the `output/` folder directly into [geojson.io](https://geojson.io/) to instantly visualize the results.

## Future Architecture Evolutions

While this is currently a synchronous prototype, scaling this to handle statewide datasets would require a few architectural upgrades that I am exploring next:

* **Asynchronous Task Queues:** Moving the heavy `engine.py` processing to a background worker queue (Celery + Redis) to prevent blocking the main API thread.
* **Spatial Databases:** Writing the resulting `GeoDataFrame` assets directly to a **PostgreSQL/PostGIS** database for scalable spatial querying.
* **Cloud Native Storage:** Streaming `.laz` files directly from an AWS S3 bucket using COPC (Cloud Optimized Point Cloud) architecture.
