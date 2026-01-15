# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- tests: Add end-to-end test verifying UI shows "❌ занято" for fully booked masters (tests/test_busy_master_display.py). ✅
- tests: Add manual request flow tests and stabilize booking-related tests (tests/test_booking_manual_request.py).
- feature: Add auto-review request after booking completion — admin command `/complete_booking` marks booking as completed and sends client a rating prompt (1-5 stars + optional comment). Reviews are saved to DB and admins are notified. Includes unit and E2E tests (tests/test_handlers_reviews_auto_request.py).
- ux: Improve user experience with friendlier messages, emojis, examples, and clearer prompts across booking, review, and admin flows. Enhanced error messages and confirmations.

### Fixed
- handlers: Ensure `InlineKeyboardMarkup` and `InlineKeyboardButton` are constructed compatibly with current test harness and aiogram usage (various small fixes in `app/handlers/booking.py`, `app/handlers/client.py`, `app/handlers/services.py`).

### Notes
- All tests pass locally: **33 passed, 1 warning**.
- Migration to aiogram 3.x and removal of temporary test shims postponed — will be scheduled as a separate task when a migration plan is approved.

---

(Generated on 2026-01-14)
