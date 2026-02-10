# -*- coding: utf-8 -*-

"""
Web Search 功能测试

测试 Web Search 工具的检测、查询提取、MCP 请求构建和响应生成
"""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch

from kiro_gateway.websearch import (
    has_web_search_tool,
    extract_search_query,
    create_mcp_request,
    parse_search_results,
    generate_search_summary,
    WebSearchResult,
    WebSearchResults,
)
from kiro_gateway.models import (
    ChatCompletionRequest,
    AnthropicMessagesRequest,
    ChatMessage,
    AnthropicMessage,
    TextContent,
    Tool,
)


# ==================================================================================================
# Test has_web_search_tool
# ==================================================================================================

def test_has_web_search_tool_with_single_web_search():
    """测试：单个 web_search 工具应该返回 True"""
    tool = Tool(
        type="function",
        function={"name": "web_search", "description": "Search the web"}
    )
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[ChatMessage(role="user", content="test")],
        tools=[tool]
    )
    
    assert has_web_search_tool(request) is True


def test_has_web_search_tool_with_multiple_tools():
    """测试：多个工具应该返回 False"""
    tool1 = Tool(
        type="function",
        function={"name": "web_search", "description": "Search"}
    )
    tool2 = Tool(
        type="function",
        function={"name": "calculator", "description": "Calculate"}
    )
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[ChatMessage(role="user", content="test")],
        tools=[tool1, tool2]
    )
    
    assert has_web_search_tool(request) is False


def test_has_web_search_tool_with_no_tools():
    """测试：没有工具应该返回 False"""
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[ChatMessage(role="user", content="test")],
        tools=None
    )
    
    assert has_web_search_tool(request) is False


def test_has_web_search_tool_with_different_tool():
    """测试：单个非 web_search 工具应该返回 False"""
    tool = Tool(
        type="function",
        function={"name": "calculator", "description": "Calculate"}
    )
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[ChatMessage(role="user", content="test")],
        tools=[tool]
    )
    
    assert has_web_search_tool(request) is False


# ==================================================================================================
# Test extract_search_query
# ==================================================================================================

def test_extract_search_query_with_prefix():
    """测试：提取带前缀的查询"""
    message = ChatMessage(
        role="user",
        content="Perform a web search for the query: Python tutorials"
    )
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[message],
        tools=None
    )
    
    query = extract_search_query(request)
    assert query == "Python tutorials"


def test_extract_search_query_without_prefix():
    """测试：提取不带前缀的查询"""
    message = ChatMessage(
        role="user",
        content="Python tutorials"
    )
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[message],
        tools=None
    )
    
    query = extract_search_query(request)
    assert query == "Python tutorials"


def test_extract_search_query_from_content_blocks():
    """测试：从 content blocks 中提取查询"""
    text_block = TextContent(type="text", text="Perform a web search for the query: FastAPI docs")
    message = ChatMessage(
        role="user",
        content=[text_block]
    )
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[message],
        tools=None
    )
    
    query = extract_search_query(request)
    assert query == "FastAPI docs"


def test_extract_search_query_from_last_user_message():
    """测试：从最后一条用户消息中提取查询"""
    messages = [
        ChatMessage(role="user", content="First message"),
        ChatMessage(role="assistant", content="Response"),
        ChatMessage(role="user", content="Perform a web search for the query: Latest news")
    ]
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=messages,
        tools=None
    )
    
    query = extract_search_query(request)
    assert query == "Latest news"


def test_extract_search_query_empty_messages():
    """测试：空消息列表应该返回 None"""
    request = ChatCompletionRequest(
        model="claude-sonnet-4",
        messages=[],
        tools=None
    )
    
    query = extract_search_query(request)
    assert query is None


# ==================================================================================================
# Test create_mcp_request
# ==================================================================================================

def test_create_mcp_request():
    """测试：创建 MCP 请求"""
    query = "Python tutorials"
    tool_use_id, mcp_request = create_mcp_request(query)
    
    # 验证 tool_use_id 格式
    assert tool_use_id.startswith("srvtoolu_")
    assert len(tool_use_id) == 41  # "srvtoolu_" (9) + 32 hex chars
    
    # 验证 mcp_request 结构
    assert "id" in mcp_request
    assert mcp_request["id"].startswith("web_search_tooluse_")
    assert mcp_request["jsonrpc"] == "2.0"
    assert mcp_request["method"] == "tools/call"
    assert mcp_request["params"]["name"] == "web_search"
    assert mcp_request["params"]["arguments"]["query"] == query


