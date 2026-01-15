#!/usr/bin/env python3
"""
Demo script for auto-review request feature.

This script simulates the end-to-end flow:
1. Admin marks booking as completed (/complete_booking)
2. Client receives review prompt and rates (1-5 stars)
3. Admins get notified

Usage: python demo.py
"""

import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch
from app.db import init_db
from app.repo import create_booking, get_booking, set_booking_status, get_user_by_id, get_or_create_user, create_service, create_master, list_reviews
from app.main import cmd_complete_booking
from app.handlers.reviews import cb_review_rating
# Mock classes for demo
class FakeMessage:
    def __init__(self, tg_id, text, args=None):
        self.from_user = type('User', (), {'id': tg_id})()
        self.text = text
        self._args = args

    def get_args(self):
        return self._args

class FakeCallbackMessage:
    def __init__(self, tg_id):
        self.from_user = type('User', (), {'id': tg_id})()

class FakeCallback:
    def __init__(self, data, tg_id, message):
        self.data = data
        self.from_user = type('User', (), {'id': tg_id})()
        self.message = message

class FakeState:
    def __init__(self):
        self.data = {}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return self.data

    async def clear(self):
        self.data.clear()

async def demo():
    print("🚀 Starting demo: Auto-review request after booking completion\n")

    # Mock bot
    mock_bot = AsyncMock()
    with patch('app.main.bot', mock_bot), patch('app.notify.bot', mock_bot):
        # Create temp DB
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name

        try:
            # Set DB path
            os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
            # Init DB
            await init_db()

            # Create test data: user, service, master, booking
            user = await get_or_create_user(123456789, "Test Client", "+1234567890")
            service = await create_service("Test Service", "Description", 100, 60)
            master = await create_master("Test Master")
            # Create booking directly with date/time
            booking_id = await create_booking(user['id'], service, master, "2026-01-15", "10:00", "Test Client", "+1234567890")

            print(f"✅ Created booking ID: {booking_id} for user {user['tg_id']}")

            # Step 1: Admin completes booking
            print("\n1️⃣ Admin runs /complete_booking")
            admin_msg = FakeMessage(987654321, "/complete_booking", args=str(booking_id))
            await cmd_complete_booking(admin_msg)
            print("   Booking marked as completed, review prompt sent to client")

            # Check booking status
            b = await get_booking(booking_id)
            assert b['status'] == 'completed', f"Expected 'completed', got {b['status']}"
            print(f"   Booking status: {b['status']}")

            # Step 2: Client rates (simulate button click)
            print("\n2️⃣ Client clicks rating button (5 stars)")
            cb_msg = FakeCallbackMessage(user['tg_id'])
            cb = FakeCallback(f'review:rating:5:booking:{booking_id}', user['tg_id'], cb_msg)
            state = FakeState()
            await cb_review_rating(cb, state)
            print("   Review saved, admin notified")

            # Verify review created
            reviews = await list_reviews()
            assert any(r['rating'] == 5 and r['user_id'] == user['id'] for r in reviews), "Review not found"
            print(f"   Review created: rating 5 for user {user['tg_id']}")

            print("\n🎉 Demo completed successfully!")
            print("   - Booking completed by admin")
            print("   - Client rated the service")
            print("   - Review saved to DB")
            print("   - Admins would be notified (mocked in this demo)")

        finally:
            os.unlink(db_path)

if __name__ == "__main__":
    asyncio.run(demo())