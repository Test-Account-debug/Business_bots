from datetime import datetime, timedelta
from app.db import get_db

def hhmm_to_minutes(t: str) -> int:
    h, m = t.split(':')
    return int(h) * 60 + int(m)

def minutes_to_hhmm(m: int) -> str:
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"

async def set_schedule(master_id: int, weekday: int, start_time: str, end_time: str, slot_interval_minutes: int = None):
    async with get_db() as db:
        await db.execute('DELETE FROM master_schedule WHERE master_id=? AND weekday=?', (master_id, weekday))
        await db.execute('INSERT INTO master_schedule (master_id, weekday, start_time, end_time, slot_interval_minutes) VALUES (?,?,?,?,?)', (master_id, weekday, start_time, end_time, slot_interval_minutes))
        await db.commit()

async def add_exception(master_id: int, date_s: str, available: int = 1, start_time: str = None, end_time: str = None, note: str = None):
    async with get_db() as db:
        # upsert
        cur = await db.execute('SELECT id FROM master_exceptions WHERE master_id=? AND date=?', (master_id, date_s))
        row = await cur.fetchone()
        if row:
            await db.execute('UPDATE master_exceptions SET available=?, start_time=?, end_time=?, note=? WHERE id=?', (available, start_time, end_time, note, row['id']))
        else:
            await db.execute('INSERT INTO master_exceptions (master_id, date, start_time, end_time, available, note) VALUES (?,?,?,?,?,?)', (master_id, date_s, start_time, end_time, available, note))
        await db.commit()

async def list_exceptions(master_id: int):
    async with get_db() as db:
        cur = await db.execute('SELECT * FROM master_exceptions WHERE master_id=? ORDER BY date DESC', (master_id,))
        rows = await cur.fetchall()
        return rows

async def generate_slots(master_id: int, date_s: str, service_duration: int, buffer_min: int = 0):
    async with get_db() as db:
        # check exception
        cur = await db.execute('SELECT * FROM master_exceptions WHERE master_id=? AND date=?', (master_id, date_s))
        exc = await cur.fetchone()
        if exc and exc['available'] == 0:
            return []
        if exc and exc['start_time'] and exc['end_time']:
            start_time, end_time = exc['start_time'], exc['end_time']
        else:
            wd = datetime.fromisoformat(date_s).weekday()
            cur = await db.execute('SELECT start_time, end_time, slot_interval_minutes FROM master_schedule WHERE master_id=? AND weekday=?', (master_id, wd))
            row = await cur.fetchone()
            if not row:
                return []
            start_time, end_time = row['start_time'], row['end_time']
            slot_interval = row['slot_interval_minutes'] if row['slot_interval_minutes'] else (service_duration + buffer_min)
        slot_interval = locals().get('slot_interval', service_duration + buffer_min)

        start_min = hhmm_to_minutes(start_time)
        end_min = hhmm_to_minutes(end_time)
        step = slot_interval
        duration = service_duration

        # get existing bookings for that master/date
        cur = await db.execute('SELECT b.time as time, s.duration_minutes as duration FROM bookings b LEFT JOIN services s ON s.id=b.service_id WHERE b.master_id=? AND b.date=? AND b.status="scheduled"', (master_id, date_s))
        bookings = await cur.fetchall()
        booked_intervals = []
        for b in bookings:
            b_start = hhmm_to_minutes(b['time'])
            b_dur = b['duration'] if b['duration'] else service_duration
            booked_intervals.append((b_start, b_start + b_dur))

        slots = []
        cur_start = start_min
        while cur_start + duration <= end_min:
            cand_start = cur_start
            cand_end = cur_start + duration
            overlap = False
            for bi_start, bi_end in booked_intervals:
                if not (cand_end <= bi_start or cand_start >= bi_end):
                    overlap = True
                    break
            if not overlap:
                slots.append(minutes_to_hhmm(cand_start))
            cur_start += step

        return slots