def test_create_mcp_request_unique_ids():
    """测试：每次调用应该生成唯一的 ID"""
    query = "test query"
    tool_use_id1, mcp_request1 = create_mcp_request(query)
    tool_use_id2, mcp_request2 = create_mcp_request(query)
    
    assert tool_use_id1 != tool_use_id2
    assert mcp_request1["id"] != mcp_request2["id"]


# ==================================================================================================
# Test parse_search_results
# ==================================================================================================

def test_parse_search_results_success():
    """测试：成功解析搜索结果"""
    mcp_response = {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "query": "Python",
                        "totalResults": 2,
                        "results": [
                            {
                                "title": "Python.org",
                                "url": "https://python.org",
                                "snippet": "Official Python website",
                                "publishedDate": 1234567890,
                                "id": "result1",
                                "domain": "python.org"
                            },
                            {
                                "title": "Python Tutorial",
                                "url": "https://docs.python.org",
                                "snippet": "Learn Python"
                            }
                        ]
                    })
                }
            ]
        }
    }
    
    results = parse_search_results(mcp_response)
    
    assert results is not None
    assert results.query == "Python"
    assert results.total_results == 2
    assert len(results.results) == 2
    assert results.results[0].title == "Python.org"
    assert results.results[0].url == "https://python.org"
    assert results.results[0].snippet == "Official Python website"


def test_parse_search_results_empty():
    """测试：空结果"""
    mcp_response = {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "query": "test",
                        "totalResults": 0,
                        "results": []
                    })
                }
            ]
        }
    }
    
    results = parse_search_results(mcp_response)
    
    assert results is not None
    assert results.query == "test"
    assert results.total_results == 0
    assert len(results.results) == 0


def test_parse_search_results_invalid_json():
    """测试：无效的 JSON 应该返回 None"""
    mcp_response = {
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": "invalid json"
                }
            ]
        }
    }
    
    results = parse_search_results(mcp_response)
    assert results is None


def test_parse_search_results_missing_result():
    """测试：缺少 result 字段应该返回 None"""
    mcp_response = {}
    
    results = parse_search_results(mcp_response)
    assert results is None


# ==================================================================================================
# Test generate_search_summary
# ==================================================================================================

def test_generate_search_summary_with_results():
    """测试：生成带结果的摘要"""
    results = WebSearchResults(
        query="Python",
        total_results=2,
        results=[
            WebSearchResult(
                title="Python.org",
                url="https://python.org",
                snippet="Official Python website"
            ),
            WebSearchResult(
                title="Python Tutorial",
                url="https://docs.python.org",
                snippet="Learn Python programming"
            )
        ]
    )
    
    summary = generate_search_summary("Python", results)
    
    assert "Python" in summary
    assert "Python.org" in summary
    assert "https://python.org" in summary
    assert "Official Python website" in summary
    assert "Python Tutorial" in summary


def test_generate_search_summary_no_results():
    """测试：生成无结果的摘要"""
    results = WebSearchResults(
        query="test",
        total_results=0,
        results=[]
    )
    
    summary = generate_search_summary("test", results)
    
    assert "test" in summary
    assert "No results found" in summary


def test_generate_search_summary_long_snippet():
    """测试：长摘要应该被截断"""
    long_snippet = "a" * 300
    results = WebSearchResults(
        query="test",
        total_results=1,
        results=[
            WebSearchResult(
                title="Test",
                url="https://test.com",
                snippet=long_snippet
            )
        ]
    )
    
    summary = generate_search_summary("test", results)
    
    # 摘要应该被截断到 200 字符 + "..."
    assert "..." in summary
    assert len([line for line in summary.split('\n') if 'aaa' in line][0]) < 250


# ==================================================================================================
# Test WebSearchResult and WebSearchResults dataclasses
# ==================================================================================================

def test_web_search_result_creation():
    """测试：创建 WebSearchResult"""
    result = WebSearchResult(
        title="Test",
        url="https://test.com",
        snippet="Test snippet",
        published_date=1234567890,
        id="test_id",
        domain="test.com",
        max_verbatim_word_limit=30,
        public_domain=True
    )
    
    assert result.title == "Test"
    assert result.url == "https://test.com"
    assert result.snippet == "Test snippet"
    assert result.published_date == 1234567890
    assert result.id == "test_id"
    assert result.domain == "test.com"
    assert result.max_verbatim_word_limit == 30
    assert result.public_domain is True


def test_web_search_results_creation():
    """测试：创建 WebSearchResults"""
    results = WebSearchResults(
        query="test",
        total_results=1,
        results=[
            WebSearchResult(title="Test", url="https://test.com")
        ],
        error=None
    )
    
    assert results.query == "test"
    assert results.total_results == 1
    assert len(results.results) == 1
    assert results.error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
