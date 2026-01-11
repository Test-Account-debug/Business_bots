import asyncio
import importlib
import aiogram
from types import SimpleNamespace
from app.repo import create_master, create_service, list_reviews

# Patch decorator during import
_orig = getattr(aiogram.Router, 'message', None)
aiogram.Router.message = lambda *a, **k: (lambda f: f)
rev_handlers = importlib.reload(importlib.import_module('app.handlers.reviews'))
admin_handlers = importlib.reload(importlib.import_module('app.handlers.admin'))
if _orig is not None:
    aiogram.Router.message = _orig

ADMIN_ID = 555000333
rev_handlers = importlib.reload(importlib.import_module('app.handlers.reviews'))
admin_handlers.ADMIN_IDS = [ADMIN_ID]


class FakeMessage:
    def __init__(self, user_id, chat_id, args='', text=None):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self._args = args
        self.text = text
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


def test_leave_review_and_admin_list(temp_db):
    async def _run():
        mid = await create_master('MR','b','c')
        sid = await create_service('SR','D',12.0,30)
        # user leaves review
        user_id = 777000
        msg = FakeMessage(user_id, user_id, args=f"{sid}|{mid}|5|Very good")
        await rev_handlers.cmd_leave_review(msg)
        assert 'спасибо' in msg.replies[-1]['text'].lower()
        # admin lists reviews
        a = FakeMessage(ADMIN_ID, ADMIN_ID, args='')
        await rev_handlers.cmd_list_reviews(a)
        assert 'rating' in a.replies[-1]['text'].lower() or 'рейтинг' in a.replies[-1]['text'].lower()
    asyncio.run(_run())


def test_avg_rating_command(temp_db):
    async def _run():
        mid = await create_master('MA','b','c')
        sid = await create_service('SA','D',2.0,20)
        # create some reviews
        await rev_handlers.cmd_leave_review(FakeMessage(111,111,args=f"{sid}|{mid}|5|Great"))
        await rev_handlers.cmd_leave_review(FakeMessage(222,222,args=f"{sid}|{mid}|3|Ok"))
        # ask avg
        msg = FakeMessage(ADMIN_ID, ADMIN_ID, args=f"master|{mid}")
        await rev_handlers.cmd_avg_rating(msg)
        assert 'средняя оценка' in msg.replies[-1]['text'].lower()
    asyncio.run(_run())