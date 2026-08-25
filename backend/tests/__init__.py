import os

# Settings reads backend/.env, so a developer's local DEV_OTP_CODE would bypass
# Twilio and fail the Verify tests. Env vars outrank .env, so pin them here —
# this package is imported before any test module touches app code.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-the-settlo-test-suite")
os.environ["DEV_OTP_CODE"] = ""
