from datetime import datetime, timedelta
from app.reminders import compute_reminder_times


def test_compute_reminder_times():
    date_s = (datetime.now() + timedelta(days=2)).date().isoformat()
    time_s = '12:30'
    times = compute_reminder_times(date_s, time_s)
    booking = times['booking']
    assert booking.hour == 12 and booking.minute == 30
    assert times['24h'] == booking - timedelta(hours=24)
    assert times['1h'] == booking - timedelta(hours=1)
