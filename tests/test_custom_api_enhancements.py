# -*- coding: utf-8 -*-
"""
Tests for custom-api-enhancements spec.

Covers:
- update_custom_api_account() database method
- _account_matches_model() helper
- Property-based tests (hypothesis)
"""

import os
import sys

os.environ.setdefault("USER_SESSION_SECRET", "test_secret")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_db(tmp_path, name="test.db"):
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
    user = db.create_user(username, linuxdo_id=f"linuxdo_{username}")
    return user.id


def _add_account(db, user_id, model=None):
    return db.add_custom_api_account(
        user_id=user_id,
        name="test",
        api_base="https://api.example.com",
        api_key="sk-testkey",
        format="openai",
        provider=None,
        model=model,
    )


# ── unit tests ────────────────────────────────────────────────────────────────

def test_update_custom_api_account_success(tmp_path):
    db = _make_db(tmp_path)
    uid = _create_user(db, "alice")
    acc_id = _add_account(db, uid)

    result = db.update_custom_api_account(
        account_id=acc_id,
        user_id=uid,
        name="updated name",
        api_base="https://new.example.com",
    )
    assert result is True

    accounts = db.get_custom_api_accounts_by_user(uid)
    acc = next(a for a in accounts if a["id"] == acc_id)
    assert acc["name"] == "updated name"
    assert acc["api_base"] == "https://new.example.com"


def test_update_custom_api_account_empty_api_key(tmp_path):
    """api_key='' should keep the original encrypted key."""
    db = _make_db(tmp_path)
    uid = _create_user(db, "bob")
    acc_id = _add_account(db, uid)

    # Get original masked key
    original_accounts = db.get_custom_api_accounts_by_user(uid)
    original_masked = next(a for a in original_accounts if a["id"] == acc_id)["api_key_masked"]

    # Update with empty api_key — should not change the key
    result = db.update_custom_api_account(
        account_id=acc_id,
        user_id=uid,
        name="new name",
        api_key="",
    )
    assert result is True

    updated_accounts = db.get_custom_api_accounts_by_user(uid)
    updated = next(a for a in updated_accounts if a["id"] == acc_id)
    assert updated["api_key_masked"] == original_masked


def test_update_returns_false_for_wrong_user(tmp_path):
    db = _make_db(tmp_path)
    uid1 = _create_user(db, "carol")
    uid2 = _create_user(db, "dave")
    acc_id = _add_account(db, uid1)

    result = db.update_custom_api_account(
        account_id=acc_id,
        user_id=uid2,
        name="hacked",
    )
    assert result is False

    # Original record unchanged
    accounts = db.get_custom_api_accounts_by_user(uid1)
    acc = next(a for a in accounts if a["id"] == acc_id)
    assert acc["name"] == "test"


def test_model_empty_string_matches_nothing():
    from kiro_gateway.token_allocator import _account_matches_model
    account = {"model": ""}
    assert _account_matches_model(account, "claude-sonnet-4-6") is False
    assert _account_matches_model(account, "") is False


def test_model_null_matches_nothing():
    from kiro_gateway.token_allocator import _account_matches_model
    account = {"model": None}
    assert _account_matches_model(account, "claude-opus-4-6") is False


def test_model_multi_matches_correctly():
    from kiro_gateway.token_allocator import _account_matches_model
    account = {"model": "claude-sonnet-4-6, claude-opus-4-6"}
    assert _account_matches_model(account, "claude-sonnet-4-6") is True
    assert _account_matches_model(account, "claude-opus-4-6") is True
    assert _account_matches_model(account, "claude-haiku-4-5") is False


def test_pro_plus_empty_model_excluded():
    from kiro_gateway.token_allocator import _account_matches_model
    for model_val in ("", None, "   "):
        account = {"model": model_val}
        assert _account_matches_model(account, "claude-sonnet-4-6") is False, \
            f"Expected False for model={model_val!r}"


# ── property-based tests ──────────────────────────────────────────────────────

# Strategies
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_."),
    min_size=1, max_size=30,
)
_username = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=3, max_size=20,
)
_model_name = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_."),
    min_size=1, max_size=40,
)


