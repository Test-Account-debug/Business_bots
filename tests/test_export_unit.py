import pytest
import csv
from io import BytesIO

from app.export import export_bookings_csv_bytes, export_reviews_csv_bytes
from app.repo import create_master, create_service, get_or_create_user, create_booking, create_review


def test_export_bookings_csv(temp_db):
    async def _run():
        mid = await create_master('UnitMaster', 'bio', 'contact')
        sid = await create_service('UService', 'desc', 1.0, 30)
        user = await get_or_create_user(555000111, 'U', '+100000000')
        d = '2026-02-02'
        t = '12:00'
        await create_booking(user['id'], sid, mid, d, t, user['name'], user['phone'])
        data = await export_bookings_csv_bytes()
        text = data.decode('utf-8')
        sio = BytesIO(data)
        text = sio.getvalue().decode('utf-8')
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        assert len(rows) == 1
        r = rows[0]
        assert r['date'] == d
        assert r['time'] == t
        assert r['service'] == 'UService'
        assert r['master'] == 'UnitMaster'
    __import__('asyncio').run(_run())


def test_export_reviews_csv(temp_db):
    async def _run():
        mid = await create_master('RMaster', 'bio', 'contact')
        sid = await create_service('RService', 'desc', 1.0, 30)
        user = await get_or_create_user(666000111, 'RUser', '+199999999')
        # create a review
        await create_review(user['id'], sid, mid, 5, 'Great')
        data = await export_reviews_csv_bytes()
        text = data.decode('utf-8')
        lines = text.splitlines()
        assert lines[0].split(',')[0].strip() == 'booking_id'
        assert '5' in text
        assert 'Great' in text
    __import__('asyncio').run(_run())
