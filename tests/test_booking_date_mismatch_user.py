import asyncio
import importlib
import aiogram
from types import SimpleNamespace

# Patch decorator during import (same pattern)
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


def test_process_date_mismatched_user(temp_db):
    async def _run():
        from app.repo import create_service
        from datetime import date
        date_s = '2026-01-15'
        sid = await create_service('Sx', 'D', 10.0, 30)
        # state claims the booking was initiated by user 1
        state = FakeState({'service_id': sid, 'booking_user_id': 1, '_state': booking_handlers.BookingStates.DATE.state})
        # message arrives from user 2
        msg = FakeMessage(2, 2, text=date_s)
        await booking_handlers.process_date(msg, state)
        assert msg.replies, 'expected a reply explaining account mismatch'
        assert any('другой аккаунт' in r['text'].lower() for r in msg.replies), f'unexpected replies: {msg.replies}'
    asyncio.run(_run())