@given(
    username_a=_username,
    username_b=_username,
    new_name=_safe_text,
)
@settings(max_examples=50)
def test_update_user_isolation(username_a, username_b, new_name):
    """
    Feature: custom-api-enhancements, Property 1: update 用户隔离
    Validates: Requirements 1.1, 1.3
    """
    import tempfile, pathlib
    assume(username_a != username_b)

    with tempfile.TemporaryDirectory() as td:
        db = _make_db(pathlib.Path(td), name="iso.db")
        uid_a = _create_user(db, username_a)
        uid_b = _create_user(db, username_b)
        acc_id = _add_account(db, uid_a)

        # User B cannot update user A's account
        result = db.update_custom_api_account(
            account_id=acc_id,
            user_id=uid_b,
            name=new_name,
        )
        assert result is False

        # Record unchanged
        accounts = db.get_custom_api_accounts_by_user(uid_a)
        acc = next(a for a in accounts if a["id"] == acc_id)
        assert acc["name"] == "test"

        # User A can update their own account
        result_a = db.update_custom_api_account(
            account_id=acc_id,
            user_id=uid_a,
            name=new_name,
        )
        assert result_a is True


@given(
    username=_username,
    new_name=st.one_of(st.none(), _safe_text),
    new_api_base=st.just("https://updated.example.com"),
    new_model=st.one_of(st.none(), _model_name),
)
@settings(max_examples=50)
def test_update_round_trip(username, new_name, new_api_base, new_model):
    """
    Feature: custom-api-enhancements, Property 2: update round-trip
    Validates: Requirements 1.2
    """
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        db = _make_db(pathlib.Path(td), name="rt.db")
        uid = _create_user(db, username)
        acc_id = _add_account(db, uid)

        result = db.update_custom_api_account(
            account_id=acc_id,
            user_id=uid,
            name=new_name,
            api_base=new_api_base,
            model=new_model,
        )
        assert result is True

        accounts = db.get_custom_api_accounts_by_user(uid)
        acc = next(a for a in accounts if a["id"] == acc_id)

        if new_name is not None:
            assert acc["name"] == new_name
        if new_api_base is not None:
            assert acc["api_base"] == new_api_base
        if new_model is not None:
            assert acc["model"] == new_model


@given(
    model_names=st.lists(_model_name, min_size=1, max_size=5),
    spaces=st.lists(st.text(" ", min_size=0, max_size=3), min_size=1, max_size=6),
)
@settings(max_examples=100)
def test_model_field_parsing(model_names, spaces):
    """
    Feature: custom-api-enhancements, Property 5: 模型字段解析与匹配
    Validates: Requirements 2.1, 2.2, 3.4, 3.5
    """
    from kiro_gateway.token_allocator import _account_matches_model

    # Build comma-separated string with random surrounding spaces
    parts = []
    for i, name in enumerate(model_names):
        sp = spaces[i % len(spaces)]
        parts.append(sp + name + sp)
    model_field = ",".join(parts)

    account = {"model": model_field}

    # Every model in the list should match
    for name in model_names:
        assert _account_matches_model(account, name) is True, \
            f"Expected {name!r} to match in {model_field!r}"

    # A name not in the list should not match (unless it happens to be a substring)
    sentinel = "ZZZNOMATCH_SENTINEL_ZZZ"
    assert _account_matches_model(account, sentinel) is False


@given(
    username=_username,
    model_string=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-, "),
        min_size=1, max_size=80,
    ),
)
@settings(max_examples=50)
def test_multi_model_storage_roundtrip(username, model_string):
    """
    Feature: custom-api-enhancements, Property 6: 多模型字符串原样存储
    Validates: Requirements 2.4
    """
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        db = _make_db(pathlib.Path(td), name="ms.db")
        uid = _create_user(db, username)

        # Store via add
        acc_id = db.add_custom_api_account(
            user_id=uid,
            name=None,
            api_base="https://api.example.com",
            api_key="sk-key",
            format="openai",
            provider=None,
            model=model_string,
        )
        accounts = db.get_custom_api_accounts_by_user(uid)
        acc = next(a for a in accounts if a["id"] == acc_id)
        assert acc["model"] == model_string

        # Store via update
        acc_id2 = _add_account(db, uid)
        db.update_custom_api_account(
            account_id=acc_id2,
            user_id=uid,
            model=model_string,
        )
        accounts2 = db.get_custom_api_accounts_by_user(uid)
        acc2 = next(a for a in accounts2 if a["id"] == acc_id2)
        assert acc2["model"] == model_string
