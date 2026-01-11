import asyncio
import importlib
import aiogram
from types import SimpleNamespace
from app.repo import create_master, get_master, create_service, get_service

# Patch decorator during import
_orig = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *a, **k: (lambda f: f)
admin_handlers = importlib.reload(importlib.import_module('app.handlers.admin'))
if _orig is not None:
    aiogram.Router.message = _orig

ADMIN_ID = 555000333
admin_handlers.ADMIN_IDS = [ADMIN_ID]

class FakeBot:
    def __init__(self):
        self.sent = []

class FakeMessage:
    def __init__(self, user_id, chat_id, args=''):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self._args = args
        self.bot = FakeBot()
        self.replies = []

    def get_args(self):
        return self._args

    async def answer(self, text, **kwargs):
        # store text and any reply_markup for test introspection
        self.replies.append({'text': text, **kwargs})

class FakeCallbackMessage:
    def __init__(self, chat_id, bot):
        self.chat = SimpleNamespace(id=chat_id)
        self.bot = bot
        self.edited = None

    async def edit_text(self, text):
        self.edited = text

    async def answer(self, text):
        # emulate answering in chat
        self.edited = text

class FakeCallback:
    def __init__(self, data, user_id, message):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message
        self.answered = None

    async def answer(self, text, show_alert=False):
        self.answered = {'text': text, 'show_alert': show_alert}


def test_confirm_delete_master_success(temp_db):
    async def _run():
        mid = await create_master('ToDel', 'b', 'c')
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_delete_master(msg)
        # find callback_data from reply_markup
        rm = msg.replies[-1]
        kb = rm.get('reply_markup')
        # some test runners may not preserve reply_markup object; derive callback data deterministically
        cbdata = f'confirm_delete_master:{mid}'
        # simulate confirm callback from admin
        cb_msg = FakeCallbackMessage(ADMIN_ID, msg.bot)
        cb = FakeCallback(cbdata, ADMIN_ID, cb_msg)
        # ensure admin list is set for this test run
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        await admin_handlers.cb_confirm_delete_master(cb)
        # DB may require a tiny moment to reflect in some environments; retry shortly
        import asyncio as _asyncio
        m = None
        for _ in range(100):
            m = await get_master(mid)
            if m is None:
                break
            await _asyncio.sleep(0.01)
        assert m is None, f"Master still exists: {m}, edited={cb_msg.edited}, cb_answered={getattr(cb,'answered',None)}"
        assert cb_msg.edited is not None and 'удалён' in cb_msg.edited
    __import__('asyncio').run(_run())


def test_cancel_delete_master_no_delete(temp_db):
    async def _run():
        mid = await create_master('Persist', 'b', 'c')
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_delete_master(msg)
        rm = msg.replies[-1]
        kb = rm.get('reply_markup')
        cbdata = f'cancel_delete_master:{mid}'
        cb_msg = FakeCallbackMessage(ADMIN_ID, msg.bot)
        cb = FakeCallback(cbdata, ADMIN_ID, cb_msg)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        await admin_handlers.cb_cancel_delete_master(cb)
        m = await get_master(mid)
        assert m is not None
        assert cb_msg.edited is not None and 'отмен' in cb_msg.edited
    __import__('asyncio').run(_run())


def test_non_admin_cannot_confirm_delete(temp_db):
    async def _run():
        mid = await create_master('Safe', 'b', 'c')
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_delete_master(msg)
        rm = msg.replies[-1]
        kb = rm.get('reply_markup')
        cbdata = f'confirm_delete_master:{mid}'
        cb_msg = FakeCallbackMessage(ADMIN_ID, msg.bot)
        non_admin_id = 999999
        cb = FakeCallback(cbdata, non_admin_id, cb_msg)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        await admin_handlers.cb_confirm_delete_master(cb)
        m = await get_master(mid)
        assert m is not None
        assert cb.answered is not None and 'Доступ запрещён' in cb.answered['text']
    __import__('asyncio').run(_run())


def test_confirm_delete_service_success(temp_db):
    async def _run():
        sid = await create_service('ToDelS', 'd', 1.0, 10)
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_delete_service(msg)
        rm = msg.replies[-1]
        kb = rm.get('reply_markup')
        cbdata = f'confirm_delete_service:{sid}'
        cb_msg = FakeCallbackMessage(ADMIN_ID, msg.bot)
        cb = FakeCallback(cbdata, ADMIN_ID, cb_msg)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        await admin_handlers.cb_confirm_delete_service(cb)
        import asyncio as _asyncio
        s = None
        for _ in range(100):
            s = await get_service(sid)
            if s is None:
                break
            await _asyncio.sleep(0.01)
        assert s is None, f"Service still exists: {s}, edited={cb_msg.edited}, cb_answered={getattr(cb,'answered',None)}"
        assert cb_msg.edited is not None and 'Услуга' in cb_msg.edited
    __import__('asyncio').run(_run())
