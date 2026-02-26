"""
Tests for the Kiro Portal account info feature.
Covers _get_kiro_account_info parsing logic and update_token_account_info DB method.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to build fake API responses
# ---------------------------------------------------------------------------

def _make_usage_response(
    subscription_title="Free",
    credit_limit=100.0,
    credit_current=30.0,
    next_reset="2026-03-01T00:00:00Z",
    email="test@example.com",
    free_trial=None,
    bonuses=None,
):
    credit_item = {
        "resourceType": "CREDIT",
        "usageLimitWithPrecision": credit_limit,
        "currentUsageWithPrecision": credit_current,
    }
    if free_trial:
        credit_item["freeTrialInfo"] = free_trial
    if bonuses:
        credit_item["bonuses"] = bonuses

    return {
        "subscriptionInfo": {"subscriptionTitle": subscription_title},
        "usageBreakdownList": [credit_item],
        "nextDateReset": next_reset,
        "userInfo": {"email": email},
    }


# ---------------------------------------------------------------------------
# Tests for _get_kiro_account_info
# ---------------------------------------------------------------------------

class TestGetKiroAccountInfo:
    """Test _get_kiro_account_info parsing logic via mocked portal requests."""

    @pytest.mark.asyncio
    async def test_free_subscription(self):
        from kiro_gateway.routes import _get_kiro_account_info

        usage_resp = _make_usage_response(subscription_title="Free", credit_limit=100.0, credit_current=25.0)
        user_info_resp = {"status": "Active"}

        call_count = {"n": 0}

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            call_count["n"] += 1
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            if operation == "GetUserInfo":
                return user_info_resp
            return {}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["subscription"]["type"] == "Free"
        assert result["usage"]["current"] == 25.0
        assert result["usage"]["limit"] == 100.0
        assert result["usage"]["percent"] == 25.0
        assert result["email"] == "test@example.com"
        assert result["status"] == "Active"

    @pytest.mark.asyncio
    async def test_pro_subscription(self):
        from kiro_gateway.routes import _get_kiro_account_info

        usage_resp = _make_usage_response(subscription_title="Pro", credit_limit=500.0, credit_current=100.0)

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["subscription"]["type"] == "Pro"

    @pytest.mark.asyncio
    async def test_pro_plus_subscription(self):
        from kiro_gateway.routes import _get_kiro_account_info

        usage_resp = _make_usage_response(subscription_title="Pro+", credit_limit=1000.0, credit_current=0.0)

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["subscription"]["type"] == "Pro+"

    @pytest.mark.asyncio
    async def test_free_trial_added_to_total(self):
        from kiro_gateway.routes import _get_kiro_account_info

        free_trial = {
            "freeTrialStatus": "ACTIVE",
            "usageLimitWithPrecision": 50.0,
            "currentUsageWithPrecision": 10.0,
        }
        usage_resp = _make_usage_response(
            credit_limit=100.0, credit_current=20.0, free_trial=free_trial
        )

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["usage"]["limit"] == 150.0   # 100 + 50
        assert result["usage"]["current"] == 30.0  # 20 + 10

    @pytest.mark.asyncio
    async def test_active_bonuses_added_to_total(self):
        from kiro_gateway.routes import _get_kiro_account_info

        bonuses = [
            {"status": "ACTIVE", "usageLimitWithPrecision": 20.0, "currentUsageWithPrecision": 5.0},
            {"status": "EXPIRED", "usageLimitWithPrecision": 10.0, "currentUsageWithPrecision": 10.0},
        ]
        usage_resp = _make_usage_response(
            credit_limit=100.0, credit_current=10.0, bonuses=bonuses
        )

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        # Only ACTIVE bonus counted
        assert result["usage"]["limit"] == 120.0   # 100 + 20
        assert result["usage"]["current"] == 15.0  # 10 + 5

    @pytest.mark.asyncio
    async def test_zero_limit_percent_is_zero(self):
        from kiro_gateway.routes import _get_kiro_account_info

        usage_resp = _make_usage_response(credit_limit=0.0, credit_current=0.0)

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["usage"]["percent"] == 0

    @pytest.mark.asyncio
    async def test_days_remaining_calculated(self):
        from kiro_gateway.routes import _get_kiro_account_info

        # Use a date far in the future
        future_date = "2099-01-01T00:00:00Z"
        usage_resp = _make_usage_response(next_reset=future_date)

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["usage"]["daysRemaining"] is not None
        assert result["usage"]["daysRemaining"] > 0

    @pytest.mark.asyncio
    async def test_idp_fallback_on_401(self):
        """Should try next idp when 401 is returned."""
        from kiro_gateway.routes import _get_kiro_account_info
        from fastapi import HTTPException

        usage_resp = _make_usage_response()
        tried_idps = []

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                tried_idps.append(idp)
                if idp == "Github":
                    raise HTTPException(status_code=401, detail="Unauthorized")
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert "Github" in tried_idps
        assert "Google" in tried_idps
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_all_idps_fail_raises(self):
        """Should raise when all idps return 401."""
        from kiro_gateway.routes import _get_kiro_account_info
        from fastapi import HTTPException

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                raise HTTPException(status_code=401, detail="Unauthorized")
            return {}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            with pytest.raises(HTTPException) as exc_info:
                await _get_kiro_account_info("fake-token")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_suspended_status_from_user_info(self):
        from kiro_gateway.routes import _get_kiro_account_info

        usage_resp = _make_usage_response()

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            if operation == "GetUserInfo":
                return {"status": "Suspended"}
            return {}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        assert result["status"] == "Suspended"

    @pytest.mark.asyncio
    async def test_last_updated_is_recent_timestamp(self):
        from kiro_gateway.routes import _get_kiro_account_info

        usage_resp = _make_usage_response()
        before = int(time.time() * 1000)

        async def fake_portal(operation, body, access_token, idp="BuilderId"):
            if operation == "GetUserUsageAndLimits":
                return usage_resp
            return {"status": "Active"}

        with patch("kiro_gateway.routes._kiro_portal_request", side_effect=fake_portal):
            result = await _get_kiro_account_info("fake-token")

        after = int(time.time() * 1000)
        assert before <= result["lastUpdated"] <= after


# ---------------------------------------------------------------------------
# Tests for database update_token_account_info
# ---------------------------------------------------------------------------

class TestUpdateTokenAccountInfo:
    """Test that update_token_account_info correctly writes to DB."""

    def _make_db(self, tmp_path):
        """Create a real UserDatabase instance pointing at a temp file."""
        from kiro_gateway.database import UserDatabase
        db = UserDatabase.__new__(UserDatabase)
        import threading
        db._lock = threading.Lock()
        db._db_path = str(tmp_path / "test.db")
        db._init_db()
        return db

    def _insert_token(self, db, token_id=1):
        """Insert a minimal token row for testing."""
        import sqlite3, time as t
        with sqlite3.connect(db._db_path) as conn:
            conn.execute(
                "INSERT INTO tokens (id, user_id, refresh_token_encrypted, token_hash, created_at) "
                "VALUES (?, 1, 'enc', ?, ?)",
                (token_id, f"hash{token_id}", int(t.time() * 1000))
            )

    def test_update_stores_values(self, tmp_path):
        import sqlite3
        db = self._make_db(tmp_path)
        self._insert_token(db, token_id=1)

        result = db.update_token_account_info(
            token_id=1,
            email="user@example.com",
            subscription="Pro",
            usage_current=42.5,
            usage_limit=100.0,
        )
        assert result is True

        with sqlite3.connect(db._db_path) as conn:
            row = conn.execute(
                "SELECT account_email, account_subscription, account_usage_current, account_usage_limit "
                "FROM tokens WHERE id=1"
            ).fetchone()

        assert row[0] == "user@example.com"
        assert row[1] == "Pro"
        assert row[2] == 42.5
        assert row[3] == 100.0

    def test_update_nonexistent_token_returns_false(self, tmp_path):
        db = self._make_db(tmp_path)
        # No token inserted — id 999 doesn't exist
        result = db.update_token_account_info(
            token_id=999,
            email="x@x.com",
            subscription="Free",
            usage_current=0.0,
            usage_limit=100.0,
        )
        assert result is False

    def test_update_checked_at_is_set(self, tmp_path):
        import sqlite3, time as t
        db = self._make_db(tmp_path)
        self._insert_token(db, token_id=2)

        before = int(t.time() * 1000)
        db.update_token_account_info(
            token_id=2,
            email=None,
            subscription="Free",
            usage_current=0.0,
            usage_limit=0.0,
        )
        after = int(t.time() * 1000)

        with sqlite3.connect(db._db_path) as conn:
            row = conn.execute("SELECT account_checked_at FROM tokens WHERE id=2").fetchone()

        assert row[0] is not None
        assert before <= row[0] <= after
