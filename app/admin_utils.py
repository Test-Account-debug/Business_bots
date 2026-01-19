import csv
import os
from io import StringIO
from app.db import get_db


async def export_bookings_csv_bytes():
    """Return CSV content as bytes (utf-8)."""
    db = await get_db()
    cur = await db.execute('SELECT * FROM bookings')
    rows = await cur.fetchall()
    cols = [col[0] for col in cur.description]
    await db.close()

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r[c] for c in cols])
    csv_text = sio.getvalue()
    return csv_text.encode('utf-8')


async def export_reviews_csv_bytes():
    """Return reviews CSV content as bytes (utf-8)."""
    db = await get_db()
    cur = await db.execute('SELECT * FROM reviews')
    rows = await cur.fetchall()
    cols = [col[0] for col in cur.description]
    await db.close()

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r[c] for c in cols])
    csv_text = sio.getvalue()
    return csv_text.encode('utf-8')
