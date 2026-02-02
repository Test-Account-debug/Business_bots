import asyncio
from types import SimpleNamespace

import importlib

# Patch aiogram Router.message decorator to be a no-op during import to avoid framework-specific registration errors in tests
import aiogram
_orig_router_message = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *args, **kwargs: (lambda f: f)
import importlib
admin_handlers = importlib.reload(importlib.import_module('app.handlers.admin'))
if _orig_router_message is not None:
    aiogram.Router.message = _orig_router_message

from app.repo import create_master, create_service, get_or_create_user, create_review

ADMIN_ID = 123456789
admin_handlers.ADMIN_IDS = [ADMIN_ID]


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_document(self, chat_id, document, filename=None, caption=None, disable_notification=False):
        data = None
        try:
            document.seek(0)
            data = document.read()
        except Exception:
            data = None
        self.sent.append({'chat_id': chat_id, 'filename': filename, 'caption': caption, 'data': data})


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
        item = {'text': text}
        item.update(kwargs)
        self.replies.append(item)


def test_admin_export_reviews_e2e(temp_db):
    async def _run():
        admin_handlers.ADMIN_IDS = [ADMIN_ID]
        mid = await create_master('ExporterR', 'bio', 'contact')
        sid = await create_service('S', 'desc', 5.0, 10)
        user = await get_or_create_user(999000998, 'U', '+37060000001')
        await create_review(user['id'], sid, mid, 4, 'Nice')
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args='')
        await admin_handlers.cmd_export_reviews(msg)
        assert len(msg.bot.sent) == 1
        sent = msg.bot.sent[0]
        assert sent['data'] is not None
        text = sent['data'].decode('utf-8') if isinstance(sent['data'], (bytes, bytearray)) else str(sent['data'])
        assert 'rating' in text or '4' in text
        assert 'Nice' in text
    __import__('asyncio').run(_run())
