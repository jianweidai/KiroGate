"""Checkpoint test: verify custom_api module imports work correctly."""

import os
import sys

os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_checkpoint_tests_only")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_checkpoint_tests")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_converter_import():
    from kiro_gateway.custom_api.converter import convert_claude_to_openai_request
    assert callable(convert_claude_to_openai_request)


def test_handler_import():
    from kiro_gateway.custom_api.handler import handle_custom_api_request
    assert callable(handle_custom_api_request)


def test_converter_additional_exports():
    from kiro_gateway.custom_api.converter import (
        convert_openai_stream_to_claude,
        convert_openai_error_to_claude,
        _clean_claude_request_for_azure,
        _estimate_input_tokens,
    )
    assert callable(convert_openai_stream_to_claude)
    assert callable(convert_openai_error_to_claude)
    assert callable(_clean_claude_request_for_azure)
    assert callable(_estimate_input_tokens)


def test_package_import():
    import kiro_gateway.custom_api
    assert kiro_gateway.custom_api is not None
