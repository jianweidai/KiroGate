"""
Final Checkpoint: Custom API Support
- 验证路由逻辑：kiro token 和 custom_api 账号都参与随机选择
- 验证 api_key 加密存储
- 验证列表接口返回脱敏数据
"""

import os
import sys
import sqlite3

os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_custom_api_final")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_custom_api_final")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def _make_db(tmp_path, name="test.db"):
    """Instantiate a UserDatabase backed by a temp file."""
    import kiro_gateway.database as db_module
    db_path = str(tmp_path / name)
    original = db_module.USER_DB_FILE
    db_module.USER_DB_FILE = db_path
    try:
        db = db_module.UserDatabase()
    finally:
        db_module.USER_DB_FILE = original
    db._db_path = db_path
    return db


def _create_user(db, username):
    """Create a test user and return its integer id."""
    user = db.create_user(username, linuxdo_id=f"linuxdo_{username}")
    return user.id


# ---------------------------------------------------------------------------
# 1. api_key 加密存储
# ---------------------------------------------------------------------------

def test_api_key_is_encrypted_in_db(tmp_path):
    """api_key 在数据库中必须以加密形式存储，不能明文出现。"""
    db = _make_db(tmp_path, "enc_test.db")
    user_id = _create_user(db, "enc_user")

    plain_key = "sk-supersecretkey12345"
    db.add_custom_api_account(
        user_id=user_id,
        name="test",
        api_base="https://api.example.com",
        api_key=plain_key,
        format="openai",
        provider=None,
        model=None,
    )

    conn = sqlite3.connect(db._db_path)
    row = conn.execute("SELECT api_key_encrypted FROM custom_api_accounts LIMIT 1").fetchone()
    conn.close()

    assert row is not None
    raw_stored = row[0]
    assert raw_stored != plain_key, "api_key must not be stored in plaintext"
    assert len(raw_stored) > 0


def test_active_accounts_returns_decrypted_key(tmp_path):
    """get_active_custom_api_accounts_by_user 应返回解密后的 api_key。"""
    db = _make_db(tmp_path, "dec_test.db")
    user_id = _create_user(db, "dec_user")
    plain_key = "sk-decryptme9999"

    db.add_custom_api_account(
        user_id=user_id,
        name="dec_test",
        api_base="https://api.example.com",
        api_key=plain_key,
        format="openai",
        provider=None,
        model=None,
    )

    accounts = db.get_active_custom_api_accounts_by_user(user_id)
    assert len(accounts) == 1
    assert accounts[0]["api_key"] == plain_key


# ---------------------------------------------------------------------------
# 2. 列表接口返回脱敏数据
# ---------------------------------------------------------------------------

def test_list_returns_masked_api_key(tmp_path):
    """get_custom_api_accounts_by_user 返回的 api_key_masked 应脱敏（前4位 + ****）。"""
    db = _make_db(tmp_path, "mask_test.db")
    user_id = _create_user(db, "mask_user")
    plain_key = "sk-abcdefghij"

    db.add_custom_api_account(
        user_id=user_id,
        name="mask_test",
        api_base="https://api.example.com",
        api_key=plain_key,
        format="openai",
        provider=None,
        model=None,
    )

    accounts = db.get_custom_api_accounts_by_user(user_id)
    assert len(accounts) == 1
    masked = accounts[0]["api_key_masked"]

    assert masked != plain_key
    assert masked.startswith(plain_key[:4])
    assert masked.endswith("****")
    assert plain_key not in masked


def test_list_does_not_expose_plain_api_key(tmp_path):
    """列表接口返回的字段中不应包含 api_key（明文）字段。"""
    db = _make_db(tmp_path, "field_test.db")
    user_id = _create_user(db, "field_user")

    db.add_custom_api_account(
        user_id=user_id,
        name="field_test",
        api_base="https://api.example.com",
        api_key="sk-shouldnotappear",
        format="openai",
        provider=None,
        model=None,
    )

    accounts = db.get_custom_api_accounts_by_user(user_id)
    assert len(accounts) == 1
    assert "api_key" not in accounts[0]
    assert "api_key_masked" in accounts[0]


