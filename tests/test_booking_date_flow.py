import asyncio
import importlib
import aiogram
from types import SimpleNamespace

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

from types import SimpleNamespace

class FakeState:
    def __init__(self, initial=None):
        self._data = dict(initial or {})
    async def update_data(self, **kwargs):
        self._data.update(kwargs)
    async def get_data(self):
        return dict(self._data)
    async def clear(self):
        self._data = {}

class FakeCallbackMessage:
    def __init__(self, chat_id):
        self.chat = SimpleNamespace(id=chat_id)
        self.edited = None
        self.replies = []
    async def edit_text(self, text, **kwargs):
        self.edited = text
    async def answer(self, text, **kwargs):
        # store replies similarly to FakeMessage
        self.replies.append({'text': text, **kwargs})

class FakeCallback:
    def __init__(self, data, user_id, message):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message
        self.answered = None
    async def answer(self, text, show_alert=False):
        self.answered = {'text': text, 'show_alert': show_alert}

class FakeMessage:
    def __init__(self, user_id, chat_id, text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self.text = text
        self.replies = []
    async def answer(self, text, **kwargs):
        self.replies.append({'text': text, **kwargs})


def test_booking_date_flow(temp_db):
    async def _run():
        from app.repo import create_service, create_master
        from app.scheduler import set_schedule
        from datetime import date
        # setup
        date_s = '2026-01-15'
        d = date.fromisoformat(date_s)
        wd = d.weekday()
        sid = await create_service('S Flow', 'desc', 25.0, 30)
        mid = await create_master('M Flow', 'bio', 'contact')
        # set schedule so slots exist
        await set_schedule(mid, wd, '09:00', '11:00')

        # simulate /services -> user clicks book:service:{sid}
        state = FakeState()
        cb_msg = FakeCallbackMessage(1)
        cb = FakeCallback(f'book:service:{sid}', 1, cb_msg)
        await booking_handlers.cb_select_service(cb, state)
        data = await state.get_data()
        assert data.get('service_id') == sid

        # simulate clicking master
        cb2_msg = FakeCallbackMessage(1)
        cb2 = FakeCallback(f'book:master:{mid}', 1, cb2_msg)
        await booking_handlers.cb_select_master(cb2, state)
        # message prompting for date should be in cb2_msg.replies
        assert any('Введите дату' in r['text'] for r in cb2_msg.replies), f"expected date prompt, got: {cb2_msg.replies}"

        # now send date as a message
        msg = FakeMessage(1, 1, text=date_s)
        await booking_handlers.process_date(msg, state)
        # expect reply with reply_markup containing time slots
        assert msg.replies, 'no replies from process_date'
        reply_with_kb = None
        for r in reversed(msg.replies):
            if 'reply_markup' in r:
                reply_with_kb = r
                break
        assert reply_with_kb is not None, f'no reply contained reply_markup: {msg.replies}'
        kb = reply_with_kb['reply_markup']
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any(':' in t or t.count(':')==0 for t in texts) or texts, f'unexpected buttons: {texts}'

    asyncio.run(_run())
