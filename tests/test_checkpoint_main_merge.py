"""Checkpoint test: verify all main branch merged modules import and work correctly."""

import os
import sys

os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_checkpoint_tests_only")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_checkpoint_tests")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_thinking_parser_module():
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType, TextSegment
    assert KiroThinkingTagParser is not None
    assert SegmentType is not None
    assert TextSegment is not None


def test_converters_thinking_functions():
    from kiro_gateway.converters import is_thinking_enabled, get_thinking_budget, inject_thinking_hint
    assert callable(is_thinking_enabled)
    assert callable(get_thinking_budget)
    assert callable(inject_thinking_hint)


def test_streaming_module():
    from kiro_gateway.streaming import (
        stream_kiro_to_openai,
        stream_kiro_to_openai_internal,
        stream_with_first_token_retry,
        collect_stream_response,
    )
    assert callable(stream_kiro_to_openai)
    assert callable(stream_kiro_to_openai_internal)
    assert callable(stream_with_first_token_retry)
    assert callable(collect_stream_response)


def test_websearch_module():
    from kiro_gateway.websearch import has_web_search_tool, extract_search_query
    assert callable(has_web_search_tool)
    assert callable(extract_search_query)


def test_models_anthropic_tool():
    from kiro_gateway.models import AnthropicTool, ChatCompletionRequest
    assert AnthropicTool is not None
    assert ChatCompletionRequest is not None


def test_auth_cache_module():
    from kiro_gateway.auth_cache import AuthManagerCache, auth_cache
    assert AuthManagerCache is not None
    assert auth_cache is not None


def test_http_client_module():
    from kiro_gateway.http_client import GlobalHTTPClientManager, KiroHttpClient
    assert GlobalHTTPClientManager is not None
    assert KiroHttpClient is not None


def test_user_manager_module():
    from kiro_gateway.user_manager import UserManager
    assert UserManager is not None


def test_config_module():
    from kiro_gateway.config import Settings, settings
    assert Settings is not None
    assert settings is not None


def test_request_handler_module():
    from kiro_gateway.request_handler import RequestHandler
    assert RequestHandler is not None


def test_routes_module():
    from kiro_gateway.routes import router
    assert router is not None
