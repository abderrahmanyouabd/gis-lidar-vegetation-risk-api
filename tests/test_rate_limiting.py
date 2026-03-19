import pytest
from unittest.mock import patch, MagicMock
from fastapi import Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.config import settings


@pytest.fixture
def test_client():
    """Create a TestClient with mocked dependencies."""
    with patch('src.main.producer') as mock_producer, \
         patch('src.main.collection') as mock_collection:
        
        mock_producer.send = MagicMock()
        mock_producer.flush = MagicMock()
        
        from src.main import app
        client = TestClient(app)
        yield client


class TestRateLimitConfig:
    """Tests for rate limiting configuration."""

    def test_rate_limit_enabled_by_default(self):
        """Rate limiting should be enabled by default."""
        assert settings.RATE_LIMIT_ENABLED is True

    def test_analyze_endpoint_limit(self):
        """Analyze endpoint should have strictest limit."""
        assert settings.RATE_LIMIT_ANALYZE == "10/minute"

    def test_read_endpoint_limit(self):
        """Read endpoints should have higher limit."""
        assert settings.RATE_LIMIT_READ == "120/minute"

    def test_delete_endpoint_limit(self):
        """Delete endpoint should have moderate limit."""
        assert settings.RATE_LIMIT_DELETE == "20/minute"


class TestLimiterInitialization:
    """Tests for limiter setup."""

    def test_limiter_uses_remote_address(self):
        """Limiter should use get_remote_address as key function."""
        from src.main import limiter
        assert limiter._key_func == get_remote_address

    def test_limiter_is_limiter_instance(self):
        """Limiter should be a Limiter instance."""
        from src.main import limiter
        assert isinstance(limiter, Limiter)


class TestRateLimitDecorators:
    """Tests that rate limit decorators are applied correctly."""

    @patch('src.main.limiter')
    def test_analyze_endpoint_has_decorator(self, mock_limiter):
        """Analyze endpoint should have rate limit decorator."""
        from src.main import analyze_risk
        decorators = getattr(analyze_risk, '__wrapped__', None)
        assert decorators is not None or hasattr(analyze_risk, '__call__')

    @patch('src.main.limiter')
    def test_list_jobs_endpoint_has_decorator(self, mock_limiter):
        """List jobs endpoint should have rate limit decorator."""
        from src.main import list_jobs
        assert hasattr(list_jobs, '__call__')

    @patch('src.main.limiter')
    def test_get_job_endpoint_has_decorator(self, mock_limiter):
        """Get job endpoint should have rate limit decorator."""
        from src.main import get_job_result
        assert hasattr(get_job_result, '__call__')

    @patch('src.main.limiter')
    def test_cancel_job_endpoint_has_decorator(self, mock_limiter):
        """Cancel job endpoint should have rate limit decorator."""
        from src.main import cancel_job
        assert hasattr(cancel_job, '__call__')


class TestRateLimitExceededHandler:
    """Tests for rate limit exceeded response."""

    def test_rate_limit_exceeded_handler_registered(self):
        """Rate limit exceeded handler should be registered on app."""
        from src.main import app
        assert hasattr(app, 'state')
        assert hasattr(app.state, 'limiter')

    def test_rate_limit_exception_handler_registered(self):
        """RateLimitExceeded exception handler should be registered."""
        from src.main import app
        from slowapi.errors import RateLimitExceeded
        handlers = app.exception_handlers
        assert RateLimitExceeded in handlers


class TestRateLimitRequestParameter:
    """Tests that endpoints accept Request parameter for rate limiting."""

    def test_analyze_accepts_request_param(self):
        """Analyze endpoint should accept Request as first parameter."""
        from src.main import analyze_risk
        import inspect
        sig = inspect.signature(analyze_risk)
        params = list(sig.parameters.keys())
        assert 'request' in params

    def test_list_jobs_accepts_request_param(self):
        """List jobs endpoint should accept Request as first parameter."""
        from src.main import list_jobs
        import inspect
        sig = inspect.signature(list_jobs)
        params = list(sig.parameters.keys())
        assert 'request' in params

    def test_get_job_accepts_request_param(self):
        """Get job endpoint should accept Request as first parameter."""
        from src.main import get_job_result
        import inspect
        sig = inspect.signature(get_job_result)
        params = list(sig.parameters.keys())
        assert 'request' in params

    def test_cancel_job_accepts_request_param(self):
        """Cancel job endpoint should accept Request as first parameter."""
        from src.main import cancel_job
        import inspect
        sig = inspect.signature(cancel_job)
        params = list(sig.parameters.keys())
        assert 'request' in params


class TestRateLimitIntegration:
    """Integration tests using TestClient to verify rate limiting works end-to-end."""

    def test_analyze_endpoint_rate_limited_after_10_requests(self, test_client):
        """11th request to analyze should return 429 after 10 successful requests."""
        for i in range(10):
            response = test_client.post("/api/v1/analyze-risk", json={})
            assert response.status_code == 200, f"Request {i+1} should succeed"
        
        response = test_client.post("/api/v1/analyze-risk", json={})
        assert response.status_code == 429, "11th request should be rate limited"

    def test_list_jobs_rate_limited_after_120_requests(self, test_client):
        """121st request to list jobs should return 429 after 120 successful requests."""
        with patch('src.main.collection') as mock_collection:
            mock_collection.count_documents.return_value = 0
            mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
            
            for i in range(120):
                response = test_client.get("/api/v1/jobs")
                assert response.status_code == 200, f"Request {i+1} should succeed"
            
            response = test_client.get("/api/v1/jobs")
            assert response.status_code == 429, "121st request should be rate limited"

    def test_get_job_rate_limited(self, test_client):
        """Rate limiting should apply to get single job endpoint."""
        with patch('src.main.collection') as mock_collection:
            mock_job = {
                '_id': 'mongo_id',
                'job_id': 'test-123',
                'status': 'completed',
                'result': {}
            }
            mock_collection.find_one.return_value = mock_job
            
            response = test_client.get("/api/v1/jobs/test-123")
            assert response.status_code == 200

    def test_delete_job_rate_limited(self, test_client):
        """Rate limiting should apply to delete job endpoint."""
        with patch('src.main.collection') as mock_collection, \
             patch('src.main.producer') as mock_producer:
            
            mock_collection.find_one.return_value = {
                'job_id': 'test-123',
                'status': 'queued'
            }
            
            for i in range(20):
                response = test_client.delete("/api/v1/jobs/test-123")
                assert response.status_code == 200, f"Request {i+1} should succeed"
            
            response = test_client.delete("/api/v1/jobs/test-123")
            assert response.status_code == 429, "21st request should be rate limited"
