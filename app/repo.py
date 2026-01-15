from app.db import get_db
from datetime import date
import aiosqlite

class SlotTaken(Exception):
    pass

class DoubleBooking(Exception):
    pass

async def get_or_create_user(tg_id: int, name: str = None, phone: str = None):
    db = await get_db()
    cur = await db.execute('SELECT * FROM users WHERE tg_id=?', (tg_id,))
    row = await cur.fetchone()
    if row:
        await db.close()
        return row
    cur = await db.execute('INSERT INTO users (tg_id, name, phone) VALUES (?,?,?)', (tg_id, name, phone))
    await db.commit()
    user_id = cur.lastrowid
    cur = await db.execute('SELECT * FROM users WHERE id=?', (user_id,))
    row = await cur.fetchone()
    await db.close()
    return row

async def list_services():
    db = await get_db()
    cur = await db.execute('SELECT * FROM services')
    rows = await cur.fetchall()
    await db.close()
    return rows

async def create_service(name, description, price, duration_minutes=30):
    db = await get_db()
    cur = await db.execute('INSERT INTO services (name, description, price, duration_minutes) VALUES (?,?,?,?)', (name, description, price, duration_minutes))
    await db.commit()
    await db.close()
    return cur.lastrowid

async def update_service(service_id: int, name: str = None, description: str = None, price: float = None, duration_minutes: int = None):
    db = await get_db()
    fields = []
    params = []
    if name is not None:
        fields.append('name=?')
        params.append(name)
    if description is not None:
        fields.append('description=?')
        params.append(description)
    if price is not None:
        fields.append('price=?')
        params.append(price)
    if duration_minutes is not None:
        fields.append('duration_minutes=?')
        params.append(duration_minutes)
    if not fields:
        await db.close()
        return
    params.append(service_id)
    sql = f"UPDATE services SET {', '.join(fields)} WHERE id=?"
    await db.execute(sql, tuple(params))
    await db.commit()
    await db.close()

async def delete_service(service_id: int):
    db = await get_db()
    await db.execute('DELETE FROM services WHERE id=?', (service_id,))
    await db.commit()
    await db.close()

async def get_service(service_id: int):
    db = await get_db()
    cur = await db.execute('SELECT * FROM services WHERE id=?', (service_id,))
    row = await cur.fetchone()
    await db.close()
    return row

async def list_masters():
    db = await get_db()
    cur = await db.execute('SELECT * FROM masters')
    rows = await cur.fetchall()
    await db.close()
    return rows

async def get_master(master_id: int):
    db = await get_db()
    cur = await db.execute('SELECT * FROM masters WHERE id=?', (master_id,))
    row = await cur.fetchone()
    await db.close()
    return row

async def create_master(name, bio=None, contact=None):
    db = await get_db()
    cur = await db.execute('INSERT INTO masters (name, bio, contact) VALUES (?,?,?)', (name, bio, contact))
    await db.commit()
    await db.close()
    return cur.lastrowid

async def update_master(master_id: int, name: str = None, bio: str = None, contact: str = None):
    db = await get_db()
    # build dynamic update
    fields = []
    params = []
    if name is not None:
        fields.append('name=?')
        params.append(name)
    if bio is not None:
        fields.append('bio=?')
        params.append(bio)
    if contact is not None:
        fields.append('contact=?')
        params.append(contact)
    if not fields:
        await db.close()
        return
    params.append(master_id)
    sql = f"UPDATE masters SET {', '.join(fields)} WHERE id=?"
    await db.execute(sql, tuple(params))
    await db.commit()
    await db.close()

async def delete_master(master_id: int):
    db = await get_db()
    await db.execute('DELETE FROM masters WHERE id=?', (master_id,))
    await db.commit()
    await db.close()

async def set_master_schedule(master_id: int, weekday: int, start_time: str, end_time: str, slot_interval_minutes: int = None):
    db = await get_db()
    await db.execute('DELETE FROM master_schedule WHERE master_id=? AND weekday=?', (master_id, weekday))
    await db.execute('INSERT INTO master_schedule (master_id, weekday, start_time, end_time, slot_interval_minutes) VALUES (?,?,?,?,?)', (master_id, weekday, start_time, end_time, slot_interval_minutes))
    await db.commit()
    await db.close()

async def user_has_active_booking(user_id: int):
    today = date.today().isoformat()
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) as c FROM bookings WHERE user_id=? AND status='scheduled' AND date>=?", (user_id, today))
    row = await cur.fetchone()
    await db.close()
    return row['c'] > 0

async def create_booking(user_id, service_id, master_id, date_s, time_s, name, phone):
    db = await get_db()
    try:
        await db.execute('BEGIN')
        # check user active booking
        cur = await db.execute("SELECT COUNT(*) as c FROM bookings WHERE user_id=? AND status='scheduled' AND date>=?", (user_id, date.today().isoformat()))
        r = await cur.fetchone()
        if r['c'] > 0:
            raise DoubleBooking()
        # try to insert; unique index on (master_id,date,time) prevents duplicates from races
        import time
        from sqlite3 import OperationalError
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                await db.execute('INSERT INTO bookings (user_id, service_id, master_id, date, time, status, name, phone) VALUES (?,?,?,?,?,?,?,?)', (user_id, service_id, master_id, date_s, time_s, 'scheduled', name, phone))
                await db.commit()
                break
            except OperationalError as e:
                # transient DB locked — retry a few times
                if 'locked' in str(e).lower():
                    if attempt < max_attempts - 1:
                        await db.rollback()
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    else:
                        await db.rollback()
                        raise SlotTaken()
                raise
            except Exception as e:
                err_msg = str(e).lower()
                if 'unique' in err_msg or 'constraint' in err_msg:
                    await db.rollback()
                    raise SlotTaken()
                await db.rollback()
                raise
    except Exception:
        await db.rollback()
        await db.close()
        raise
    await db.close()

