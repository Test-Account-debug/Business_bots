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
OTHER_ID = 999999111
admin_handlers.ADMIN_IDS = [ADMIN_ID]


class FakeMessage:
    def __init__(self, user_id, chat_id, args='', text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self._args = args
        self.text = text
        self.bot = SimpleNamespace()
        self.replies = []

    def get_args(self):
        return self._args

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


def test_non_admin_cannot_start_edit(temp_db):
    async def _run():
        mid = await create_master('M', 'b', 'c')
        msg = FakeMessage(OTHER_ID, OTHER_ID, args=str(mid))
        # ensure other user is not admin
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        await admin_handlers.cmd_edit_master(msg)
        assert msg.replies[-1]['text'].lower().startswith('доступ запрещён')
    asyncio.run(_run())


def test_only_author_can_confirm_apply(temp_db):
    async def _run():
        mid = await create_master('AU', 'b', 'c')
        admin_handlers.ADMIN_IDS = [ADMIN_ID, OTHER_ID]
        start = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_edit_master(start)
        # walk to confirmation quickly
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='N'))
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='B'))
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='C'))
        # attempt confirm by other admin
        cbdata = f'confirm_apply_edit:master:{mid}:{ADMIN_ID}'
        cb_msg = FakeCallbackMessage(ADMIN_ID)
        cb = FakeCallback(cbdata, OTHER_ID, cb_msg)
        await admin_handlers.cb_confirm_apply_edit(cb)
        # should get an alert that only author can confirm
        assert cb.answered is not None and 'только автор' in cb.answered['text'].lower()
        # staged edit should still be present
        assert ADMIN_ID in admin_handlers.STAGED_EDITS
        # now real author applies
        cb2 = FakeCallback(cbdata, ADMIN_ID, cb_msg)
        await admin_handlers.cb_confirm_apply_edit(cb2)
        m = await get_master(mid)
        assert m['name'] == 'N'
    asyncio.run(_run())


def test_price_and_duration_negative_boundaries(temp_db):
    async def _run():
        sid = await create_service('Svc', 'D', 1.0, 10)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        start = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_edit_service(start)
        # name ok
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='Good'))
        # price negative
        p_neg = FakeMessage(ADMIN_ID, ADMIN_ID, text='-5')
        await admin_handlers.handle_staged_edit(p_neg)
        assert 'Цена должна быть между' in p_neg.replies[-1]['text']
        # zero duration
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='10'))
        bad_dur = FakeMessage(ADMIN_ID, ADMIN_ID, text='0')
        await admin_handlers.handle_staged_edit(bad_dur)
        assert 'Длительность должна быть между' in bad_dur.replies[-1]['text']
    asyncio.run(_run())


def test_whitespace_inputs_treated_as_empty_and_keep_values(temp_db):
    async def _run():
        mid = await create_master('Orig', 'B', 'C')
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        start = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_edit_master(start)
        # whitespace name -> treated as empty -> keep current and move to bio
        ws_name = FakeMessage(ADMIN_ID, ADMIN_ID, text='   ')
        await admin_handlers.handle_staged_edit(ws_name)
        assert admin_handlers.STAGED_EDITS[ADMIN_ID]['step'] == 'bio'
        # whitespace bio -> keep
        ws_bio = FakeMessage(ADMIN_ID, ADMIN_ID, text=' \t ')
        await admin_handlers.handle_staged_edit(ws_bio)
        assert admin_handlers.STAGED_EDITS[ADMIN_ID]['step'] == 'contact'
        # whitespace contact -> keep -> confirmation
        ws_ct = FakeMessage(ADMIN_ID, ADMIN_ID, text='  ')
        await admin_handlers.handle_staged_edit(ws_ct)
        # confirmation message present
        summary = ws_ct.replies[-1]['text']
        assert 'Подтвердите изменения' in summary
    asyncio.run(_run())
