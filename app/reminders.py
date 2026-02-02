from datetime import datetime, timedelta
import asyncio
import logging
from app.repo import get_booking, get_user_by_id, set_reminder_sent
from app.notify import notify_user

logger = logging.getLogger(__name__)

_scheduled_reminders = {}


def _dt_from_parts(date_s: str, time_s: str) -> datetime:
    return datetime.fromisoformat(f"{date_s}T{time_s}")


def compute_reminder_times(date_s: str, time_s: str):
    """Return dict with reminder datetimes for 24h and 1h before booking."""
    dt = _dt_from_parts(date_s, time_s)
    return {
        '24h': dt - timedelta(hours=24),
        '1h': dt - timedelta(hours=1),
        'booking': dt,
    }


def schedule_reminders(booking_id: int, date_s: str, time_s: str):
    """Schedule reminder tasks for a booking (24h and 1h before)."""
    times = compute_reminder_times(date_s, time_s)
    now = datetime.now()
    for kind in ('24h', '1h'):
        run_at = times[kind]
        delay = (run_at - now).total_seconds()
        if delay < 0:
            delay = 0
        # NOTE: schedule_reminders uses background tasks created via
        # `asyncio.create_task`. Ensure bot runs within an asyncio loop.
        # If scheduling occurs outside a running loop it may raise or
        # produce 'coroutine was never awaited' warnings during tests.
        task = asyncio.create_task(_send_reminder(booking_id, kind, delay))
        _scheduled_reminders.setdefault(booking_id, {})[kind] = task


def cancel_reminders(booking_id: int):
    d = _scheduled_reminders.pop(booking_id, {})
    for t in d.values():
        try:
            t.cancel()
        except Exception:
            pass


async def _send_reminder(booking_id: int, kind: str, delay: float):
    await asyncio.sleep(delay)
    booking = await get_booking(booking_id)
    if not booking:
        logger.info(f"reminder_skip: booking {booking_id} not found")
        return
    if booking['status'] != 'scheduled':
        logger.info(f"reminder_skip: booking_id={booking_id} reason=not_scheduled status={booking['status']}")
        return
    flag_col = 'reminded_24' if kind == '24h' else 'reminded_1'
    if booking[flag_col]:
        logger.info(f"reminder_skip: booking_id={booking_id} reason=already_sent kind={kind}")
        return
    # send notification to user
    user = await get_user_by_id(booking['user_id'])
    if not user:
        logger.info(f"reminder_skip: booking_id={booking_id} no user")
        return
    tg = user['tg_id']
    if not tg:
        logger.info(f"reminder_skip: booking_id={booking_id} user_no_tg")
        return
    # Compose friendly message
    if kind == '24h':
        text = f"Напоминаем: у вас запись завтра {booking['date']} в {booking['time']}. Ждём вас!"
    else:
        text = f"Напоминание: сегодня у вас запись в {booking['time']}. До встречи!"
    try:
        await notify_user(tg, text)
        await set_reminder_sent(booking_id, kind)
        logger.info(f"reminder_sent: booking_id={booking_id} kind={kind}")
    except Exception:
        logger.exception(f"reminder_error: booking_id={booking_id} kind={kind}")
