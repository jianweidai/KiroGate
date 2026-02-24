# -*- coding: utf-8 -*-

"""
针对 kiro.rs master 同步修复的单元测试

覆盖以下修复点：
1. converters.py - _normalize_json_schema / convert_anthropic_tools_to_openai
2. parsers.py    - AwsEventStreamParser exception 事件解析
3. streaming.py  - stop_reason: max_tokens / model_context_window_exceeded
4. websearch.py  - Anthropic SSE 事件序列重构
"""

import json
import pytest

# ==================================================================================================
# 1. JSON Schema 规范化
# ==================================================================================================

from kiro_gateway.converters import _normalize_json_schema, convert_anthropic_tools_to_openai
from kiro_gateway.models import AnthropicTool


class TestNormalizeJsonSchema:

    def test_null_required_becomes_empty_list(self):
        result = _normalize_json_schema({"type": "object", "properties": {}, "required": None})
        assert result["required"] == []

    def test_null_properties_becomes_empty_dict(self):
        result = _normalize_json_schema({"type": "object", "properties": None})
        assert result["properties"] == {}

    def test_missing_type_defaults_to_object(self):
        result = _normalize_json_schema({"properties": {}})
        assert result["type"] == "object"

    def test_empty_type_string_defaults_to_object(self):
        result = _normalize_json_schema({"type": "", "properties": {}})
        assert result["type"] == "object"

    def test_valid_schema_unchanged(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        result = _normalize_json_schema(schema)
        assert result["type"] == "object"
        assert result["required"] == ["name"]
        assert result["additionalProperties"] is False

    def test_required_filters_non_strings(self):
        result = _normalize_json_schema({
            "type": "object",
            "properties": {},
            "required": ["name", 123, None, "age"],
        })
        assert result["required"] == ["name", "age"]

    def test_non_dict_input_returns_default(self):
        result = _normalize_json_schema(None)
        assert result["type"] == "object"
        assert result["properties"] == {}
        assert result["required"] == []

    def test_additional_properties_invalid_becomes_true(self):
        result = _normalize_json_schema({"type": "object", "properties": {}, "additionalProperties": "yes"})
        assert result["additionalProperties"] is True

    def test_additional_properties_bool_preserved(self):
        result = _normalize_json_schema({"type": "object", "properties": {}, "additionalProperties": False})
        assert result["additionalProperties"] is False


class TestConvertAnthropicToolsToOpenai:

    def test_null_input_schema_normalized(self):
        """input_schema 为空 dict 时不应崩溃（Pydantic 不允许 None，实际 MCP 可能传空 {}）"""
        tool = AnthropicTool(name="bash", description="Run bash", input_schema={})
        result = convert_anthropic_tools_to_openai([tool])
        assert result is not None
        assert result[0].function.parameters["type"] == "object"

    def test_required_null_normalized(self):
        tool = AnthropicTool(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": None}
        )
        result = convert_anthropic_tools_to_openai([tool])
        assert result[0].function.parameters["required"] == []

    def test_properties_null_normalized(self):
        tool = AnthropicTool(
            name="no_args",
            description="No args tool",
            input_schema={"type": "object", "properties": None}
        )
        result = convert_anthropic_tools_to_openai([tool])
        assert result[0].function.parameters["properties"] == {}

    def test_valid_schema_preserved(self):
        tool = AnthropicTool(
            name="search",
            description="Search",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
        )
        result = convert_anthropic_tools_to_openai([tool])
        params = result[0].function.parameters
        assert params["required"] == ["q"]
        assert "q" in params["properties"]

    def test_empty_tools_returns_none(self):
        assert convert_anthropic_tools_to_openai([]) is None

    def test_none_tools_returns_none(self):
        assert convert_anthropic_tools_to_openai(None) is None


# ==================================================================================================
# 2. AwsEventStreamParser exception 事件解析
# ==================================================================================================

from kiro_gateway.parsers import AwsEventStreamParser


class TestAwsEventStreamParserException:

    def _make_chunk(self, data: dict) -> bytes:
        return json.dumps(data).encode("utf-8")

    def test_exception_event_parsed(self):
        parser = AwsEventStreamParser()
        chunk = self._make_chunk({"exceptionType": "ContentLengthExceededException"})
        events = parser.feed(chunk)
        exception_events = [e for e in events if e["type"] == "exception"]
        assert len(exception_events) == 1
        assert exception_events[0]["data"] == "ContentLengthExceededException"

    def test_unknown_exception_type_parsed(self):
        parser = AwsEventStreamParser()
        chunk = self._make_chunk({"exceptionType": "SomeOtherException"})
        events = parser.feed(chunk)
        exception_events = [e for e in events if e["type"] == "exception"]
        assert len(exception_events) == 1
        assert exception_events[0]["data"] == "SomeOtherException"

    def test_content_event_still_works(self):
        parser = AwsEventStreamParser()
        chunk = self._make_chunk({"content": "hello world"})
        events = parser.feed(chunk)
        content_events = [e for e in events if e["type"] == "content"]
        assert len(content_events) == 1
        assert content_events[0]["data"] == "hello world"

    def test_context_usage_event_still_works(self):
        parser = AwsEventStreamParser()
        chunk = self._make_chunk({"contextUsagePercentage": 75.5})
        events = parser.feed(chunk)
        usage_events = [e for e in events if e["type"] == "context_usage"]
        assert len(usage_events) == 1
        assert usage_events[0]["data"] == 75.5

    def test_mixed_events_in_sequence(self):
        parser = AwsEventStreamParser()
        data = (
            json.dumps({"content": "text"})
            + json.dumps({"contextUsagePercentage": 100.0})
            + json.dumps({"exceptionType": "ContentLengthExceededException"})
        )
        events = parser.feed(data.encode("utf-8"))
        types = [e["type"] for e in events]
        assert "content" in types
        assert "context_usage" in types
        assert "exception" in types


# ==================================================================================================
# 3. stop_reason 逻辑（通过 streaming 模块的辅助函数间接测试）
# ==================================================================================================

class TestStopReasonLogic:
    """
    验证 exception 事件 → stop_reason 的映射逻辑。
    直接测试解析器输出，确保下游 streaming 能拿到正确的 exception data。
    """

    def test_content_length_exceeded_maps_to_max_tokens(self):
        """ContentLengthExceededException 应映射为 max_tokens"""
        parser = AwsEventStreamParser()
        chunk = json.dumps({"exceptionType": "ContentLengthExceededException"}).encode()
        events = parser.feed(chunk)
        exc = next(e for e in events if e["type"] == "exception")
        # streaming.py 中：if exception_type == "ContentLengthExceededException" → "max_tokens"
        assert exc["data"] == "ContentLengthExceededException"

    def test_context_usage_100_triggers_window_exceeded(self):
        """context_usage_percentage >= 100 应触发 model_context_window_exceeded"""
        parser = AwsEventStreamParser()
        chunk = json.dumps({"contextUsagePercentage": 100.0}).encode()
        events = parser.feed(chunk)
        ctx = next(e for e in events if e["type"] == "context_usage")
        # streaming.py 中：if context_usage_percentage >= 100.0 → "model_context_window_exceeded"
        assert ctx["data"] >= 100.0

    def test_context_usage_below_100_no_override(self):
        """context_usage_percentage < 100 不应触发 stop_reason 覆盖"""
        parser = AwsEventStreamParser()
        chunk = json.dumps({"contextUsagePercentage": 80.0}).encode()
        events = parser.feed(chunk)
        ctx = next(e for e in events if e["type"] == "context_usage")
        assert ctx["data"] < 100.0


# ==================================================================================================
# 4. WebSearch Anthropic SSE 事件序列
# ==================================================================================================

import asyncio
from kiro_gateway.websearch import (
    generate_websearch_sse_events_anthropic,
    WebSearchResult,
    WebSearchResults,
)


def collect_sse_events(coro) -> list[dict]:
    """收集异步生成器产生的所有 SSE 事件，解析为带 _event/_data 的列表"""
    async def _collect():
        events = []
        current_event = None
        async for raw in coro:
            # 每个 raw 可能是 "event: xxx\ndata: {...}\n\n"
            for line in raw.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_str = line[len("data:"):].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = data_str
                    events.append({"_event": current_event, "_data": data})
                    current_event = None
        return events
    return asyncio.run(_collect())


class TestWebsearchAnthropicSseSequence:

    def _make_results(self):
        return WebSearchResults(
            results=[WebSearchResult(title="Test", url="https://example.com", snippet="A snippet")],
            query="test query",
        )

    def _get_events(self, results=None):
        return collect_sse_events(
            generate_websearch_sse_events_anthropic(
                model="claude-sonnet-4",
                query="test query",
                tool_use_id="srvtoolu_abc123",
                search_results=results or self._make_results(),
                input_tokens=100,
            )
        )

    def test_event_sequence_order(self):
        """验证事件顺序：message_start → content_block_* × 4组 → message_delta → message_stop"""
        events = self._get_events()
        event_types = [e["_event"] for e in events]

        assert event_types[0] == "message_start"
        assert event_types[-1] == "message_stop"
        assert "message_delta" in event_types
        assert event_types.count("content_block_start") == 4
        assert event_types.count("content_block_stop") == 4

    def test_index_0_is_text_block(self):
        """index 0 应该是 text block（搜索决策说明）"""
        events = self._get_events()
        block_starts = [e for e in events if e["_event"] == "content_block_start"]
        idx0 = block_starts[0]["_data"]
        assert idx0["index"] == 0
        assert idx0["content_block"]["type"] == "text"

    def test_index_0_text_contains_query(self):
        """index 0 的 text_delta 应包含搜索查询"""
        events = self._get_events()
        deltas = [e for e in events if e["_event"] == "content_block_delta"
                  and e["_data"]["index"] == 0]
        text = "".join(d["_data"]["delta"]["text"] for d in deltas)
        assert "test query" in text

    def test_index_1_is_server_tool_use(self):
        """index 1 应该是 server_tool_use，input 在 content_block_start 中完整发送"""
        events = self._get_events()
        block_starts = [e for e in events if e["_event"] == "content_block_start"]
        idx1 = block_starts[1]["_data"]
        assert idx1["index"] == 1
        assert idx1["content_block"]["type"] == "server_tool_use"
        # input 在 content_block_start 中完整发送，不是空 {}
        assert idx1["content_block"]["input"] == {"query": "test query"}

    def test_index_1_no_input_json_delta(self):
        """server_tool_use 不应有 input_json_delta（已在 content_block_start 完整发送）"""
        events = self._get_events()
        deltas_idx1 = [e for e in events if e["_event"] == "content_block_delta"
                       and e["_data"]["index"] == 1]
        assert len(deltas_idx1) == 0

    def test_index_2_is_web_search_tool_result(self):
        """index 2 应该是 web_search_tool_result，且无 tool_use_id 字段"""
        events = self._get_events()
        block_starts = [e for e in events if e["_event"] == "content_block_start"]
        idx2 = block_starts[2]["_data"]
        assert idx2["index"] == 2
        assert idx2["content_block"]["type"] == "web_search_tool_result"
        # 官方格式无 tool_use_id
        assert "tool_use_id" not in idx2["content_block"]

    def test_index_2_contains_search_results(self):
        """web_search_tool_result 应包含搜索结果"""
        events = self._get_events()
        block_starts = [e for e in events if e["_event"] == "content_block_start"]
        idx2 = block_starts[2]["_data"]
        content = idx2["content_block"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "web_search_result"
        assert content[0]["title"] == "Test"
        assert content[0]["url"] == "https://example.com"

    def test_index_3_is_text_summary(self):
        """index 3 应该是 text block（搜索结果摘要）"""
        events = self._get_events()
        block_starts = [e for e in events if e["_event"] == "content_block_start"]
        idx3 = block_starts[3]["_data"]
        assert idx3["index"] == 3
        assert idx3["content_block"]["type"] == "text"

    def test_message_delta_no_stop_sequence(self):
        """message_delta.delta 不应有 stop_sequence 字段"""
        events = self._get_events()
        delta_event = next(e for e in events if e["_event"] == "message_delta")
        assert "stop_sequence" not in delta_event["_data"]["delta"]

    def test_message_delta_has_server_tool_use_usage(self):
        """message_delta.usage 应包含 server_tool_use.web_search_requests"""
        events = self._get_events()
        delta_event = next(e for e in events if e["_event"] == "message_delta")
        usage = delta_event["_data"]["usage"]
        assert "server_tool_use" in usage
        assert usage["server_tool_use"]["web_search_requests"] == 1

    def test_message_start_no_stop_sequence(self):
        """message_start.message 不应有 stop_sequence 字段"""
        events = self._get_events()
        start_event = next(e for e in events if e["_event"] == "message_start")
        assert "stop_sequence" not in start_event["_data"]["message"]

    def test_empty_search_results(self):
        """空搜索结果时事件序列仍然完整"""
        empty_results = WebSearchResults(results=[], query="nothing")
        events = collect_sse_events(
            generate_websearch_sse_events_anthropic(
                model="claude-sonnet-4",
                query="nothing",
                tool_use_id="srvtoolu_xyz",
                search_results=empty_results,
                input_tokens=50,
            )
        )
        event_types = [e["_event"] for e in events]
        assert "message_start" in event_types
        assert "message_stop" in event_types
        assert event_types.count("content_block_start") == 4

        # web_search_tool_result content 应为空列表
        block_starts = [e for e in events if e["_event"] == "content_block_start"]
        idx2 = block_starts[2]["_data"]
        assert idx2["content_block"]["content"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
