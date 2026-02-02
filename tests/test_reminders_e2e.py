import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from app.repo import create_service, create_master, create_booking, get_or_create_user, list_bookings, get_booking


@pytest.mark.asyncio
async def test_reminder_sent_for_scheduled_booking(temp_db):
    # create booking in past so reminder runs immediately
    base = datetime.now() - timedelta(hours=2)
    date_s = base.date().isoformat()
    time_s = base.time().strftime('%H:%M')
    sid = await create_service('R1', 'd', 10.0, 30)
    mid = await create_master('M1', 'bio', 'c')
    user = await get_or_create_user(9000, name='U', phone='+79000000000')
    await create_booking(user['id'], sid, mid, date_s, time_s, 'U', '+79000000000')
    bookings = await list_bookings()
    bid = bookings[0]['id']

    # Patch notify_user to capture calls
    import app.reminders as reminders
    with patch('app.reminders.notify_user', new_callable=AsyncMock) as mock_notify:
        # call send directly for 24h and 1h
        await reminders._send_reminder(bid, '24h', 0)
        await reminders._send_reminder(bid, '1h', 0)

    # Check flags updated in DB
    b = await get_booking(bid)
    assert b['reminded_24'] == 1
    assert b['reminded_1'] == 1


@pytest.mark.asyncio
async def test_no_reminder_for_cancelled_or_completed(temp_db):
    base = datetime.now() - timedelta(hours=2)
    date_s = base.date().isoformat()
    time_s = base.time().strftime('%H:%M')
    sid = await create_service('R2', 'd', 10.0, 30)
    mid = await create_master('M2', 'bio', 'c')
    user = await get_or_create_user(9001, name='U2', phone='+79000000001')
    await create_booking(user['id'], sid, mid, date_s, time_s, 'U2', '+79000000001')
    bookings = await list_bookings()
    bid = bookings[0]['id']

    from app.repo import set_booking_status
    await set_booking_status(bid, 'cancelled')

    import app.reminders as reminders
    with patch('app.reminders.notify_user', new_callable=AsyncMock) as mock_notify:
        await reminders._send_reminder(bid, '24h', 0)
        await reminders._send_reminder(bid, '1h', 0)
    # flags should remain 0
    b = await get_booking(bid)
    assert b['reminded_24'] == 0
    assert b['reminded_1'] == 0
