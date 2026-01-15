import asyncio
import importlib
import aiogram
from types import SimpleNamespace
from app.repo import create_service, create_master, create_booking, create_review, get_or_create_user, get_review

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

reviews_handlers = importlib.reload(importlib.import_module('app.handlers.reviews'))
if _orig is not None:
    aiogram.Router.message = _orig

from app.repo import list_reviews, get_review

class FakeState:
    def __init__(self, initial=None):
        self._data = dict(initial or {})
    async def update_data(self, **kwargs):
        self._data.update(kwargs)
    async def get_data(self):
        return dict(self._data)
    async def clear(self):
        self._data = {}
    async def get_state(self):
        return self._data.get('_state')

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
    async def answer(self, text='', show_alert=False):
        self.answered = {'text': text, 'show_alert': show_alert}


async def _create_completed_booking(tmp_db):
    # create service/master/user and a booking with status 'completed'
    sid = await create_service('S','d',10.0,30)
    mid = await create_master('M','b','c')
    user = await get_or_create_user(777, name='User777', phone='+7000000777')
    await create_booking(user['id'], sid, mid, '2026-01-10', '09:00', 'User', '+7000000777')
    # mark booking completed
    from app.repo import set_booking_status, get_booking
    rows = await list_reviews()
    # get booking id
    from app.repo import list_bookings
    bs = await list_bookings()
    bid = bs[0]['id']
    await set_booking_status(bid, 'completed')
    return bid, user, sid, mid


def test_rating_callback_creates_review(temp_db):
    async def _run():
        bid, user, sid, mid = await _create_completed_booking(temp_db)
        # monkeypatch notify_admins to capture calls
        import app.notify as notify_mod
        calls = []
        async def fake_notify(text):
            calls.append(text)
        notify_mod.notify_admins = fake_notify
        # user clicks rating button
        cb_msg = FakeCallbackMessage(1)
        cb = FakeCallback(f'review:rating:5:booking:{bid}', user['id'], cb_msg)
        state = FakeState()
        await reviews_handlers.cb_review_rating(cb, state)
        # assert review exists
        rows = await list_reviews()
        assert any(r['rating'] == 5 and r['user_id'] == user['id'] for r in rows)
        # admin notified
        assert calls, 'notify_admins should have been called'
    asyncio.run(_run())


def test_interactive_review_flow(temp_db):
    async def _run():
        bid, user, sid, mid = await _create_completed_booking(temp_db)
        # start interactive flow
        cb_msg = FakeCallbackMessage(1)
        cb = FakeCallback(f'review:text:booking:{bid}', user['id'], cb_msg)
        state = FakeState()
        # user clicked 'Оставить комментарий'
        await reviews_handlers.cb_review_text_start(cb, state)
        # now user sends rating
        rating_msg = FakeMessage(user['id'], 1, text='4')
        await reviews_handlers.r_review_rating(rating_msg, state)
        # should prompt for comment
        assert 'комментар' in rating_msg.replies[-1]['text'].lower()
        # send comment
        comment_msg = FakeMessage(user['id'], 1, text='Хорошо')
        await reviews_handlers.r_review_text(comment_msg, state)
        rows = await list_reviews()
        assert any(r['rating'] == 4 and 'Хорошо' in (r['text'] or '') for r in rows)
    asyncio.run(_run())
