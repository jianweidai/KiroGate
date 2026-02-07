"""Final checkpoint verification - Task 10: 合并完成确认"""

import os
import sys

# Set required env vars before any kiro_gateway imports to bypass security validation
os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_final_checkpoint")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_final_checkpoint")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_core_module_imports():
    """Verify all core modules can be imported successfully."""
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType, TextSegment
    from kiro_gateway.converters import is_thinking_enabled, get_thinking_budget, inject_thinking_hint
    from kiro_gateway.streaming import stream_kiro_to_openai_internal, collect_stream_response
    from kiro_gateway.websearch import has_web_search_tool, extract_search_query
    from kiro_gateway.models import AnthropicTool, AnthropicMessagesRequest
    from kiro_gateway.request_handler import RequestHandler
    from kiro_gateway.config import APP_VERSION, settings
    from kiro_gateway.auth_cache import AuthManagerCache
    from kiro_gateway.http_client import KiroHttpClient
    from kiro_gateway.user_manager import UserManager
    from kiro_gateway.routes import router


def test_anthropic_tool_optional_input_schema():
    """Req 7.1, 7.3: AnthropicTool accepts missing input_schema."""
    from kiro_gateway.models import AnthropicTool
    tool = AnthropicTool(name="test_tool")
    assert tool.input_schema is None
    assert tool.name == "test_tool"


def test_thinking_parser_basic():
    """Req 1.3: Parser produces THINKING + TEXT segments."""
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType
    parser = KiroThinkingTagParser()
    segments = parser.push_and_parse("<thinking>hello</thinking>world")
    segments += parser.flush()
    has_thinking = any(s.type == SegmentType.THINKING for s in segments)
    has_text = any(s.type == SegmentType.TEXT for s in segments)
    assert has_thinking
    assert has_text


def test_thinking_parser_passthrough():
    """Req 1.3: Non-thinking input goes to TEXT mode."""
    from kiro_gateway.thinking_parser import KiroThinkingTagParser, SegmentType
    parser = KiroThinkingTagParser()
    segments = parser.push_and_parse("just plain text")
    segments += parser.flush()
    assert all(s.type == SegmentType.TEXT for s in segments)


def test_thinking_budget_default():
    """Req 2.3: Default budget is 200000."""
    from kiro_gateway.converters import get_thinking_budget
    assert get_thinking_budget(None) == 200000


def test_thinking_budget_custom():
    """Req 2.2: Budget reads from config."""
    from kiro_gateway.converters import get_thinking_budget
    assert get_thinking_budget({"budget_tokens": 1024}) == 1024


def test_version_is_2_3_0():
    """Req 8.10: Version should be 2.3.0."""
    from kiro_gateway.config import APP_VERSION
    assert APP_VERSION == "2.3.0"
