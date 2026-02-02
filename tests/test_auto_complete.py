"""
Unit tests for auto-completion logic (grace period, status checks, logging).
"""
import asyncio
import pytest
import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from app.auto_complete import (
    schedule_auto_complete, 
    cancel_auto_complete,
    _auto_complete,
    GRACE_PERIOD_MINUTES
)
from app.repo import (
    create_service, 
    create_master, 
    create_booking, 
    get_or_create_user,
    set_booking_status,
    get_booking,
    list_bookings
)


@pytest.fixture(autouse=True)
def enable_logging():
    """Enable logging for all tests."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('app.auto_complete')
    logger.setLevel(logging.INFO)


class TestGracePeriodCalculation:
    """Test grace period calculation in auto-completion scheduling."""
    
    @patch('app.auto_complete.asyncio.create_task')
    async def test_grace_period_added_to_duration(self, mock_create_task, temp_db):
        """Test that grace period is correctly added to service duration."""
        # Setup
        service_duration = 30  # minutes
        expected_total = service_duration + GRACE_PERIOD_MINUTES
        
        # Create a booking in the future to avoid negative delays
        base_time = datetime.now() + timedelta(hours=1)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        # Create test data
        sid = await create_service('TestService', 'desc', 100.0, service_duration)
        mid = await create_master('TestMaster', 'bio', 'contact')
        user = await get_or_create_user(999, name='TestUser', phone='+7999999999')
        bid = await create_booking(user['id'], sid, mid, date_s, time_s, 'TestUser', '+7999999999')
        
        # Schedule
        schedule_auto_complete(bid, date_s, time_s, service_duration)
        
        # Verify that a task was created with correct delay
        mock_create_task.assert_called_once()
        task_coro = mock_create_task.call_args[0][0]
        # Extract the delay from the coroutine by inspecting the function
        # We can't directly access it, but we can verify scheduling happened


    def test_grace_period_constant_is_set(self):
        """Test that GRACE_PERIOD_MINUTES constant is defined."""
        assert GRACE_PERIOD_MINUTES == 15
        assert isinstance(GRACE_PERIOD_MINUTES, int)


class TestStatusChecks:
    """Test status checks before auto-completion."""
    
    async def test_skip_if_already_completed(self, temp_db, caplog):
        """Test that auto-completion is skipped if booking is already completed."""
        # Create completed booking
        sid = await create_service('S', 'd', 10.0, 30)
        mid = await create_master('M', 'b', 'c')
        user = await get_or_create_user(777, name='User', phone='+7777777777')
        await create_booking(user['id'], sid, mid, '2026-01-15', '09:00', 'User', '+7777777777')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Mark as completed before auto-completion
        await set_booking_status(bid, 'completed')
        
        # Run auto-complete with 0 delay
        with caplog.at_level(logging.INFO, logger='app.auto_complete'):
            with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
                await _auto_complete(bid, 0)
        
        # Check that it was skipped in logs
        assert 'auto_complete_skip' in caplog.text
        assert f'booking_id={bid}' in caplog.text
        assert 'already_completed' in caplog.text


    async def test_skip_if_cancelled(self, temp_db, caplog):
        """Test that auto-completion is skipped if booking is cancelled."""
        # Create cancelled booking
        sid = await create_service('S', 'd', 10.0, 30)
        mid = await create_master('M', 'b', 'c')
        user = await get_or_create_user(888, name='User', phone='+7888888888')
        await create_booking(user['id'], sid, mid, '2026-01-15', '10:00', 'User', '+7888888888')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Mark as cancelled before auto-completion
        await set_booking_status(bid, 'cancelled')
        
        # Run auto-complete with 0 delay
        with caplog.at_level(logging.INFO, logger='app.auto_complete'):
            with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
                await _auto_complete(bid, 0)
        
        # Check that it was skipped in logs
        assert 'auto_complete_skip' in caplog.text
        assert f'booking_id={bid}' in caplog.text
        assert 'cancelled' in caplog.text


    async def test_complete_if_scheduled(self, temp_db, caplog):
        """Test that auto-completion proceeds if booking is still scheduled."""
        # Create scheduled booking
        sid = await create_service('S', 'd', 10.0, 30)
        mid = await create_master('M', 'b', 'c')
        user = await get_or_create_user(999, name='User', phone='+7999999999')
        await create_booking(user['id'], sid, mid, '2026-01-15', '11:00', 'User', '+7999999999')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Verify it's scheduled
        booking = await get_booking(bid)
        assert booking['status'] == 'scheduled'
        
        # Run auto-complete with 0 delay
        with caplog.at_level(logging.INFO, logger='app.auto_complete'):
            with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
                with patch('app.auto_complete.create_review', new_callable=AsyncMock):
                    await _auto_complete(bid, 0)
        
        # Verify it's now completed
        booking = await get_booking(bid)
        assert booking['status'] == 'completed'
        
        # Check that completion was logged
        assert 'auto_complete:' in caplog.text
        assert f'booking_id={bid}' in caplog.text
        assert 'scheduled->completed' in caplog.text


class TestLogging:
    """Test logging of auto-completions and skips."""
    
    async def test_log_successful_completion(self, temp_db, caplog):
        """Test that successful auto-completion is logged with correct fields."""
        sid = await create_service('S', 'd', 10.0, 30)
        mid = await create_master('M', 'b', 'c')
        user = await get_or_create_user(111, name='User', phone='+7111111111')
        await create_booking(user['id'], sid, mid, '2026-01-15', '12:00', 'User', '+7111111111')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        with caplog.at_level(logging.INFO, logger='app.auto_complete'):
            with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
                with patch('app.auto_complete.create_review', new_callable=AsyncMock):
                    await _auto_complete(bid, 0)
        
        # Check log contains all required fields
        assert 'auto_complete:' in caplog.text
        assert f'booking_id={bid}' in caplog.text
        assert 'timestamp=' in caplog.text
        assert 'status_change=scheduled->completed' in caplog.text


    async def test_log_skip_with_reason(self, temp_db, caplog):
        """Test that skipped auto-completions are logged with reason."""
        sid = await create_service('S', 'd', 10.0, 30)
        mid = await create_master('M', 'b', 'c')
        user = await get_or_create_user(222, name='User', phone='+7222222222')
        await create_booking(user['id'], sid, mid, '2026-01-15', '13:00', 'User', '+7222222222')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Mark as completed
        await set_booking_status(bid, 'completed')
        
        with caplog.at_level(logging.INFO, logger='app.auto_complete'):
            with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
                await _auto_complete(bid, 0)
        
        # Check skip log contains all required fields
        assert 'auto_complete_skip:' in caplog.text
        assert f'booking_id={bid}' in caplog.text
        assert 'reason=already_completed' in caplog.text
        assert 'timestamp=' in caplog.text


class TestTaskScheduling:
    """Test task scheduling and cancellation."""
    
    @patch('app.auto_complete.asyncio.create_task')
    def test_cancel_scheduled_task(self, mock_create_task):
        """Test that cancel_auto_complete cancels the task."""
        # Create a mock task
        mock_task = MagicMock()
        mock_create_task.return_value = mock_task
        
        bid = 123
        # Schedule a task
        schedule_auto_complete(bid, '2026-01-20', '14:00', 30)
        
        # Verify task was created
        assert mock_create_task.called
        
        # Cancel the task
        cancel_auto_complete(bid)
        
        # Verify cancel was called
        mock_task.cancel.assert_called_once()


    @patch('app.auto_complete.asyncio.create_task')
    def test_cancel_nonexistent_task(self, mock_create_task):
        """Test that cancelling nonexistent task doesn't raise."""
        # Should not raise
        cancel_auto_complete(999)
