import csv
import os
from io import StringIO
from app.db import get_db


async def export_bookings_csv_bytes():
    """Return CSV content as bytes (utf-8)."""
    async with get_db() as db:
        cur = await db.execute('SELECT * FROM bookings')
        rows = await cur.fetchall()
        cols = [col[0] for col in cur.description]

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r[c] for c in cols])
    csv_text = sio.getvalue()
    return csv_text.encode('utf-8')


async def export_bookings_csv_bytes_friendly():
    """New friendly CSV format delegating to app.export (id,date,time,service,master,client_name,phone,status)."""
    from app.export import export_bookings_csv_bytes as _exp
    return await _exp()


async def export_bookings_csv(path='export/bookings.csv'):
    """Backward-compatible helper that writes CSV to disk and returns path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = await export_bookings_csv_bytes()
    with open(path, 'wb') as f:
        f.write(data)
    return path
