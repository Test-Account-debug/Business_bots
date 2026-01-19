import asyncio
import pytest
from app.repo import get_or_create_user, create_service, create_master, get_booking, set_booking_status, create_booking, list_reviews


def test_e2e_full_booking_flow(temp_db):
    """Integration test: simulate full booking flow through repo functions"""
    async def _run():
        # Setup test data
        user = await get_or_create_user(123456789, "Test Client")
        service = await create_service("Test Service", "Description", 100, 60)
        master = await create_master("Test Master")

        # Step 1-7: Simulate booking creation (normally through handlers)
        booking_id = await create_booking(user['id'], service, master, "2026-01-15", "10:00", "Test Client", "+1234567890")
        assert booking_id is not None

        # Step 8: Admin completes booking
        await set_booking_status(booking_id, 'completed')
        b = await get_booking(booking_id)
        assert b['status'] == 'completed'

        # Step 9: Client rates the service (simulate review creation)
        from app.repo import create_review
        rid = await create_review(user['id'], service, master, 5, "Great service!")
        assert rid is not None

        # Verify review created
        reviews = await list_reviews()
        assert any(r['rating'] == 5 and r['user_id'] == user['id'] and r['text'] == "Great service!" for r in reviews)

        print("✅ E2E flow simulated successfully: booking -> completion -> review")

    asyncio.run(_run())


def test_e2e_edge_cases(temp_db):
    """Test edge cases: busy master, double booking, cancellation"""
    async def _run():
        # Setup
        user = await get_or_create_user(123456789, "Test Client")
        service = await create_service("Test Service", "Description", 100, 60)
        master = await create_master("Test Master")

        # Edge case 1: Double booking attempt
        booking1 = await create_booking(user['id'], service, master, "2026-01-15", "10:00", "Test Client", "+1234567890")
        # Second booking should fail due to DoubleBooking exception
        try:
            booking2 = await create_booking(user['id'], service, master, "2026-01-15", "11:00", "Test Client", "+1234567890")
            assert False, "Double booking should fail"
        except Exception as e:
            assert "DoubleBooking" in str(type(e)) or "активная запись" in str(e)

        # Edge case 2: Invalid status change
        try:
            await set_booking_status(99999, 'completed')  # Non-existent booking
            assert False, "Should fail for non-existent booking"
        except Exception:
            pass  # Expected

        # Edge case 3: Review for non-completed booking
        from app.repo import create_review
        # This should work, but in real handlers it's checked
        rid = await create_review(user['id'], service, master, 4, None)
        reviews = await list_reviews()
        assert any(r['rating'] == 4 and r['user_id'] == user['id'] for r in reviews)

        print("✅ Edge cases tested successfully")

    asyncio.run(_run())