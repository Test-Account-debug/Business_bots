import asyncio
import os
import pytest
from app.repo import create_master, get_master, update_master, delete_master, create_service, get_service, update_service, delete_service
from app.admin_utils import export_bookings_csv_bytes

def test_master_crud(temp_db):
    async def _run():
        mid = await create_master('A', 'bio', 'contact')
        m = await get_master(mid)
        assert m['name'] == 'A'
        await update_master(mid, name='B', bio='nb')
        m2 = await get_master(mid)
        assert m2['name'] == 'B' and m2['bio'] == 'nb'
        await delete_master(mid)
        m3 = await get_master(mid)
        assert m3 is None
    __import__('asyncio').run(_run())

def test_service_crud(temp_db):
    async def _run():
        sid = await create_service('S', 'desc', 5.0, 20)
        s = await get_service(sid)
        assert s['name'] == 'S'
        await update_service(sid, name='S2', price=7.0)
        s2 = await get_service(sid)
        assert s2['name'] == 'S2' and float(s2['price']) == 7.0
        await delete_service(sid)
        s3 = await get_service(sid)
        assert s3 is None
    __import__('asyncio').run(_run())

def test_export_bookings_csv(temp_db):
    async def _run():
        data = await export_bookings_csv_bytes()
        assert isinstance(data, bytes)
        assert len(data) > 0
    __import__('asyncio').run(_run())
