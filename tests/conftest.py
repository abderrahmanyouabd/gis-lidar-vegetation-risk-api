import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon, LineString


@pytest.fixture
def mock_tree_point():
    """Single point geometry for a tree canopy."""
    return Point(0, 0)


@pytest.fixture
def mock_tree_polygon():
    """Simple polygon for a tree canopy."""
    return Polygon([
        (-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)
    ])


@pytest.fixture
def mock_trees_gdf(mock_tree_polygon):
    """GeoDataFrame with a single tree."""
    gdf = gpd.GeoDataFrame({
        'Tree_ID': [1],
        'Max_Height_m': [25.0],
        'ground_z_m': [100.0],
        'top_z_m': [125.0],
        'Point_Count': [500],
        'geometry': [mock_tree_polygon]
    }, crs="EPSG:3857")
    return gdf


@pytest.fixture
def mock_trees_gdf_multiple():
    """GeoDataFrame with multiple trees at different distances."""
    trees = [
        {'Tree_ID': 1, 'Max_Height_m': 25.0, 'ground_z_m': 100.0, 'top_z_m': 125.0, 'Point_Count': 500,
         'geometry': Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)])},
        {'Tree_ID': 2, 'Max_Height_m': 30.0, 'ground_z_m': 100.0, 'top_z_m': 130.0, 'Point_Count': 600,
         'geometry': Polygon([(99, -1), (101, -1), (101, 1), (99, 1), (99, -1)])},
        {'Tree_ID': 3, 'Max_Height_m': 20.0, 'ground_z_m': 100.0, 'top_z_m': 120.0, 'Point_Count': 400,
         'geometry': Polygon([(199, -1), (201, -1), (201, 1), (199, 1), (199, -1)])},
    ]
    return gpd.GeoDataFrame(trees, crs="EPSG:3857")


@pytest.fixture
def mock_conductor_points():
    """Mock numpy array of conductor points (ASPRS class 14)."""
    dtype = [('X', '<f8'), ('Y', '<f8'), ('Z', '<f8')]
    points = np.array([
        (0.0, 0.0, 35.0),
        (10.0, 0.0, 34.0),
        (20.0, 0.0, 33.0),
        (30.0, 0.0, 33.0),
        (40.0, 0.0, 34.0),
        (50.0, 0.0, 35.0),
    ], dtype=dtype)
    return points


@pytest.fixture
def empty_trees_gdf():
    """Empty GeoDataFrame."""
    return gpd.GeoDataFrame(geometry=[], crs="EPSG:3857")


@pytest.fixture
def powerline_line():
    """Simple line for powerline geometry."""
    return LineString([(0, 0, 35), (100, 0, 35)])