# ---------------------------------------------------------------------------
# 3. 路由逻辑：kiro token 和 custom_api 账号都参与随机选择
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_routing_selects_custom_api_when_only_custom_api(tmp_path):
    """当用户只有 custom_api 账号时，路由必须选择 custom_api。"""
    from kiro_gateway.token_allocator import SmartTokenAllocator
    import kiro_gateway.token_allocator as ta_module

    db = _make_db(tmp_path, "route1.db")
    user_id = _create_user(db, "route_user1")

    db.add_custom_api_account(
        user_id=user_id,
        name="only_custom",
        api_base="https://api.example.com",
        api_key="sk-routetest",
        format="openai",
        provider=None,
        model=None,
    )

    original_db = ta_module.user_db
    ta_module.user_db = db
    try:
        allocator = SmartTokenAllocator()
        account_type, account_data, manager = await allocator.get_best_token(user_id=user_id)
        assert account_type == "custom_api"
        assert manager is None
        assert account_data["api_key"] == "sk-routetest"
    finally:
        ta_module.user_db = original_db


@pytest.mark.asyncio
async def test_routing_raises_when_no_accounts(tmp_path):
    """当用户没有任何账号时，get_best_token 必须抛出 NoTokenAvailable。"""
    from kiro_gateway.token_allocator import SmartTokenAllocator, NoTokenAvailable
    import kiro_gateway.token_allocator as ta_module

    db = _make_db(tmp_path, "route2.db")
    user_id = _create_user(db, "route_user2")

    original_db = ta_module.user_db
    ta_module.user_db = db
    try:
        allocator = SmartTokenAllocator()
        with pytest.raises(NoTokenAvailable):
            await allocator.get_best_token(user_id=user_id)
    finally:
        ta_module.user_db = original_db


@pytest.mark.asyncio
async def test_routing_both_types_selected_over_many_calls(tmp_path):
    """
    当用户同时有 kiro token 和 custom_api 账号时，
    多次调用后两类账号都应被选中（概率 > 0）。
    """
    from kiro_gateway.token_allocator import SmartTokenAllocator
    import kiro_gateway.token_allocator as ta_module

    db = _make_db(tmp_path, "route3.db")
    user_id = _create_user(db, "route_user3")

    db.add_custom_api_account(
        user_id=user_id,
        name="custom1",
        api_base="https://api.example.com",
        api_key="sk-custom-route",
        format="openai",
        provider=None,
        model=None,
    )

    db.donate_token(
        user_id=user_id,
        refresh_token="fake-refresh-token-for-routing-test",
        visibility="private",
    )

    original_db = ta_module.user_db
    ta_module.user_db = db
    seen_types = set()
    try:
        allocator = SmartTokenAllocator()
        # With 50/50 chance, P(miss one type in 50 tries) < 2^-50
        for _ in range(50):
            try:
                account_type, _, _ = await allocator.get_best_token(user_id=user_id)
                seen_types.add(account_type)
            except Exception:
                pass
            if len(seen_types) == 2:
                break
    finally:
        ta_module.user_db = original_db

    assert "kiro" in seen_types, "kiro token was never selected in 50 attempts"
    assert "custom_api" in seen_types, "custom_api account was never selected in 50 attempts"


# ---------------------------------------------------------------------------
# 4. 用户隔离
# ---------------------------------------------------------------------------

def test_user_isolation_list(tmp_path):
    """用户 A 的账号不应出现在用户 B 的列表中。"""
    db = _make_db(tmp_path, "iso.db")
    user_a = _create_user(db, "user_a")
    user_b = _create_user(db, "user_b")

    db.add_custom_api_account(user_a, "a_account", "https://a.example.com", "sk-aaa", "openai", None, None)
    db.add_custom_api_account(user_b, "b_account", "https://b.example.com", "sk-bbb", "openai", None, None)

    a_accounts = db.get_custom_api_accounts_by_user(user_a)
    b_accounts = db.get_custom_api_accounts_by_user(user_b)

    assert len(a_accounts) == 1
    assert len(b_accounts) == 1
    assert a_accounts[0]["api_base"] == "https://a.example.com"
    assert b_accounts[0]["api_base"] == "https://b.example.com"


def test_user_isolation_delete(tmp_path):
    """用户 B 不能删除用户 A 的账号。"""
    db = _make_db(tmp_path, "iso_del.db")
    user_a = _create_user(db, "user_a2")
    user_b = _create_user(db, "user_b2")

    account_id = db.add_custom_api_account(user_a, "a_acct", "https://a.example.com", "sk-aaa", "openai", None, None)

    result = db.delete_custom_api_account(account_id, user_b)
    assert result is False

    a_accounts = db.get_custom_api_accounts_by_user(user_a)
    assert len(a_accounts) == 1
