"""Checkpoint test: verify all Thinking Mode integration imports work correctly."""

import os
import sys

# Set required env vars before any kiro_gateway imports to bypass security validation
os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_checkpoint_tests_only")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_checkpoint_tests")

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_thinking_parser_imports():
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType, TextSegment
    assert KiroThinkingTagParser is not None
    assert SegmentType is not None
    assert TextSegment is not None


def test_converters_thinking_functions():
    from kiro_gateway.converters import is_thinking_enabled, get_thinking_budget, inject_thinking_hint
    assert callable(is_thinking_enabled)
    assert callable(get_thinking_budget)
    assert callable(inject_thinking_hint)


def test_streaming_imports():
    from kiro_gateway.streaming import (
        stream_kiro_to_openai,
        stream_kiro_to_openai_internal,
        stream_with_first_token_retry,
        collect_stream_response,
    )
    assert callable(stream_kiro_to_openai)
    assert callable(collect_stream_response)


def test_thinking_parser_basic_functionality():
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType

    parser = KiroThinkingTagParser()
    segments = parser.push_and_parse("<thinking>hello world</thinking>\nresult")

    thinking_segments = [s for s in segments if s.type == SegmentType.THINKING]
    assert len(thinking_segments) > 0, "Should have at least one THINKING segment"
    assert parser.is_thinking_mode


def test_thinking_parser_passthrough():
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType

    parser = KiroThinkingTagParser()
    segments = parser.push_and_parse("just normal text without thinking")

    assert all(s.type == SegmentType.TEXT for s in segments)
    assert not parser.is_thinking_mode


def test_is_thinking_enabled():
    from kiro_gateway.converters import is_thinking_enabled

    assert is_thinking_enabled({"type": "enabled", "budget_tokens": 1024}) is True
    assert is_thinking_enabled(None) is False
    assert is_thinking_enabled({"type": "disabled"}) is False


def test_get_thinking_budget():
    from kiro_gateway.converters import get_thinking_budget

    assert get_thinking_budget({"type": "enabled", "budget_tokens": 5000}) == 5000
    assert get_thinking_budget({"type": "enabled"}) == 200000
    assert get_thinking_budget(None) == 200000
