from datetime import datetime, timedelta
import asyncio
import logging
from app.repo import set_booking_status, get_booking, get_service
from app.notify import notify_admins
from app.repo import get_user_by_id, create_review

# Grace period: delay before auto-completion (in minutes)
GRACE_PERIOD_MINUTES = 15

# Configure logging
logger = logging.getLogger(__name__)

_scheduled_tasks = {}


def schedule_auto_complete(booking_id, date_s, time_s, duration_min):
    """Schedule auto-completion with grace period.
    
    Args:
        booking_id: Booking ID
        date_s: Booking date (ISO format)
        time_s: Booking time (HH:MM format)
        duration_min: Service duration in minutes
    """
    # Calculate when to complete: booking_time + duration + grace_period
    dt = datetime.fromisoformat(f"{date_s}T{time_s}") + timedelta(
        minutes=duration_min + GRACE_PERIOD_MINUTES
    )
    delay = (dt - datetime.now()).total_seconds()
    if delay < 0:
        delay = 0
    # NOTE: schedule_auto_complete creates a background task using
    # `asyncio.create_task`. Ensure the bot runs inside an asyncio
    # event loop (as in `app/main.py`). If called outside a running
    # loop, tasks may not be scheduled and you may see
    # "coroutine was never awaited" warnings. This is a potential
    # runtime observation during testing; logic kept as-is for MVP.
    task = asyncio.create_task(_auto_complete(booking_id, delay))
    _scheduled_tasks[booking_id] = task


def cancel_auto_complete(booking_id):
    """Cancel scheduled auto-completion for a booking."""
    task = _scheduled_tasks.pop(booking_id, None)
    if task:
        task.cancel()


async def _auto_complete(booking_id, delay):
    """Auto-complete a booking after delay.
    
    Checks current status before completion to avoid double-processing.
    Logs all auto-completions and skips.
    """
    await asyncio.sleep(delay)
    
    # Get fresh booking status from DB
    booking = await get_booking(booking_id)
    if not booking:
        logger.info(f"auto_complete: booking {booking_id} not found (already deleted?)")
        return
    
    # Check if already completed or cancelled
    if booking['status'] == 'completed':
        logger.info(
            f"auto_complete_skip: booking_id={booking_id}, "
            f"reason=already_completed, timestamp={datetime.now().isoformat()}"
        )
        return
    
    if booking['status'] == 'cancelled':
        logger.info(
            f"auto_complete_skip: booking_id={booking_id}, "
            f"reason=cancelled, timestamp={datetime.now().isoformat()}"
        )
        return
    
    # Auto-complete the booking
    old_status = booking['status']
    await set_booking_status(booking_id, 'completed')
    
    # Log successful completion
    logger.info(
        f"auto_complete: booking_id={booking_id}, "
        f"timestamp={datetime.now().isoformat()}, "
        f"status_change={old_status}->completed"
    )
    
    # Auto-request review
    user = await get_user_by_id(booking['user_id'])
    if user:
        await create_review(
            user['id'], booking['service_id'], booking['master_id'], 
            rating=5, text=None
        )
        await notify_admins(
            f"Авто-завершение и авто-отзыв: booking_id={booking_id}"
        )
