import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon, LineString
import json

from src.spatial_math import (
    _build_powerline_from_conductors,
    _build_simulated_powerline,
    evaluate_vegetation_risk
)
from src.config import settings


class TestRiskLevelCalculation:
    """Tests for risk level calculation based on distance thresholds."""

    def test_critical_risk_at_threshold(self, mock_trees_gdf):
        """Test that distance exactly at CRITICAL threshold returns CRITICAL."""
        gdf = mock_trees_gdf.copy()
        gdf['Distance_to_Line_m'] = settings.CRITICAL_CLEARANCE_M
        
        gdf['Risk_Level'] = gdf['Distance_to_Line_m'].apply(
            lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                      else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                      else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                      else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                      else 'SAFE'
        )
        
        assert gdf['Risk_Level'].iloc[0] == 'CRITICAL'

    def test_critical_risk_below_threshold(self, mock_trees_gdf):
        """Test that distance below CRITICAL threshold returns CRITICAL."""
        gdf = mock_trees_gdf.copy()
        gdf['Distance_to_Line_m'] = settings.CRITICAL_CLEARANCE_M - 1.0
        
        gdf['Risk_Level'] = gdf['Distance_to_Line_m'].apply(
            lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                      else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                      else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                      else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                      else 'SAFE'
        )
        
        assert gdf['Risk_Level'].iloc[0] == 'CRITICAL'

    def test_high_risk(self, mock_trees_gdf):
        """Test that distance in HIGH range returns HIGH."""
        gdf = mock_trees_gdf.copy()
        gdf['Distance_to_Line_m'] = settings.CRITICAL_CLEARANCE_M * 1.5
        
        gdf['Risk_Level'] = gdf['Distance_to_Line_m'].apply(
            lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                      else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                      else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                      else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                      else 'SAFE'
        )
        
        assert gdf['Risk_Level'].iloc[0] == 'HIGH'

    def test_moderate_risk(self, mock_trees_gdf):
        """Test that distance in MODERATE range returns MODERATE."""
        gdf = mock_trees_gdf.copy()
        gdf['Distance_to_Line_m'] = settings.CRITICAL_CLEARANCE_M * 3
        
        gdf['Risk_Level'] = gdf['Distance_to_Line_m'].apply(
            lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                      else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                      else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                      else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                      else 'SAFE'
        )
        
        assert gdf['Risk_Level'].iloc[0] == 'MODERATE'

    def test_low_risk(self, mock_trees_gdf):
        """Test that distance in LOW range returns LOW."""
        gdf = mock_trees_gdf.copy()
        gdf['Distance_to_Line_m'] = settings.CRITICAL_CLEARANCE_M * 6
        
        gdf['Risk_Level'] = gdf['Distance_to_Line_m'].apply(
            lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                      else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                      else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                      else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                      else 'SAFE'
        )
        
        assert gdf['Risk_Level'].iloc[0] == 'LOW'

    def test_safe_risk(self, mock_trees_gdf):
        """Test that distance above all thresholds returns SAFE."""
        gdf = mock_trees_gdf.copy()
        gdf['Distance_to_Line_m'] = settings.CRITICAL_CLEARANCE_M * 10
        
        gdf['Risk_Level'] = gdf['Distance_to_Line_m'].apply(
            lambda d: 'CRITICAL' if d <= settings.CRITICAL_CLEARANCE_M
                      else 'HIGH'     if d <= settings.CRITICAL_CLEARANCE_M * 2
                      else 'MODERATE' if d <= settings.CRITICAL_CLEARANCE_M * 4
                      else 'LOW'      if d <= settings.CRITICAL_CLEARANCE_M * 8
                      else 'SAFE'
        )
        
        assert gdf['Risk_Level'].iloc[0] == 'SAFE'


