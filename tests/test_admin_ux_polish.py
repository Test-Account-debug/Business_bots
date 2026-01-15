import importlib
import aiogram
from types import SimpleNamespace

# Patch decorator during import
_orig = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *a, **k: (lambda f: f)
admin_handlers = importlib.reload(importlib.import_module('app.handlers.admin'))
if _orig is not None:
    aiogram.Router.message = _orig

ADMIN_ID = 555000333
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


async def _start_master(mid):
    msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(mid))
    await admin_handlers.cmd_edit_master(msg)
    return msg


def test_master_prompts_friendly(temp_db):
    async def _run():
        mid = await __import__('app.repo', fromlist=['create_master']).create_master('A', 'B', 'C')
        msg = await _start_master(mid)
        t = msg.replies[-1]['text']
        assert 'пример' in t.lower()
        assert 'оставьте пустым' in t.lower()
        assert 'нажмите' not in t.lower()
    __import__('asyncio').run(_run())


def test_price_boundaries_accept_min_max(temp_db):
    async def _run():
        sid = await __import__('app.repo', fromlist=['create_service']).create_service('S', 'D', 1.0, 10)
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        start = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_edit_service(start)
        # name
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='N'))
        # price -> min
        min_price = str(admin_handlers.MIN_PRICE)
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text=min_price))
        # price accepted, next step should be duration
        # we'll check next prompt exists by sending an empty message to trigger next step
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text=''))
        assert admin_handlers.STAGED_EDITS[ADMIN_ID]['step'] in ('duration','description')
        # now test max price
        admin_handlers.STAGED_EDITS.pop(ADMIN_ID, None)
        start2 = FakeMessage(ADMIN_ID, ADMIN_ID, args=str(sid))
        await admin_handlers.cmd_edit_service(start2)
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text='N'))
        max_price = str(admin_handlers.MAX_PRICE)
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text=max_price))
        await admin_handlers.handle_staged_edit(FakeMessage(ADMIN_ID, ADMIN_ID, text=''))
        assert admin_handlers.STAGED_EDITS[ADMIN_ID]['step'] in ('duration','description')
    __import__('asyncio').run(_run())