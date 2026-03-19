import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.main import (
    list_jobs,
    cancel_job,
    JobListItem,
    JobListResponse,
    PaginationInfo
)


class TestListJobs:
    """Tests for GET /api/v1/jobs endpoint."""

    @patch('src.main.collection')
    def test_pagination_defaults(self, mock_collection):
        """Test default pagination values."""
        mock_collection.count_documents.return_value = 0
        mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        
        response = list_jobs(page=1, limit=20)
        
        assert response.pagination.page == 1
        assert response.pagination.limit == 20
        assert response.jobs == []

    @patch('src.main.collection')
    def test_custom_page_and_limit(self, mock_collection):
        """Test custom pagination values."""
        mock_collection.count_documents.return_value = 100
        mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        
        response = list_jobs(page=3, limit=50)
        
        assert response.pagination.page == 3
        assert response.pagination.limit == 50

    @patch('src.main.collection')
    def test_empty_jobs_list(self, mock_collection):
        """Test returns empty list when no jobs exist."""
        mock_collection.count_documents.return_value = 0
        mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        
        response = list_jobs(page=1, limit=20)
        
        assert response.jobs == []
        assert response.pagination.total == 0

    @patch('src.main.collection')
    def test_returns_job_fields_excluding_result(self, mock_collection):
        """Test that job fields are returned but result/error are excluded."""
        mock_job = {
            'job_id': 'test-123',
            'cloud_url': 'https://example.com/test.copc',
            'status': 'completed',
            'message': 'Done',
            'created_at': datetime(2026, 3, 19, 10, 30, 0),
            'result': {'some': 'data'},
            'error': 'some error'
        }
        mock_collection.count_documents.return_value = 1
        mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = [mock_job]
        
        response = list_jobs(page=1, limit=20)
        
        assert len(response.jobs) == 1
        job = response.jobs[0]
        assert job.job_id == 'test-123'
        assert job.cloud_url == 'https://example.com/test.copc'
        assert job.status == 'completed'
        assert job.message == 'Done'
        assert job.created_at == datetime(2026, 3, 19, 10, 30, 0)

    @patch('src.main.collection')
    def test_total_count_is_correct(self, mock_collection):
        """Test total count matches database."""
        mock_collection.count_documents.return_value = 45
        mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        
        response = list_jobs(page=1, limit=20)
        
        assert response.pagination.total == 45
        assert response.pagination.total_pages == 3

    @patch('src.main.collection')
    def test_total_pages_calculation(self, mock_collection):
        """Test total_pages is calculated correctly."""
        mock_collection.count_documents.return_value = 85
        mock_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        
        response = list_jobs(page=1, limit=20)
        
        assert response.pagination.total_pages == 5


class TestCancelJob:
    """Tests for DELETE /api/v1/jobs/{job_id} endpoint."""

    @patch('src.main.collection')
    @patch('src.main.producer')
    def test_cancel_queued_job(self, mock_producer, mock_collection):
        """Test cancelling a queued job."""
        mock_collection.find_one.return_value = {
            'job_id': 'test-123',
            'status': 'queued'
        }
        
        response = cancel_job('test-123')
        
        assert response['job_id'] == 'test-123'
        assert response['status'] == 'cancelled'
        mock_collection.update_one.assert_called_once()
        mock_producer.send.assert_called_once()

    @patch('src.main.collection')
    @patch('src.main.producer')
    def test_cancel_processing_job(self, mock_producer, mock_collection):
        """Test cancelling a processing job."""
        mock_collection.find_one.return_value = {
            'job_id': 'test-123',
            'status': 'processing'
        }
        
        response = cancel_job('test-123')
        
        assert response['job_id'] == 'test-123'
        assert response['status'] == 'cancelled'

    @patch('src.main.collection')
    def test_reject_completed_job(self, mock_collection):
        """Test cannot cancel a completed job."""
        mock_collection.find_one.return_value = {
            'job_id': 'test-123',
            'status': 'completed'
        }
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            cancel_job('test-123')
        
        assert exc_info.value.status_code == 400
        assert 'completed' in exc_info.value.detail

    @patch('src.main.collection')
    def test_reject_failed_job(self, mock_collection):
        """Test cannot cancel a failed job."""
        mock_collection.find_one.return_value = {
            'job_id': 'test-123',
            'status': 'failed'
        }
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            cancel_job('test-123')
        
        assert exc_info.value.status_code == 400
        assert 'failed' in exc_info.value.detail

    @patch('src.main.collection')
    def test_reject_already_cancelled(self, mock_collection):
        """Test cannot cancel an already cancelled job."""
        mock_collection.find_one.return_value = {
            'job_id': 'test-123',
            'status': 'cancelled'
        }
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            cancel_job('test-123')
        
        assert exc_info.value.status_code == 400
        assert 'already cancelled' in exc_info.value.detail

    @patch('src.main.collection')
    def test_job_not_found(self, mock_collection):
        """Test 404 when job does not exist."""
        mock_collection.find_one.return_value = None
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            cancel_job('nonexistent-id')
        
        assert exc_info.value.status_code == 404
        assert 'not found' in exc_info.value.detail.lower()

    @patch('src.main.collection')
    @patch('src.main.producer')
    def test_broadcasts_cancellation_event(self, mock_producer, mock_collection):
        """Test cancellation is broadcast via Kafka."""
        mock_collection.find_one.return_value = {
            'job_id': 'test-123',
            'status': 'queued'
        }
        
        cancel_job('test-123')
        
        mock_producer.send.assert_called_with('job-status-events', {
            'job_id': 'test-123',
            'status': 'cancelled',
            'message': 'Job cancelled by user'
        })
        mock_producer.flush.assert_called_once()
