import asyncio
import importlib
import aiogram
from types import SimpleNamespace
from datetime import date

# Patch decorator during import (same pattern as other tests)
_orig = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *a, **k: (lambda f: f)
# ensure Text filter exists for decorator usage in handlers
import aiogram.filters as _f
_f.Text = lambda *a, **k: (lambda f: f)
# avoid TelegramEvent.register enforcing keyword checks during tests
try:
    import aiogram.dispatcher.event.telegram as _te
    _te.TelegramEvent.register = lambda *a, **k: None
except Exception:
    pass

booking_handlers = importlib.reload(importlib.import_module('app.handlers.booking'))
if _orig is not None:
    aiogram.Router.message = _orig

from app.scheduler import set_schedule, generate_slots
from app.repo import create_service, create_master, create_booking


class FakeState:
    def __init__(self, initial=None):
        self._data = dict(initial or {})
    async def update_data(self, **kwargs):
        self._data.update(kwargs)
    async def get_data(self):
        return dict(self._data)
    async def clear(self):
        self._data = {}


class FakeMessage:
    def __init__(self, user_id, chat_id, text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self.text = text
        self.replies = []
    async def answer(self, text, **kwargs):
        self.replies.append({'text': text, **kwargs})


def test_busy_master_shows_busy_label(temp_db):
    async def _run():
        # fixed date for test
        date_s = '2026-01-15'
        d = date.fromisoformat(date_s)
        wd = d.weekday()

        # create service and two masters
        sid = await create_service('S Busy', 'desc', 20.0, 30)
        mid_free = await create_master('M Free', 'b', 'c')
        mid_busy = await create_master('M Busy', 'b', 'c')

        # set schedules for both masters on that weekday
        await set_schedule(mid_free, wd, '09:00', '11:00')
        await set_schedule(mid_busy, wd, '09:00', '11:00')

        # generate slots for busy master and fill them with bookings
        slots = await generate_slots(mid_busy, date_s, 30)
        assert slots, 'expected slots to exist for busy master schedule'
        # create distinct users for each booking to avoid double-booking checks
        uid = 1000
        for t in slots:
            uid += 1
            await create_booking(uid, sid, mid_busy, date_s, t, f'User{uid}', f'+370600{uid}')

        # Now simulate client flow: state with service_id and DATE
        state = FakeState({'service_id': sid, '_state': booking_handlers.BookingStates.DATE.state})
        msg = FakeMessage(1, 1, text=date_s)
        await booking_handlers.process_date(msg, state)

        # last reply should include reply_markup with buttons; find button texts
        assert msg.replies, 'no replies found from process_date'
        # find last reply that contains reply_markup
        reply_with_kb = None
        for r in reversed(msg.replies):
            if 'reply_markup' in r:
                reply_with_kb = r
                break
        assert reply_with_kb is not None, 'no reply contained reply_markup'

        kb = reply_with_kb['reply_markup']
        # InlineKeyboardMarkup.inline_keyboard is a list of rows, each row is list of InlineKeyboardButton
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        # Expect to find a busy label for M Busy
        assert any('❌ занято' in t for t in texts), f'expected busy label in keyboard texts: {texts}'

    asyncio.run(_run())
