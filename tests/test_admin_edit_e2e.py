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
    def __init__(self, user_id, chat_id, args='', text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self._args = args
        self.text = text
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
        self.edited = text


class FakeCallback:
    def __init__(self, data, user_id, message):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message
        self.answered = None

    async def answer(self, text, show_alert=False):
        self.answered = {'text': text, 'show_alert': show_alert}


def test_edit_master_e2e_apply_and_cancel(temp_db):
    async def _run():
        # create master
        mid = await create_master('OrigName', 'OrigBio', 'OrigContact')
        # start interactive edit
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        start_msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_edit_master(start_msg)
        # ensure staged
        assert ADMIN_ID in admin_handlers.STAGED_EDITS
        staged = admin_handlers.STAGED_EDITS[ADMIN_ID]
        assert staged['id'] == mid and staged['type'] == 'master'

        # send name
        name_msg = FakeMessage(ADMIN_ID, ADMIN_ID, text='NewName')
        await admin_handlers.handle_staged_edit(name_msg)
        # last reply on the name message should prompt for bio
        assert 'bio' in name_msg.replies[-1]['text'].lower()

        # send bio
        bio_msg = FakeMessage(ADMIN_ID, ADMIN_ID, text='NewBio')
        await admin_handlers.handle_staged_edit(bio_msg)
        # last reply on the bio message should prompt for contact
        assert 'контакт' in bio_msg.replies[-1]['text'].lower()

        # send contact and trigger confirmation
        contact_msg = FakeMessage(ADMIN_ID, ADMIN_ID, text='NewContact')
        await admin_handlers.handle_staged_edit(contact_msg)
        # summary should be in replies of the contact message
        summary = contact_msg.replies[-1]['text']
        assert 'Подтвердите изменения' in summary
        # simulate pressing Apply
        cbdata = f'confirm_apply_edit:master:{mid}:{ADMIN_ID}'
        cb_msg = FakeCallbackMessage(ADMIN_ID, start_msg.bot)
        cb = FakeCallback(cbdata, ADMIN_ID, cb_msg)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        await admin_handlers.cb_confirm_apply_edit(cb)
        # check DB updated
        m = await get_master(mid)
        assert m['name'] == 'NewName'
        assert m['bio'] == 'NewBio'
        assert m['contact'] == 'NewContact'
        assert cb_msg.edited is not None and 'применены' in cb_msg.edited.lower()

        # Now test cancel flow: start a new staging and then cancel
        # start again
        start_msg2 = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_edit_master(start_msg2)
        assert ADMIN_ID in admin_handlers.STAGED_EDITS
        # send name only
        nm = FakeMessage(ADMIN_ID, ADMIN_ID, text='ShouldNotApply')
        await admin_handlers.handle_staged_edit(nm)
        # cancel by callback
        cbdata2 = f'cancel_apply_edit:{ADMIN_ID}'
        cb_msg2 = FakeCallbackMessage(ADMIN_ID, start_msg2.bot)
        cb2 = FakeCallback(cbdata2, ADMIN_ID, cb_msg2)
        await admin_handlers.cb_cancel_apply_edit(cb2)
        # staged removed
        assert ADMIN_ID not in admin_handlers.STAGED_EDITS
        # DB unchanged (should still be previous NewName)
        m2 = await get_master(mid)
        assert m2['name'] == 'NewName'
        assert 'отмен' in cb_msg2.edited.lower()

    asyncio.run(_run())


def test_edit_master_invalid_inputs(temp_db):
    async def _run():
        mid = await create_master('Orig', 'B', 'C')
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        start = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
        await admin_handlers.cmd_edit_master(start)
        # too long name
        long_name = 'x' * (admin_handlers.MAX_NAME_LEN + 1)
        bad = FakeMessage(ADMIN_ID, ADMIN_ID, text=long_name)
        await admin_handlers.handle_staged_edit(bad)
        assert 'слишком длин' in bad.replies[-1]['text'].lower()
        # still on name step
        assert admin_handlers.STAGED_EDITS[ADMIN_ID]['step'] == 'name'
        # accept empty to keep current and proceed
        ok = FakeMessage(ADMIN_ID, ADMIN_ID, text='')
        await admin_handlers.handle_staged_edit(ok)
        assert admin_handlers.STAGED_EDITS[ADMIN_ID]['step'] == 'bio'
        # too long bio
        long_bio = 'y' * (admin_handlers.MAX_BIO_LEN + 1)
        bad_bio = FakeMessage(ADMIN_ID, ADMIN_ID, text=long_bio)
        await admin_handlers.handle_staged_edit(bad_bio)
        assert 'слишком длин' in bad_bio.replies[-1]['text'].lower()

    asyncio.run(_run())

def test_edit_service_e2e_apply_and_cancel(temp_db):
    async def _run():
        sid = await create_service('OrigSvc', 'Desc', 1.0, 10)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        start_msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_edit_service(start_msg)
        assert ADMIN_ID in admin_handlers.STAGED_EDITS
        staged = admin_handlers.STAGED_EDITS[ADMIN_ID]
        assert staged['id'] == sid and staged['type'] == 'service'

        # name
        n = FakeMessage(ADMIN_ID, ADMIN_ID, text='SvcNew')
        await admin_handlers.handle_staged_edit(n)
        # price
        p = FakeMessage(ADMIN_ID, ADMIN_ID, text='12.5')
        await admin_handlers.handle_staged_edit(p)
        # duration
        d = FakeMessage(ADMIN_ID, ADMIN_ID, text='45')
        await admin_handlers.handle_staged_edit(d)
        # description -> should present summary
        desc = FakeMessage(ADMIN_ID, ADMIN_ID, text='DescNew')
        await admin_handlers.handle_staged_edit(desc)
        summary = desc.replies[-1]['text']
        assert 'Подтвердите изменения' in summary
        cbdata = f'confirm_apply_edit:service:{sid}:{ADMIN_ID}'
        cb_msg = FakeCallbackMessage(ADMIN_ID, start_msg.bot)
        cb = FakeCallback(cbdata, ADMIN_ID, cb_msg)
        await admin_handlers.cb_confirm_apply_edit(cb)
        s = await get_service(sid)
        assert s['name'] == 'SvcNew'
        assert float(s['price']) == 12.5
        assert int(s['duration_minutes']) == 45
        assert s['description'] == 'DescNew'
        assert 'применены' in cb_msg.edited.lower()

        # negative cases for price/duration/description lengths
        # restart
        start2 = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_edit_service(start2)
        assert ADMIN_ID in admin_handlers.STAGED_EDITS
        # name OK
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='Ok'))
        # invalid price string
        bad_price = FakeMessage(ADMIN_ID, ADMIN_ID, text='abc')
        await admin_handlers.handle_staged_edit(bad_price)
        assert 'Неверный формат цены' in bad_price.replies[-1]['text']
        # price out of range
        huge_price = FakeMessage(ADMIN_ID, ADMIN_ID, text=str(admin_handlers.MAX_PRICE * 10))
        await admin_handlers.handle_staged_edit(huge_price)
        assert 'Цена должна быть между' in huge_price.replies[-1]['text']
        # now give valid price
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='50'))
        # invalid duration non-int
        bad_dur = FakeMessage(ADMIN_ID, ADMIN_ID, text='x')
        await admin_handlers.handle_staged_edit(bad_dur)
        assert 'Неверный формат длительности' in bad_dur.replies[-1]['text']
        # duration out of range
        large_dur = FakeMessage(ADMIN_ID, ADMIN_ID, text=str(admin_handlers.MAX_DURATION * 10))
        await admin_handlers.handle_staged_edit(large_dur)
        assert 'Длительность должна быть между' in large_dur.replies[-1]['text']
        # valid duration
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='30'))
        # too long description
        long_desc = FakeMessage(ADMIN_ID, ADMIN_ID, text='x' * (admin_handlers.MAX_DESC_LEN + 1))
        await admin_handlers.handle_staged_edit(long_desc)
        assert 'Описание слишком длинное' in long_desc.replies[-1]['text']

        # cancel flow
        start3 = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_edit_service(start3)
        assert ADMIN_ID in admin_handlers.STAGED_EDITS
        # cancel immediately
        cbdata2 = f'cancel_apply_edit:{ADMIN_ID}'
        cb_msg2 = FakeCallbackMessage(ADMIN_ID, start3.bot)
        cb2 = FakeCallback(cbdata2, ADMIN_ID, cb_msg2)
        await admin_handlers.cb_cancel_apply_edit(cb2)
        assert ADMIN_ID not in admin_handlers.STAGED_EDITS
        assert 'отмен' in cb_msg2.edited.lower()

    asyncio.run(_run())