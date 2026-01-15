import asyncio
import importlib
import aiogram
from types import SimpleNamespace
from app.repo import list_manual_requests

# Patch decorator during import
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

ADMIN_ID = 555000333

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

class FakeCallbackMessage:
    def __init__(self, chat_id):
        self.chat = SimpleNamespace(id=chat_id)
        self.edited = None
    async def edit_text(self, text):
        self.edited = text
    async def answer(self, text):
        self.edited = text

class FakeCallback:
    def __init__(self, data, user_id, message):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message
        self.answered = None
    async def answer(self, text, show_alert=False):
        self.answered = {'text': text, 'show_alert': show_alert}


def test_manual_request_flow_no_slots(temp_db):
    async def _run():
        from app.repo import create_service
        sid = await create_service('Sx', 'D', 10.0, 30)
        state = FakeState({'service_id': sid})
        # start manual request (no master specified)
        msg = FakeCallbackMessage(123)
        cb = FakeCallback('manual:request:start', 111, msg)
        # call start
        await booking_handlers.cb_manual_start(cb, state)
        # send prefer
        pref_msg = FakeMessage(111, 111, text='утром')
        await booking_handlers.mr_prefer(pref_msg, state)
        assert 'имя' in pref_msg.replies[-1]['text'].lower()
        # send name
        name_msg = FakeMessage(111, 111, text='Ivan')
        await booking_handlers.mr_name(name_msg, state)
        assert 'телефон' in name_msg.replies[-1]['text'].lower()
        # send phone
        phone_msg = FakeMessage(111, 111, text='+37061234567')
        await booking_handlers.mr_phone(phone_msg, state)
        # confirm callback
        conf_cb_msg = FakeCallbackMessage(111)
        conf_cb = FakeCallback('manual:request:confirm', 111, conf_cb_msg)
        await booking_handlers.cb_manual_confirm(conf_cb, state)
        rows = await list_manual_requests()
        assert any('Ivan' in r['text'] and '+37061234567' in r['text'] for r in rows)
    asyncio.run(_run())


def test_manual_request_for_specific_master(temp_db):
    async def _run():
        from app.repo import create_service, create_master
        sid = await create_service('S2','D',5.0,30)
        mid = await create_master('M2','b','c')
        state = FakeState({'service_id': sid})
        # start manual for specific master
        msg = FakeCallbackMessage(222)
        cb = FakeCallback(f'manual:request:start:master:{mid}', 222, msg)
        await booking_handlers.cb_manual_start(cb, state)
        # prefer
        await booking_handlers.mr_prefer(FakeMessage(222,222,text='после 16:00'), state)
        await booking_handlers.mr_name(FakeMessage(222,222,text='Olga'), state)
        await booking_handlers.mr_phone(FakeMessage(222,222,text='+37061230000'), state)
        conf_cb = FakeCallback('manual:request:confirm', 222, FakeCallbackMessage(222))
        await booking_handlers.cb_manual_confirm(conf_cb, state)
        rows = await list_manual_requests()
        assert any('Olga' in r['text'] and 'master=' in r['text'] for r in rows)
    asyncio.run(_run())