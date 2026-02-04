import csv
from io import StringIO
from app.repo import get_bookings_for_export, get_reviews_for_export


async def export_bookings_csv_bytes():
    rows = await get_bookings_for_export()
    # cur.description not available here; build header explicitly
    cols = ['id', 'date', 'time', 'service', 'master', 'client_name', 'phone', 'status']
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r[c] for c in cols])
    return sio.getvalue().encode('utf-8')


async def export_reviews_csv_bytes():
    rows = await get_reviews_for_export()
    cols = ['booking_id', 'rating', 'comment', 'created_at']
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(cols)
    for r in rows:
        # r['booking_id'] may be None
        writer.writerow([r['booking_id'], r['rating'], r['comment'] or '', r['created_at']])
    return sio.getvalue().encode('utf-8')


#kiek isviso siame projekte parasyta kodo eiliu?
