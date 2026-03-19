import pytest
from unittest.mock import patch, MagicMock
import geopandas as gpd
from shapely.geometry import Point, Polygon

from src.crs_utils import (
    is_projected_crs,
    get_crs_units,
    reproject_gdf,
    validate_crs_for_analysis,
    get_working_crs
)
from src.config import settings


class TestIsProjectedCRS:
    """Tests for CRS type detection."""

    def test_epsg_3857_is_projected(self):
        """EPSG:3857 (Web Mercator) should be projected."""
        assert is_projected_crs("EPSG:3857") is True

    def test_epsg_4326_is_geographic(self):
        """EPSG:4326 (WGS84) should be geographic."""
        assert is_projected_crs("EPSG:4326") is False

    def test_utm_zone_is_projected(self):
        """UTM zones should be projected."""
        assert is_projected_crs("EPSG:32610") is True

    def test_invalid_crs_returns_false(self):
        """Invalid CRS should return False."""
        assert is_projected_crs("EPSG:999999") is False


class TestGetCRSUnits:
    """Tests for CRS unit detection."""

    def test_returns_string(self):
        """get_crs_units should return a string."""
        units = get_crs_units("EPSG:3857")
        assert isinstance(units, str)

    def test_returns_string_for_any_crs(self):
        """get_crs_units should return a string for any valid CRS."""
        units = get_crs_units("EPSG:4326")
        assert isinstance(units, str)


class TestReprojectGDF:
    """Tests for GeoDataFrame reprojection."""

    def test_reprojects_correctly(self):
        """Should reproject from EPSG:4326 to EPSG:3857."""
        gdf = gpd.GeoDataFrame({
            'id': [1],
            'geometry': [Point(0, 0)]
        }, crs="EPSG:4326")

        result = reproject_gdf(gdf, "EPSG:3857")
        assert result.crs.to_string() == "EPSG:3857"

    def test_skips_when_already_correct_crs(self):
        """Should skip reprojection when CRS matches."""
        gdf = gpd.GeoDataFrame({
            'id': [1],
            'geometry': [Point(0, 0)]
        }, crs="EPSG:3857")

        result = reproject_gdf(gdf, "EPSG:3857")
        assert result.crs.to_string() == "EPSG:3857"

    def test_raises_error_when_no_crs(self):
        """Should raise error when GeoDataFrame has no CRS."""
        gdf = gpd.GeoDataFrame({
            'id': [1],
            'geometry': [Point(0, 0)]
        })

        with pytest.raises(ValueError, match="no CRS"):
            reproject_gdf(gdf, "EPSG:3857")


class TestValidateCRS:
    """Tests for CRS validation for analysis."""

    def test_projected_crs_is_valid(self):
        """EPSG:3857 should be valid for analysis."""
        is_valid, msg = validate_crs_for_analysis("EPSG:3857", "EPSG:3857")
        assert is_valid is True

    def test_geographic_crs_is_invalid(self):
        """EPSG:4326 should be invalid for analysis."""
        is_valid, msg = validate_crs_for_analysis("EPSG:4326", "EPSG:3857")
        assert is_valid is False
        assert "EPSG:4326" in msg
        assert "geographic" in msg.lower()


class TestGetWorkingCRS:
    """Tests for working CRS determination with mocked detection."""

    @patch('src.crs_utils.detect_crs_from_copc')
    def test_uses_detected_crs_when_matches_target(self, mock_detect):
        """Should use detected CRS when it matches TARGET_CRS."""
        mock_detect.return_value = "EPSG:3857"
        
        working, source, info = get_working_crs("https://example.com/test.copc")
        
        assert working == "EPSG:3857"
        assert source == "EPSG:3857"
        assert "matches TARGET_CRS" in info

    @patch('src.crs_utils.detect_crs_from_copc')
    def test_reprojects_when_detected_differs(self, mock_detect):
        """Should use TARGET_CRS and reproject when detected differs."""
        mock_detect.return_value = "EPSG:32611"
        
        working, source, info = get_working_crs("https://example.com/test.copc")
        
        assert working == "EPSG:3857"
        assert source == "EPSG:32611"
        assert "reprojecting" in info

    @patch('src.crs_utils.detect_crs_from_copc')
    def test_falls_back_when_detection_fails(self, mock_detect):
        """Should use TARGET_CRS when detection fails."""
        mock_detect.return_value = None
        
        working, source, info = get_working_crs("https://example.com/test.copc")
        
        assert working == "EPSG:3857"
        assert source == "EPSG:3857"
        assert "fallback" in info

    @patch('src.crs_utils.detect_crs_from_copc')
    def test_handles_geographic_detected_crs(self, mock_detect):
        """Should reproject when detected CRS is geographic."""
        mock_detect.return_value = "EPSG:4326"
        
        working, source, info = get_working_crs("https://example.com/test.copc")
        
        assert working == "EPSG:3857"
        assert source == "EPSG:4326"
        assert "invalid" in info.lower() or "reprojecting" in info

    @patch('src.crs_utils.settings')
    def test_uses_config_when_auto_detect_disabled(self, mock_settings):
        """Should use TARGET_CRS from config when AUTO_DETECT_CRS is False."""
        mock_settings.AUTO_DETECT_CRS = False
        mock_settings.TARGET_CRS = "EPSG:3857"
        
        working, source, info = get_working_crs("https://example.com/test.copc")
        
        assert working == "EPSG:3857"
        assert "config:TARGET_CRS" in info
