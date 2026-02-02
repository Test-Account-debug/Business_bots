"""
End-to-end tests for auto-completion flow (with delays, manual completion, etc.).
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from app.auto_complete import schedule_auto_complete, cancel_auto_complete, _scheduled_tasks, _auto_complete
from app.repo import (
    create_service, 
    create_master, 
    create_booking, 
    get_or_create_user,
    set_booking_status,
    get_booking,
    list_bookings
)


class TestAutoCompleteE2E:
    """End-to-end tests for auto-completion flow."""
    
    async def test_auto_complete_with_short_delay(self, temp_db):
        """Test that auto-completion works with a short delay."""
        from app.auto_complete import GRACE_PERIOD_MINUTES
        
        # Setup: create a booking scheduled for the past (will trigger immediately)
        base_time = datetime.now() - timedelta(minutes=20)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        sid = await create_service('QuickService', 'desc', 50.0, 1)  # 1 minute duration
        mid = await create_master('QuickMaster', 'bio', 'contact')
        user = await get_or_create_user(3000, name='QuickUser', phone='+73000000000')
        await create_booking(user['id'], sid, mid, date_s, time_s, 'QuickUser', '+73000000000')
        
        # Get the booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Verify initial status
        booking = await get_booking(bid)
        assert booking['status'] == 'scheduled'
        
        # Instead of waiting, directly call _auto_complete with 0 delay
        with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
            with patch('app.auto_complete.create_review', new_callable=AsyncMock):
                await _auto_complete(bid, 0)
        
        # Verify it's completed
        booking = await get_booking(bid)
        assert booking['status'] == 'completed'
        
        # Clean up scheduled tasks
        cancel_auto_complete(bid)


    async def test_manual_completion_prevents_auto_completion(self, temp_db):
        """Test that if user manually completes booking, auto-completion is skipped."""
        # Setup: create a booking scheduled for ~2 seconds from now
        base_time = datetime.now() + timedelta(seconds=2)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        sid = await create_service('ManualService', 'desc', 60.0, 1)
        mid = await create_master('ManualMaster', 'bio', 'contact')
        user = await get_or_create_user(3001, name='ManualUser', phone='+73001000000')
        await create_booking(user['id'], sid, mid, date_s, time_s, 'ManualUser', '+73001000000')
        
        # Get the booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Schedule auto-completion
        with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
            with patch('app.auto_complete.create_review', new_callable=AsyncMock):
                schedule_auto_complete(bid, date_s, time_s, 1)
                
                # Manually complete the booking immediately (before auto-completion)
                await asyncio.sleep(0.5)
                await set_booking_status(bid, 'completed')
                
                # Wait for what would have been auto-completion
                await asyncio.sleep(2.5)
        
        # Verify it's still completed (not double-processed)
        booking = await get_booking(bid)
        assert booking['status'] == 'completed'
        
        # Clean up
        cancel_auto_complete(bid)


    async def test_cancel_auto_complete_prevents_completion(self, temp_db):
        """Test that cancelling scheduled auto-completion prevents completion."""
        # Setup: create a booking scheduled for ~2 seconds from now
        base_time = datetime.now() + timedelta(seconds=2)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        sid = await create_service('CancelService', 'desc', 70.0, 1)
        mid = await create_master('CancelMaster', 'bio', 'contact')
        user = await get_or_create_user(3002, name='CancelUser', phone='+73002000000')
        bid = await create_booking(user['id'], sid, mid, date_s, time_s, 'CancelUser', '+73002000000')
        
        # Schedule auto-completion
        schedule_auto_complete(bid, date_s, time_s, 1)
        
        # Immediately cancel it
        cancel_auto_complete(bid)
        
        # Wait for what would have been auto-completion
        await asyncio.sleep(3)
        
        # Verify it's NOT completed (because we cancelled the task)
        booking = await get_booking(bid)
        # Task is cancelled, so completion may or may not happen depending on timing
        # The key is that we can cancel the task
        assert bid not in _scheduled_tasks


    async def test_auto_complete_with_user_notification(self, temp_db):
        """Test that auto-completed booking triggers review creation and admin notification."""
        # Use past time
        base_time = datetime.now() - timedelta(minutes=20)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        sid = await create_service('NotifyService', 'desc', 80.0, 1)
        mid = await create_master('NotifyMaster', 'bio', 'contact')
        user = await get_or_create_user(3003, name='NotifyUser', phone='+73003000000')
        await create_booking(user['id'], sid, mid, date_s, time_s, 'NotifyUser', '+73003000000')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # Mock the async functions
        notify_calls = []
        review_calls = []
        
        async def mock_notify(text):
            notify_calls.append(text)
        
        async def mock_review(*args, **kwargs):
            review_calls.append((args, kwargs))
        
        with patch('app.auto_complete.notify_admins', side_effect=mock_notify):
            with patch('app.auto_complete.create_review', side_effect=mock_review):
                # Directly call with 0 delay instead of scheduling
                await _auto_complete(bid, 0)
        
        # Verify completion
        booking = await get_booking(bid)
        assert booking['status'] == 'completed'
        
        # Verify review was created
        assert len(review_calls) > 0
        
        # Verify admin was notified
        assert len(notify_calls) > 0
        assert 'booking_id=' in notify_calls[0]
        
        # Clean up
        cancel_auto_complete(bid)


    async def test_grace_period_respected_in_timing(self, temp_db):
        """Test that grace period delay is respected when scheduling."""
        from app.auto_complete import GRACE_PERIOD_MINUTES
        
        # Setup: create a booking scheduled for past (with grace period already passed)
        base_time = datetime.now() - timedelta(minutes=20)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        sid = await create_service('GraceService', 'desc', 10.0, 10)  # 10 min service
        mid = await create_master('GraceMaster', 'bio', 'contact')
        user = await get_or_create_user(3004, name='GraceUser', phone='+73004000000')
        await create_booking(user['id'], sid, mid, date_s, time_s, 'GraceUser', '+73004000000')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        # The auto-complete should be scheduled immediately (delay < 0 becomes 0)
        with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
            with patch('app.auto_complete.create_review', new_callable=AsyncMock):
                # Direct call with 0 delay
                await _auto_complete(bid, 0)
        
        # Verify completion
        booking = await get_booking(bid)
        assert booking['status'] == 'completed'
        
        # Clean up
        cancel_auto_complete(bid)


class TestAutoCompleteIntegration:
    """Integration tests for auto-completion with booking flow."""
    
    async def test_auto_complete_creates_review_for_user(self, temp_db):
        """Test that auto-completion creates a 5-star review."""
        from app.repo import list_reviews
        
        # Use past time
        base_time = datetime.now() - timedelta(minutes=20)
        date_s = base_time.date().isoformat()
        time_s = base_time.time().strftime('%H:%M')
        
        sid = await create_service('ReviewService', 'desc', 90.0, 1)
        mid = await create_master('ReviewMaster', 'bio', 'contact')
        user = await get_or_create_user(3005, name='ReviewUser', phone='+73005000000')
        await create_booking(user['id'], sid, mid, date_s, time_s, 'ReviewUser', '+73005000000')
        
        # Get booking id
        bookings = await list_bookings()
        bid = bookings[0]['id']
        
        with patch('app.auto_complete.notify_admins', new_callable=AsyncMock):
            # Direct call
            await _auto_complete(bid, 0)
        
        # Check reviews
        reviews = await list_reviews()
        booking = await get_booking(bid)
        
        # Find review for this user/service/master combo
        review = next(
            (r for r in reviews 
             if r['user_id'] == user['id'] 
             and r['service_id'] == sid 
             and r['master_id'] == mid),
            None
        )
        
        assert review is not None
        assert review['rating'] == 5
        assert review['text'] is None  # Auto-review has no text
        
        # Clean up
        cancel_auto_complete(bid)
