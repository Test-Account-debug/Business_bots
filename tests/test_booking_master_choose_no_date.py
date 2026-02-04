import asyncio
import importlib
import aiogram
from types import SimpleNamespace

# Patch decorator during import (same pattern)
_orig = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *a, **k: (lambda f: f)
import aiogram.filters as _f
_f.Text = lambda *a, **k: (lambda f: f)
try:
    import aiogram.dispatcher.event.telegram as _te
    _te.TelegramEvent.register = lambda *a, **k: None
except Exception:
    pass
booking_handlers = importlib.reload(importlib.import_module('app.handlers.booking'))
if _orig is not None:
    aiogram.Router.message = _orig

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
        self.replies = []
    async def answer(self, text, **kwargs):
        self.replies.append({'text': text, **kwargs})

class FakeCallback:
    def __init__(self, data, user_id, message):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message
    async def answer(self, text, show_alert=False):
        pass


def test_master_choose_without_date(temp_db):
    async def _run():
        from app.repo import create_service, create_master
        sid = await create_service('Sx', 'D', 10.0, 30)
        mid = await create_master('Mx', 'b', 'c')
        # state has service_id but no date
        state = FakeState({'service_id': sid})
        msg = FakeCallbackMessage(1)
        cb = FakeCallback(f'book:master_choose:{mid}', 1, msg)
        await booking_handlers.cb_master_choose(cb, state)
        # expect prompt to enter date
        assert msg.replies, 'no reply from cb_master_choose'
        assert any('введите дату' in r['text'].lower() for r in msg.replies), f'unexpected replies: {msg.replies}'
    asyncio.run(_run())