class TestBuildPowerlineFromConductors:
    """Tests for building powerline from real conductor points."""

    def test_builds_powerline_from_conductor_points(self, mock_conductor_points):
        """Test that powerline is built from conductor points."""
        result = _build_powerline_from_conductors(mock_conductor_points, "EPSG:3857")
        
        assert not result.empty
        assert len(result) == 1
        assert result['source'].iloc[0] == 'lidar_class_14'
        assert result['Type'].iloc[0] == 'Conductor (class 14)'

    def test_returns_empty_for_empty_conductor_points(self):
        """Test that empty array returns empty GeoDataFrame."""
        empty_pts = np.array([])
        result = _build_powerline_from_conductors(empty_pts, "EPSG:3857")
        
        assert result.empty

    def test_powerline_has_3d_geometry(self, mock_conductor_points):
        """Test that powerline geometry includes Z coordinates."""
        result = _build_powerline_from_conductors(mock_conductor_points, "EPSG:3857")
        
        coords = list(result.geometry.iloc[0].coords)
        for coord in coords:
            assert len(coord) == 3  # (x, y, z)


class TestBuildSimulatedPowerline:
    """Tests for simulated powerline fallback."""

    def test_creates_simulated_powerline(self, mock_trees_gdf):
        """Test that simulated powerline is created from tree bounds."""
        result = _build_simulated_powerline(mock_trees_gdf)
        
        assert not result.empty
        assert result['source'].iloc[0] == 'simulated'
        assert 'Simulated' in result['Type'].iloc[0]

    def test_simulated_powerline_has_fixed_z(self, mock_trees_gdf):
        """Test that simulated powerline has fixed Z of 35m."""
        result = _build_simulated_powerline(mock_trees_gdf)
        
        coords = list(result.geometry.iloc[0].coords)
        for coord in coords:
            assert coord[2] == 35.0


class TestEvaluateVegetationRisk:
    """Integration tests for full vegetation risk evaluation."""

    def test_returns_correct_structure(self, mock_trees_gdf):
        """Test that output has expected keys."""
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        assert 'trees' in result
        assert 'powerline' in result
        assert 'metadata' in result

    def test_empty_trees_returns_empty_dicts(self, empty_trees_gdf):
        """Test that empty GeoDataFrame returns empty dicts."""
        result = evaluate_vegetation_risk(empty_trees_gdf)
        
        assert result == {"trees": {}, "powerline": {}}

    def test_metadata_has_required_fields(self, mock_trees_gdf):
        """Test that metadata contains required fields."""
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        assert 'horizontal_crs' in result['metadata']
        assert 'vertical_datum' in result['metadata']
        assert 'powerline_source' in result['metadata']
        assert 'units' in result['metadata']

    def test_uses_simulated_powerline_when_no_conductors(self, mock_trees_gdf):
        """Test that simulated powerline is used when no conductor points."""
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        assert result['metadata']['powerline_source'] == 'simulated'

    def test_uses_real_powerline_with_conductors(self, mock_trees_gdf, mock_conductor_points):
        """Test that real powerline is used when conductor points exist."""
        mock_trees_gdf.attrs['conductor_pts'] = mock_conductor_points
        
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        assert result['metadata']['powerline_source'] == 'lidar_class_14'

    def test_output_is_geojson_serializable(self, mock_trees_gdf):
        """Test that output can be serialized to JSON."""
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        # Should not raise
        json_str = json.dumps(result)
        assert 'trees' in json_str
        assert 'powerline' in json_str


class TestDistanceCalculation:
    """Tests for distance calculations."""

    def test_distance_column_exists(self, mock_trees_gdf):
        """Test that Distance_to_Line_m column is created."""
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        # Parse the trees GeoJSON back to check columns
        trees_data = result['trees']
        if 'features' in trees_data and len(trees_data['features']) > 0:
            props = trees_data['features'][0]['properties']
            assert 'Distance_to_Line_m' in props

    def test_risk_level_column_exists(self, mock_trees_gdf):
        """Test that Risk_Level column is created."""
        result = evaluate_vegetation_risk(mock_trees_gdf)
        
        trees_data = result['trees']
        if 'features' in trees_data and len(trees_data['features']) > 0:
            props = trees_data['features'][0]['properties']
            assert 'Risk_Level' in props
