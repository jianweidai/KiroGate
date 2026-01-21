# -*- coding: utf-8 -*-

# KiroGate
# Based on kiro-openai-gateway by Jwadow (https://github.com/Jwadow/kiro-openai-gateway)
# Original Copyright (C) 2025 Jwadow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Web Search 工具处理模块

实现 OpenAI/Anthropic API Web Search 请求到 Kiro MCP 的转换和响应生成
参考 amq2api 的成功实现
"""

import json
import random
import string
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from loguru import logger

from kiro_gateway.models import AnthropicMessagesRequest, ChatCompletionRequest
from kiro_gateway.tokenizer import count_message_tokens, count_tools_tokens


@dataclass
class WebSearchResult:
    """单个搜索结果"""
    title: str
    url: str
    snippet: Optional[str] = None
    published_date: Optional[int] = None
    id: Optional[str] = None
    domain: Optional[str] = None
    max_verbatim_word_limit: Optional[int] = None
    public_domain: Optional[bool] = None


@dataclass
class WebSearchResults:
    """Web Search 搜索结果集合"""
    results: List[WebSearchResult]
    total_results: Optional[int] = None
    query: Optional[str] = None
    error: Optional[str] = None


def has_web_search_tool(request_data: Union[ChatCompletionRequest, AnthropicMessagesRequest]) -> bool:
    """
    检查请求是否为纯 Web Search 请求
    
    条件：tools 有且只有一个，且 name 为 web_search
    
    Args:
        request_data: OpenAI 或 Anthropic 请求数据
        
    Returns:
        bool: 是否为 Web Search 请求
    """
    tools = request_data.tools
    if not tools:
        return False
    
    # OpenAI format: tools[0].function.name
    # Anthropic format: tools[0].name
    if len(tools) != 1:
        return False
    
    tool = tools[0]
    if hasattr(tool, 'function') and hasattr(tool.function, 'name'):
        return tool.function.name == "web_search"
    elif hasattr(tool, 'name'):
        return tool.name == "web_search"
    
    return False


def extract_search_query(request_data: Union[ChatCompletionRequest, AnthropicMessagesRequest]) -> Optional[str]:
    """
    从消息中提取搜索查询
    
    读取 messages 的最后一条用户消息的内容
    并去除 "Perform a web search for the query: " 前缀
    
    Args:
        request_data: OpenAI 或 Anthropic 请求数据
        
    Returns:
        Optional[str]: 搜索查询，如果提取失败则返回 None
    """
    messages = request_data.messages
    if not messages:
        return None
    
    # 从后往前找最后一条用户消息
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        
        content = msg.content
        
        # 提取文本内容
        text = None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list) and len(content) > 0:
            # 查找第一个 text 类型的 content block
            for block in content:
                if hasattr(block, 'type') and block.type == 'text':
                    text = block.text if hasattr(block, 'text') else None
                    break
                elif isinstance(block, dict) and block.get('type') == 'text':
                    text = block.get('text')
                    break
        
        if text:
            # 去除前缀 "Perform a web search for the query: "
            PREFIX = "Perform a web search for the query: "
            if text.startswith(PREFIX):
                query = text[len(PREFIX):]
            else:
                query = text
            
            return query.strip() if query else None
    
    return None


def generate_random_id_22() -> str:
    """生成22位大小写字母和数字的随机字符串"""
    charset = string.ascii_letters + string.digits
    return ''.join(random.choice(charset) for _ in range(22))


def generate_random_id_8() -> str:
    """生成8位小写字母和数字的随机字符串"""
    charset = string.ascii_lowercase + string.digits
    return ''.join(random.choice(charset) for _ in range(8))


def create_mcp_request(query: str) -> tuple[str, Dict[str, Any]]:
    """
    创建 MCP 请求
    
    ID 格式: web_search_tooluse_{22位随机}_{毫秒时间戳}_{8位随机}
    
    Args:
        query: 搜索查询
        
    Returns:
        tuple[str, Dict]: (tool_use_id, mcp_request)
    """
    random_22 = generate_random_id_22()
    timestamp = int(time.time() * 1000)
    random_8 = generate_random_id_8()
    
    request_id = f"web_search_tooluse_{random_22}_{timestamp}_{random_8}"
    
    # tool_use_id 使用 srvtoolu_ 前缀 + 32位随机字符
    tool_use_id = f"srvtoolu_{uuid.uuid4().hex[:32]}"
    
    mcp_request = {
        "id": request_id,
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": {
                "query": query
            }
        }
    }
    
    return tool_use_id, mcp_request


def parse_search_results(mcp_response: Dict[str, Any]) -> Optional[WebSearchResults]:
    """
    解析 MCP 响应中的搜索结果
    
    Args:
        mcp_response: MCP API 响应
        
    Returns:
        Optional[WebSearchResults]: 解析后的搜索结果，失败返回 None
    """
    try:
        result = mcp_response.get('result')
        if not result:
            return None
        
        content = result.get('content', [])
        if not content:
            return None
        
        first_content = content[0]
        if first_content.get('type') != 'text':
            return None
        
        # 解析 JSON 文本
        text = first_content.get('text', '')
        search_data = json.loads(text)
        
        # 构建 WebSearchResults
        results = []
        for item in search_data.get('results', []):
            result = WebSearchResult(
                title=item.get('title', ''),
                url=item.get('url', ''),
                snippet=item.get('snippet'),
                published_date=item.get('publishedDate'),
                id=item.get('id'),
                domain=item.get('domain'),
                max_verbatim_word_limit=item.get('maxVerbatimWordLimit'),
                public_domain=item.get('publicDomain')
            )
            results.append(result)
        
        return WebSearchResults(
            results=results,
            total_results=search_data.get('totalResults'),
            query=search_data.get('query'),
            error=search_data.get('error')
        )
    
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"解析搜索结果失败: {e}")
        return None


def generate_search_summary(query: str, results: Optional[WebSearchResults]) -> str:
    """
    生成搜索结果摘要
    
    Args:
        query: 搜索查询
        results: 搜索结果
        
    Returns:
        str: 格式化的搜索结果摘要
    """
    summary = f'Here are the search results for "{query}":\n\n'
    
    if results and results.results:
        for i, result in enumerate(results.results, 1):
            summary += f"{i}. **{result.title}**\n"
            if result.snippet:
                # 截断过长的摘要
                snippet = result.snippet
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                summary += f"   {snippet}\n"
            summary += f"   Source: {result.url}\n\n"
    else:
        summary += "No results found.\n"
    
    summary += "\nPlease note that these are web search results and may not be fully accurate or up-to-date."
    
    return summary


async def generate_websearch_sse_events_openai(
    model: str,
    query: str,
    tool_use_id: str,
    search_results: Optional[WebSearchResults],
    input_tokens: int
) -> AsyncIterator[str]:
    """
    生成 OpenAI 格式的 Web Search SSE 事件序列
    
    Args:
        model: 模型名称
        query: 搜索查询
        tool_use_id: 工具使用 ID
        search_results: 搜索结果
        input_tokens: 输入 token 数
        
    Yields:
        str: SSE 格式的事件字符串
    """
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created_time = int(time.time())
    
    # 生成搜索结果摘要
    summary = generate_search_summary(query, search_results)
    
    # 1. 首个 chunk - role
    chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant", "content": ""},
            "finish_reason": None
        }]
    }
    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    # 2. 分块发送文本内容
    chunk_size = 100
    for i in range(0, len(summary), chunk_size):
        text_chunk = summary[i:i + chunk_size]
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": text_chunk},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    # 3. 最终 chunk - usage
    output_tokens = (len(summary) + 3) // 4  # 简单估算
    final_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    }
    yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
    
    # 4. [DONE]
    yield "data: [DONE]\n\n"


async def generate_websearch_sse_events_anthropic(
    model: str,
    query: str,
    tool_use_id: str,
    search_results: Optional[WebSearchResults],
    input_tokens: int
) -> AsyncIterator[str]:
    """
    生成 Anthropic 格式的 Web Search SSE 事件序列
    
    Args:
        model: 模型名称
        query: 搜索查询
        tool_use_id: 工具使用 ID
        search_results: 搜索结果
        input_tokens: 输入 token 数
        
    Yields:
        str: SSE 格式的事件字符串
    """
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    
    # 1. message_start
    event = {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0
            }
        }
    }
    yield f"event: message_start\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 2. content_block_start (server_tool_use)
    event = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {
            "id": tool_use_id,
            "type": "server_tool_use",
            "name": "web_search",
            "input": {}
        }
    }
    yield f"event: content_block_start\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 3. content_block_delta (input_json_delta)
    input_json = {"query": query}
    event = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {
            "type": "input_json_delta",
            "partial_json": json.dumps(input_json, ensure_ascii=False)
        }
    }
    yield f"event: content_block_delta\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 4. content_block_stop (server_tool_use)
    event = {
        "type": "content_block_stop",
        "index": 0
    }
    yield f"event: content_block_stop\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 5. content_block_start (web_search_tool_result)
    search_content = []
    if search_results and search_results.results:
        for result in search_results.results:
            search_content.append({
                "type": "web_search_result",
                "title": result.title,
                "url": result.url,
                "encrypted_content": result.snippet or "",
                "page_age": None
            })
    
    event = {
        "type": "content_block_start",
        "index": 1,
        "content_block": {
            "type": "web_search_tool_result",
            "tool_use_id": tool_use_id,
            "content": search_content
        }
    }
    yield f"event: content_block_start\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 6. content_block_stop (web_search_tool_result)
    event = {
        "type": "content_block_stop",
        "index": 1
    }
    yield f"event: content_block_stop\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 7. content_block_start (text)
    event = {
        "type": "content_block_start",
        "index": 2,
        "content_block": {
            "type": "text",
            "text": ""
        }
    }
    yield f"event: content_block_start\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 8. content_block_delta (text_delta) - 生成搜索结果摘要
    summary = generate_search_summary(query, search_results)
    
    # 分块发送文本（每100字符一块）
    chunk_size = 100
    for i in range(0, len(summary), chunk_size):
        chunk = summary[i:i + chunk_size]
        event = {
            "type": "content_block_delta",
            "index": 2,
            "delta": {
                "type": "text_delta",
                "text": chunk
            }
        }
        yield f"event: content_block_delta\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 9. content_block_stop (text)
    event = {
        "type": "content_block_stop",
        "index": 2
    }
    yield f"event: content_block_stop\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 10. message_delta
    output_tokens = (len(summary) + 3) // 4  # 简单估算
    event = {
        "type": "message_delta",
        "delta": {
            "stop_reason": "end_turn",
            "stop_sequence": None
        },
        "usage": {
            "output_tokens": output_tokens
        }
    }
    yield f"event: message_delta\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    # 11. message_stop
    event = {
        "type": "message_stop"
    }
    yield f"event: message_stop\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def handle_websearch_request(
    request: Request,
    request_data: Union[ChatCompletionRequest, AnthropicMessagesRequest],
    response_format: str = "openai"
) -> StreamingResponse:
    """
    处理 Web Search 请求
    
    Args:
        request: FastAPI Request
        request_data: 请求数据
        response_format: 响应格式（"openai" 或 "anthropic"）
        
    Returns:
        StreamingResponse: SSE 流式响应
    """
    logger.info(f"Processing Web Search request (format: {response_format})")
    
    # 1. 提取搜索查询
    query = extract_search_query(request_data)
    if not query:
        logger.error("Failed to extract search query from request")
        # 返回错误响应
        async def error_stream():
            if response_format == "anthropic":
                error_event = {
                    "type": "error",
                    "error": {
                        "type": "invalid_request_error",
                        "message": "Failed to extract search query"
                    }
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
            else:
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    logger.info(f"Web Search query: {query}")
    
    # 2. 构建 MCP 请求
    tool_use_id, mcp_request = create_mcp_request(query)
    logger.debug(f"MCP request: {json.dumps(mcp_request, ensure_ascii=False)}")
    
    # 3. 调用 Kiro MCP API
    auth_manager = getattr(request.state, 'auth_manager', None) or request.app.state.auth_manager
    
    try:
        # 使用 auth_manager 的 q_host 和 headers
        mcp_url = f"{auth_manager.q_host}/mcp"
        headers = {
            "Authorization": f"Bearer {auth_manager.access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(mcp_url, json=mcp_request, headers=headers)
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"MCP API error: {response.status_code} - {error_text}")
                raise Exception(f"MCP API returned {response.status_code}: {error_text}")
            
            mcp_response = response.json()
            logger.debug(f"MCP response: {json.dumps(mcp_response, ensure_ascii=False)[:500]}")
    
    except Exception as e:
        logger.error(f"Failed to call MCP API: {e}")
        # 返回错误响应
        async def error_stream():
            if response_format == "anthropic":
                error_event = {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": f"Failed to perform web search: {str(e)}"
                    }
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
            else:
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    # 4. 解析搜索结果
    search_results = parse_search_results(mcp_response)
    if search_results:
        logger.info(f"Found {len(search_results.results)} search results")
    else:
        logger.warning("No search results found or failed to parse")
    
    # 5. 计算输入 tokens
    messages_for_tokenizer = [msg.model_dump() for msg in request_data.messages]
    tools_for_tokenizer = [tool.model_dump() for tool in request_data.tools] if request_data.tools else None
    
    input_tokens = count_message_tokens(messages_for_tokenizer, apply_claude_correction=False)
    if tools_for_tokenizer:
        input_tokens += count_tools_tokens(tools_for_tokenizer, apply_claude_correction=False)
    
    # 6. 生成 SSE 事件流
    if response_format == "anthropic":
        event_generator = generate_websearch_sse_events_anthropic(
            request_data.model,
            query,
            tool_use_id,
            search_results,
            input_tokens
        )
    else:
        event_generator = generate_websearch_sse_events_openai(
            request_data.model,
            query,
            tool_use_id,
            search_results,
            input_tokens
        )
    
    logger.info(f"Web Search request completed successfully (format: {response_format})")
    return StreamingResponse(event_generator, media_type="text/event-stream")