async def list_bookings():
    db = await get_db()
    cur = await db.execute('SELECT * FROM bookings ORDER BY date DESC, time DESC')
    rows = await cur.fetchall()
    await db.close()
    return rows


async def get_booking(booking_id: int):
    db = await get_db()
    cur = await db.execute('SELECT * FROM bookings WHERE id=?', (booking_id,))
    row = await cur.fetchone()
    await db.close()
    return row


async def set_booking_status(booking_id: int, status: str):
    db = await get_db()
    await db.execute('UPDATE bookings SET status=? WHERE id=?', (status, booking_id))
    await db.commit()
    await db.close()

async def get_user_by_id(user_id: int):
    db = await get_db()
    cur = await db.execute('SELECT * FROM users WHERE id=?', (user_id,))
    row = await cur.fetchone()
    await db.close()
    return row


async def add_exception(master_id: int, date_s: str, available: int = 1, start_time: str = None, end_time: str = None, note: str = None):
    db = await get_db()
    # upsert
    cur = await db.execute('SELECT id FROM master_exceptions WHERE master_id=? AND date=?', (master_id, date_s))
    row = await cur.fetchone()
    if row:
        await db.execute('UPDATE master_exceptions SET available=?, start_time=?, end_time=?, note=? WHERE id=?', (available, start_time, end_time, note, row['id']))
    else:
        await db.execute('INSERT INTO master_exceptions (master_id, date, start_time, end_time, available, note) VALUES (?,?,?,?,?,?)', (master_id, date_s, start_time, end_time, available, note))
    await db.commit()
    await db.close()

async def list_exceptions(master_id: int):
    db = await get_db()
    cur = await db.execute('SELECT * FROM master_exceptions WHERE master_id=? ORDER BY date DESC', (master_id,))
    rows = await cur.fetchall()
    await db.close()
    return rows

# Manual request CRUD (for cases when no slots available)
async def create_manual_request(user_id: int, text: str):
    db = await get_db()
    cur = await db.execute('INSERT INTO manual_requests (user_id, text, processed) VALUES (?,?,0)', (user_id, text))
    await db.commit()
    await db.close()
    return cur.lastrowid

async def list_manual_requests(limit: int = 100):
    db = await get_db()
    cur = await db.execute('SELECT * FROM manual_requests ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = await cur.fetchall()
    await db.close()
    return rows

async def set_manual_request_processed(request_id: int, processed: int = 1):
    db = await get_db()
    await db.execute('UPDATE manual_requests SET processed=? WHERE id=?', (processed, request_id))
    await db.commit()
    await db.close()

# Reviews CRUD and aggregation
async def create_review(user_id: int, service_id: int = None, master_id: int = None, rating: int = 5, text: str = None):
    db = await get_db()
    cur = await db.execute('INSERT INTO reviews (user_id, service_id, master_id, rating, text) VALUES (?,?,?,?,?)', (user_id, service_id, master_id, rating, text))
    await db.commit()
    await db.close()
    return cur.lastrowid

async def get_review(review_id: int):
    db = await get_db()
    cur = await db.execute('SELECT * FROM reviews WHERE id=?', (review_id,))
    row = await cur.fetchone()
    await db.close()
    return row

async def delete_review(review_id: int):
    db = await get_db()
    await db.execute('DELETE FROM reviews WHERE id=?', (review_id,))
    await db.commit()
    await db.close()

async def list_reviews(service_id: int = None, master_id: int = None, limit: int = None):
    db = await get_db()
    sql = 'SELECT r.*, u.tg_id as user_tg_id FROM reviews r LEFT JOIN users u ON r.user_id = u.id'
    where = []
    params = []
    if service_id is not None:
        where.append('r.service_id=?')
        params.append(service_id)
    if master_id is not None:
        where.append('r.master_id=?')
        params.append(master_id)
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY r.created_at DESC'
    if limit:
        sql += f' LIMIT {int(limit)}'
    cur = await db.execute(sql, tuple(params))
    rows = await cur.fetchall()
    await db.close()
    return rows

async def average_rating_for_master(master_id: int):
    db = await get_db()
    cur = await db.execute('SELECT AVG(rating) as avg, COUNT(*) as cnt FROM reviews WHERE master_id=?', (master_id,))
    row = await cur.fetchone()
    await db.close()
    return (row['avg'] or 0.0, row['cnt'] or 0)

async def average_rating_for_service(service_id: int):
    db = await get_db()
    cur = await db.execute('SELECT AVG(rating) as avg, COUNT(*) as cnt FROM reviews WHERE service_id=?', (service_id,))
    row = await cur.fetchone()
    await db.close()
    return (row['avg'] or 0.0, row['cnt'] or 0)