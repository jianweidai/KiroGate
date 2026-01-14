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
Streaming response processing logic, converts Kiro stream to OpenAI/Anthropic format.

Contains generators for:
- Converting AWS SSE to OpenAI SSE
- Forming streaming chunks
- Processing tool calls in stream
- Adaptive timeout handling for slow models
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING, AsyncGenerator, Callable, Awaitable, Optional, Dict, Any, List

import httpx
from fastapi import HTTPException
from loguru import logger

from kiro_gateway.parsers import AwsEventStreamParser, parse_bracket_tool_calls, deduplicate_tool_calls
from kiro_gateway.utils import generate_completion_id
from kiro_gateway.config import settings, get_adaptive_timeout
from kiro_gateway.tokenizer import count_tokens, count_message_tokens, count_tools_tokens

if TYPE_CHECKING:
    from kiro_gateway.auth import KiroAuthManager
    from kiro_gateway.cache import ModelInfoCache

try:
    from kiro_gateway.debug_logger import debug_logger
except ImportError:
    debug_logger = None


# ==================================================================================================
# Extended Thinking 相关常量和辅助函数
# ==================================================================================================

# Thinking 标签
THINKING_START_TAG = "<thinking>"
THINKING_END_TAG = "</thinking>"


def _pending_tag_suffix(buffer: str, tag: str) -> int:
    """
    检测 buffer 末尾是否是 tag 的部分前缀。
    
    用于处理跨字节流边界的标签检测。
    
    Args:
        buffer: 当前缓冲区内容
        tag: 要检测的标签
    
    Returns:
        部分标签的长度（0 表示没有部分标签）
        
    Examples:
        >>> _pending_tag_suffix("hello<thi", "<thinking>")
        4  # "<thi" 是 "<thinking>" 的前缀
        >>> _pending_tag_suffix("hello", "<thinking>")
        0  # 没有部分标签
    """
    max_len = min(len(buffer), len(tag) - 1)
    for length in range(max_len, 0, -1):
        if buffer[-length:] == tag[:length]:
            return length
    return 0


class ThinkingStreamHandler:
    """
    Extended Thinking 流解析处理器。
    
    实时解析 Kiro API 返回的文本流，检测 <thinking> 标签并转换为
    Anthropic 格式的 thinking content block。
    
    使用状态机管理 thinking 块的开始和结束，支持跨 chunk 边界的标签检测。
    
    Attributes:
        in_thinking_block: 是否在 thinking 块中
        thinking_buffer: 累积待处理的文本
        pending_start_chars: 待处理的开始标签字符数
        thinking_enabled: 是否启用 thinking 解析
    """
    
    def __init__(self, thinking_enabled: bool = True):
        """
        初始化 ThinkingStreamHandler。
        
        Args:
            thinking_enabled: 是否启用 thinking 解析
        """
        self.thinking_enabled = thinking_enabled
        self.in_thinking_block = False
        self.thinking_buffer = ""
        self.pending_start_chars = 0
    
    def process_content(self, content: str) -> List[Dict[str, Any]]:
        """
        处理接收到的内容，解析 thinking 标签。
        
        Args:
            content: 新接收到的内容片段
        
        Returns:
            事件列表，每个事件包含：
            - type: "text" 或 "thinking"
            - content: 内容片段
            - action: "start"（开始块）、"delta"（内容增量）、"stop"（结束块）
        """
        if not self.thinking_enabled:
            # 未启用 thinking，直接返回文本
            return [{"type": "text", "content": content, "action": "delta"}]
        
        events = []
        self.thinking_buffer += content
        
        while self.thinking_buffer:
            if not self.in_thinking_block:
                # 不在 thinking 块中，查找 <thinking> 开始标签
                events_part = self._process_text_mode()
                events.extend(events_part)
            else:
                # 在 thinking 块中，查找 </thinking> 结束标签
                events_part = self._process_thinking_mode()
                events.extend(events_part)
            
            # 检查是否需要继续处理
            if not events_part:
                break
        
        return events
    
    def _process_text_mode(self) -> List[Dict[str, Any]]:
        """处理文本模式，查找 thinking 开始标签。"""
        events = []
        
        think_start = self.thinking_buffer.find(THINKING_START_TAG)
        
        if think_start == -1:
            # 没有找到完整的开始标签
            pending = _pending_tag_suffix(self.thinking_buffer, THINKING_START_TAG)
            
            # 发送非标签部分作为普通文本
            emit_len = len(self.thinking_buffer) - pending
            if emit_len > 0:
                text_chunk = self.thinking_buffer[:emit_len]
                events.append({"type": "text", "content": text_chunk, "action": "delta"})
            
            self.thinking_buffer = self.thinking_buffer[emit_len:]
        else:
            # 找到完整的 <thinking> 标签
            before_text = self.thinking_buffer[:think_start]
            if before_text:
                # 发送标签前的文本
                events.append({"type": "text", "content": before_text, "action": "delta"})
            
            # 进入 thinking 模式
            events.append({"type": "thinking", "content": "", "action": "start"})
            self.in_thinking_block = True
            self.thinking_buffer = self.thinking_buffer[think_start + len(THINKING_START_TAG):]
        
        return events
    
    def _process_thinking_mode(self) -> List[Dict[str, Any]]:
        """处理 thinking 模式，查找结束标签。"""
        events = []
        
        think_end = self.thinking_buffer.find(THINKING_END_TAG)
        
        if think_end == -1:
            # 没有找到完整的结束标签
            pending = _pending_tag_suffix(self.thinking_buffer, THINKING_END_TAG)
            emit_len = len(self.thinking_buffer) - pending
            
            if emit_len > 0:
                thinking_chunk = self.thinking_buffer[:emit_len]
                events.append({"type": "thinking", "content": thinking_chunk, "action": "delta"})
            
            self.thinking_buffer = self.thinking_buffer[emit_len:]
        else:
            # 找到完整的 </thinking> 标签
            thinking_chunk = self.thinking_buffer[:think_end]
            if thinking_chunk:
                events.append({"type": "thinking", "content": thinking_chunk, "action": "delta"})
            
            # 关闭 thinking 块
            events.append({"type": "thinking", "content": "", "action": "stop"})
            self.in_thinking_block = False
            self.thinking_buffer = self.thinking_buffer[think_end + len(THINKING_END_TAG):]
        
        return events
    
    def flush(self) -> List[Dict[str, Any]]:
        """
        刷新缓冲区中剩余的内容。
        
        在流结束时调用，输出所有剩余内容。
        
        Returns:
            剩余内容的事件列表
        """
        events = []
        
        if self.thinking_buffer:
            if self.in_thinking_block:
                events.append({"type": "thinking", "content": self.thinking_buffer, "action": "delta"})
            else:
                events.append({"type": "text", "content": self.thinking_buffer, "action": "delta"})
            self.thinking_buffer = ""
        
        return events


class FirstTokenTimeoutError(Exception):
    """Exception raised when first token timeout occurs."""
    pass


class StreamReadTimeoutError(Exception):
    """Exception raised when stream read timeout occurs."""
    pass


async def _read_chunk_with_timeout(
    byte_iterator,
    timeout: float
) -> bytes:
    """
    Read a chunk from byte iterator with timeout.

    Args:
        byte_iterator: Async byte iterator
        timeout: Timeout in seconds

    Returns:
        Bytes chunk

    Raises:
        StreamReadTimeoutError: If timeout occurs
        StopAsyncIteration: If iterator is exhausted
    """
    try:
        return await asyncio.wait_for(
            byte_iterator.__anext__(),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise StreamReadTimeoutError(f"流式读取在 {timeout}s 后超时")


def _calculate_usage_tokens(
    full_content: str,
    context_usage_percentage: Optional[float],
    model_cache: "ModelInfoCache",
    model: str,
    request_messages: Optional[list],
    request_tools: Optional[list]
) -> Dict[str, Any]:
    """
    Calculate token usage from response.

    Args:
        full_content: Full response content
        context_usage_percentage: Context usage percentage from API
        model_cache: Model cache for token limits
        model: Model name
        request_messages: Request messages for fallback counting
        request_tools: Request tools for fallback counting

    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens and source info
    """
    completion_tokens = count_tokens(full_content)

    total_tokens_from_api = 0
    if context_usage_percentage is not None and context_usage_percentage > 0:
        max_input_tokens = model_cache.get_max_input_tokens(model)
        total_tokens_from_api = int((context_usage_percentage / 100) * max_input_tokens)

    if total_tokens_from_api > 0:
        prompt_tokens = max(0, total_tokens_from_api - completion_tokens)
        total_tokens = total_tokens_from_api
        prompt_source = "subtraction"
        total_source = "API Kiro"
    else:
        prompt_tokens = 0
        if request_messages:
            prompt_tokens += count_message_tokens(request_messages, apply_claude_correction=False)
        if request_tools:
            prompt_tokens += count_tools_tokens(request_tools, apply_claude_correction=False)
        total_tokens = prompt_tokens + completion_tokens
        prompt_source = "tiktoken"
        total_source = "tiktoken"

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_source": prompt_source,
        "total_source": total_source
    }


def _format_tool_calls_for_streaming(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format tool calls for streaming response with required index field.

    Args:
        tool_calls: List of tool calls

    Returns:
        List of indexed tool calls for streaming
    """
    indexed_tool_calls = []
    for idx, tc in enumerate(tool_calls):
        func = tc.get("function") or {}
        tool_name = func.get("name") or ""
        tool_args = func.get("arguments") or "{}"

        logger.debug(f"Tool call [{idx}] '{tool_name}': id={tc.get('id')}, args_length={len(tool_args)}")

        indexed_tc = {
            "index": idx,
            "id": tc.get("id"),
            "type": tc.get("type", "function"),
            "function": {
                "name": tool_name,
                "arguments": tool_args
            }
        }
        indexed_tool_calls.append(indexed_tc)

    return indexed_tool_calls


def _format_tool_calls_for_non_streaming(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format tool calls for non-streaming response (without index field).

    Args:
        tool_calls: List of tool calls

    Returns:
        List of cleaned tool calls for non-streaming
    """
    cleaned_tool_calls = []
    for tc in tool_calls:
        func = tc.get("function") or {}
        cleaned_tc = {
            "id": tc.get("id"),
            "type": tc.get("type", "function"),
            "function": {
                "name": func.get("name", ""),
                "arguments": func.get("arguments", "{}")
            }
        }
        cleaned_tool_calls.append(cleaned_tc)

    return cleaned_tool_calls


async def stream_kiro_to_openai_internal(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager",
    first_token_timeout: float = settings.first_token_timeout,
    stream_read_timeout: float = settings.stream_read_timeout,
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    Internal generator for converting Kiro stream to OpenAI format.

    Parses AWS SSE stream and converts events to OpenAI chat.completion.chunk.
    Supports tool calls and usage calculation.

    IMPORTANT: This function raises FirstTokenTimeoutError if first token
    is not received within first_token_timeout seconds.

    Args:
        client: HTTP client (for connection management)
        response: HTTP response with data stream
        model: Model name to include in response
        model_cache: Model cache for token limits
        auth_manager: Authentication manager
        first_token_timeout: First token timeout (seconds)
        stream_read_timeout: Stream read timeout for subsequent chunks (seconds)
        request_messages: Original request messages (for fallback token counting)
        request_tools: Original request tools (for fallback token counting)

    Yields:
        Strings in SSE format: "data: {...}\\n\\n" or "data: [DONE]\\n\\n"

    Raises:
        FirstTokenTimeoutError: If first token not received within timeout
        StreamReadTimeoutError: If stream read times out
    """
    completion_id = generate_completion_id()
    created_time = int(time.time())
    first_chunk = True

    parser = AwsEventStreamParser()
    metering_data = None
    context_usage_percentage = None
    content_parts: list[str] = []  # 使用 list 替代字符串拼接，提升性能

    # 根据模型自适应调整超时时间
    adaptive_first_token_timeout = get_adaptive_timeout(model, first_token_timeout)
    adaptive_stream_read_timeout = get_adaptive_timeout(model, stream_read_timeout)

    try:
        byte_iterator = response.aiter_bytes()

        # Wait for first chunk with adaptive timeout
        try:
            first_byte_chunk = await asyncio.wait_for(
                byte_iterator.__anext__(),
                timeout=adaptive_first_token_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"First token timeout after {adaptive_first_token_timeout}s (model: {model})")
            raise FirstTokenTimeoutError(f"在 {adaptive_first_token_timeout}s 内未收到响应")
        except StopAsyncIteration:
            logger.debug("Empty response from Kiro API")
            yield "data: [DONE]\n\n"
            return

        # Process first chunk
        if debug_logger:
            debug_logger.log_raw_chunk(first_byte_chunk)

        events = parser.feed(first_byte_chunk)
        for event in events:
            if event["type"] == "content":
                content = event["data"]
                content_parts.append(content)

                delta = {"content": content}
                if first_chunk:
                    delta["role"] = "assistant"
                    first_chunk = False

                openai_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}]
                }

                chunk_text = f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"

                if debug_logger:
                    debug_logger.log_modified_chunk(chunk_text.encode('utf-8'))

                yield chunk_text

            elif event["type"] == "usage":
                metering_data = event["data"]

            elif event["type"] == "context_usage":
                context_usage_percentage = event["data"]

        # Continue reading remaining chunks with adaptive timeout
        # 对于慢模型和大文档，可能需要更长时间等待每个 chunk
        consecutive_timeouts = 0
        max_consecutive_timeouts = 3  # 允许连续超时次数
        while True:
            try:
                chunk = await _read_chunk_with_timeout(byte_iterator, adaptive_stream_read_timeout)
                consecutive_timeouts = 0  # 重置超时计数器
            except StopAsyncIteration:
                break
            except StreamReadTimeoutError as e:
                consecutive_timeouts += 1
                if consecutive_timeouts <= max_consecutive_timeouts:
                    logger.warning(
                        f"Stream read timeout {consecutive_timeouts}/{max_consecutive_timeouts} "
                        f"after {adaptive_stream_read_timeout}s (model: {model}). "
                        f"Model may be processing large content - continuing to wait..."
                    )
                    # 继续等待下一个 chunk
                    continue
                else:
                    logger.error(f"Stream read timeout after {max_consecutive_timeouts} consecutive timeouts (model: {model}): {e}")
                    raise

            if debug_logger:
                debug_logger.log_raw_chunk(chunk)

            events = parser.feed(chunk)

            for event in events:
                if event["type"] == "content":
                    content = event["data"]
                    content_parts.append(content)

                    delta = {"content": content}
                    if first_chunk:
                        delta["role"] = "assistant"
                        first_chunk = False

                    openai_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": model,
                        "choices": [{"index": 0, "delta": delta, "finish_reason": None}]
                    }

                    chunk_text = f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"

                    if debug_logger:
                        debug_logger.log_modified_chunk(chunk_text.encode('utf-8'))

                    yield chunk_text

                elif event["type"] == "usage":
                    metering_data = event["data"]

                elif event["type"] == "context_usage":
                    context_usage_percentage = event["data"]

        # 合并 content 部分（比字符串拼接更高效）
        full_content = ''.join(content_parts)

        # Check bracket-style tool calls in full content
        bracket_tool_calls = parse_bracket_tool_calls(full_content)
        all_tool_calls = parser.get_tool_calls() + bracket_tool_calls
        all_tool_calls = deduplicate_tool_calls(all_tool_calls)

        finish_reason = "tool_calls" if all_tool_calls else "stop"

        # Calculate usage tokens using helper function
        usage_info = _calculate_usage_tokens(
            full_content, context_usage_percentage, model_cache, model,
            request_messages, request_tools
        )

        # Send tool calls if any
        if all_tool_calls:
            logger.debug(f"Processing {len(all_tool_calls)} tool calls for streaming response")
            indexed_tool_calls = _format_tool_calls_for_streaming(all_tool_calls)

            tool_calls_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_time,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"tool_calls": indexed_tool_calls},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(tool_calls_chunk, ensure_ascii=False)}\n\n"

        # Final chunk with usage
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": usage_info["prompt_tokens"],
                "completion_tokens": usage_info["completion_tokens"],
                "total_tokens": usage_info["total_tokens"],
            }
        }

        if metering_data:
            final_chunk["usage"]["credits_used"] = metering_data

        logger.debug(
            f"[Usage] {model}: "
            f"prompt_tokens={usage_info['prompt_tokens']} ({usage_info['prompt_source']}), "
            f"completion_tokens={usage_info['completion_tokens']} (tiktoken), "
            f"total_tokens={usage_info['total_tokens']} ({usage_info['total_source']})"
        )

        yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    except FirstTokenTimeoutError:
        raise
    except StreamReadTimeoutError:
        raise
    except Exception as e:
        logger.error(f"Error during streaming: {e}", exc_info=True)
    finally:
        await response.aclose()
        logger.debug("Streaming completed")


async def stream_kiro_to_openai(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager",
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    Генератор для преобразования потока Kiro в OpenAI формат.
    
    Это wrapper над stream_kiro_to_openai_internal, который НЕ делает retry.
    Retry логика реализована в stream_with_first_token_retry.
    
    Args:
        client: HTTP клиент (для управления соединением)
        response: HTTP ответ с потоком данных
        model: Имя модели для включения в ответ
        model_cache: Кэш моделей для получения лимитов токенов
        auth_manager: Менеджер аутентификации
        request_messages: Исходные сообщения запроса (для fallback подсчёта токенов)
        request_tools: Исходные инструменты запроса (для fallback подсчёта токенов)
    
    Yields:
        Строки в формате SSE: "data: {...}\\n\\n" или "data: [DONE]\\n\\n"
    """
    async for chunk in stream_kiro_to_openai_internal(
        client, response, model, model_cache, auth_manager,
        request_messages=request_messages,
        request_tools=request_tools
    ):
        yield chunk


async def stream_with_first_token_retry(
    make_request: Callable[[], Awaitable[httpx.Response]],
    client: httpx.AsyncClient,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager",
    max_retries: int = settings.first_token_max_retries,
    first_token_timeout: float = settings.first_token_timeout,
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    Streaming с автоматическим retry при таймауте первого токена.
    
    Если модель не отвечает в течение first_token_timeout секунд,
    запрос отменяется и делается новый. Максимум max_retries попыток.
    
    Это seamless для пользователя - он просто видит задержку,
    но в итоге получает ответ (или ошибку после всех попыток).
    
    Args:
        make_request: Функция для создания нового HTTP запроса
        client: HTTP клиент
        model: Имя модели
        model_cache: Кэш моделей
        auth_manager: Менеджер аутентификации
        max_retries: Максимальное количество попыток
        first_token_timeout: Таймаут ожидания первого токена (секунды)
        request_messages: Исходные сообщения запроса (для fallback подсчёта токенов)
        request_tools: Исходные инструменты запроса (для fallback подсчёта токенов)
    
    Yields:
        Строки в формате SSE
    
    Raises:
        HTTPException: После исчерпания всех попыток
    
    Example:
        >>> async def make_req():
        ...     return await http_client.request_with_retry("POST", url, payload, stream=True)
        >>> async for chunk in stream_with_first_token_retry(make_req, client, model, cache, auth):
        ...     print(chunk)
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(max_retries):
        response: Optional[httpx.Response] = None
        try:
            # Делаем запрос
            if attempt > 0:
                logger.warning(f"Retry attempt {attempt + 1}/{max_retries} after first token timeout")
            
            response = await make_request()
            
            if response.status_code != 200:
                # Ошибка от API - закрываем response и выбрасываем исключение
                try:
                    error_content = await response.aread()
                    error_text = error_content.decode('utf-8', errors='replace')
                except Exception:
                    error_text = "未知错误"
                
                try:
                    await response.aclose()
                except Exception:
                    pass
                
                logger.error(f"Error from Kiro API: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"上游 API 错误: {error_text}"
                )
            
            # Пытаемся стримить с таймаутом на первый токен
            async for chunk in stream_kiro_to_openai_internal(
                client,
                response,
                model,
                model_cache,
                auth_manager,
                first_token_timeout=first_token_timeout,
                request_messages=request_messages,
                request_tools=request_tools
            ):
                yield chunk
            
            # Успешно завершили - выходим
            return
            
        except FirstTokenTimeoutError as e:
            last_error = e
            logger.warning(f"First token timeout on attempt {attempt + 1}/{max_retries}")
            
            # Закрываем текущий response если он открыт
            if response:
                try:
                    await response.aclose()
                except Exception:
                    pass
            
            # Продолжаем к следующей попытке
            continue
            
        except Exception as e:
            # Другие ошибки - не retry, пробрасываем
            logger.error(f"Unexpected error during streaming: {e}", exc_info=True)
            if response:
                try:
                    await response.aclose()
                except Exception:
                    pass
            raise
    
    # Все попытки исчерпаны - выбрасываем HTTP ошибку
    logger.error(f"All {max_retries} attempts failed due to first token timeout")
    raise HTTPException(
        status_code=504,
        detail=f"模型在 {max_retries} 次尝试后仍未在 {first_token_timeout}s 内响应，请稍后再试。"
    )


async def collect_stream_response(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager",
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None
) -> dict:
    """
    Собирает полный ответ из streaming потока.
    
    Используется для non-streaming режима - собирает все chunks
    и формирует единый ответ.
    
    Args:
        client: HTTP клиент
        response: HTTP ответ с потоком
        model: Имя модели
        model_cache: Кэш моделей
        auth_manager: Менеджер аутентификации
        request_messages: Исходные сообщения запроса (для fallback подсчёта токенов)
        request_tools: Исходные инструменты запроса (для fallback подсчёта токенов)
    
    Returns:
        Словарь с полным ответом в формате OpenAI chat.completion
    """
    content_parts: list[str] = []  # 使用 list 替代字符串拼接，提升性能
    final_usage = None
    tool_calls = []
    completion_id = generate_completion_id()

    async for chunk_str in stream_kiro_to_openai(
        client,
        response,
        model,
        model_cache,
        auth_manager,
        request_messages=request_messages,
        request_tools=request_tools
    ):
        if not chunk_str.startswith("data:"):
            continue
        
        data_str = chunk_str[len("data:"):].strip()
        if not data_str or data_str == "[DONE]":
            continue
        
        try:
            chunk_data = json.loads(data_str)
            
            # Извлекаем данные из chunk
            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
            if "content" in delta:
                content_parts.append(delta["content"])
            if "tool_calls" in delta:
                tool_calls.extend(delta["tool_calls"])
            
            # Сохраняем usage из последнего chunk
            if "usage" in chunk_data:
                final_usage = chunk_data["usage"]
                
        except (json.JSONDecodeError, IndexError):
            continue

    # 合并 content 部分（比字符串拼接更高效）
    full_content = ''.join(content_parts)

    # Формируем финальный ответ
    message = {"role": "assistant", "content": full_content}
    if tool_calls:
        # Для non-streaming ответа удаляем поле index из tool_calls,
        # так как оно требуется только для streaming chunks
        cleaned_tool_calls = []
        for tc in tool_calls:
            # Извлекаем function с защитой от None
            func = tc.get("function") or {}
            cleaned_tc = {
                "id": tc.get("id"),
                "type": tc.get("type", "function"),
                "function": {
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", "{}")
                }
            }
            cleaned_tool_calls.append(cleaned_tc)
        message["tool_calls"] = cleaned_tool_calls
    
    finish_reason = "tool_calls" if tool_calls else "stop"
    
    # Формируем usage для ответа
    usage = final_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    # Логируем информацию о токенах для отладки (non-streaming использует те же логи из streaming)
    
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason
        }],
        "usage": usage
    }


# ==================================================================================================
# Anthropic Streaming Functions
# ==================================================================================================

def generate_anthropic_message_id() -> str:
    """Генерирует ID сообщения в формате Anthropic."""
    import uuid
    return f"msg_{uuid.uuid4().hex[:24]}"


async def stream_kiro_to_anthropic(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager",
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None,
    thinking_enabled: bool = False,
    stream_read_timeout: float = settings.stream_read_timeout
) -> AsyncGenerator[str, None]:
    """
    Преобразует поток Kiro в формат Anthropic SSE.

    Anthropic использует другой формат событий:
    - message_start: начало сообщения
    - content_block_start: начало блока контента
    - content_block_delta: дельта контента (text_delta или input_json_delta)
    - content_block_stop: конец блока контента
    - message_delta: финальная информация (stop_reason, usage)
    - message_stop: конец сообщения

    Args:
        client: HTTP клиент
        response: HTTP ответ с потоком
        model: Имя модели
        model_cache: Кэш моделей
        auth_manager: Менеджер аутентификации
        request_messages: Сообщения запроса (для подсчёта токенов)
        request_tools: Инструменты запроса (для подсчёта токенов)
        thinking_enabled: Включен ли режим thinking
        stream_read_timeout: Stream read timeout for each chunk (seconds)

    Yields:
        Строки в формате Anthropic SSE
    """
    message_id = generate_anthropic_message_id()
    parser = AwsEventStreamParser()
    metering_data = None
    context_usage_percentage = None
    content_parts: list[str] = []  # 使用 list 替代字符串拼接，提升性能
    content_block_index = 0
    text_block_started = False
    thinking_block_started = False  # Extended Thinking: 跟踪 thinking 块状态
    tool_blocks_started = {}  # tool_id -> index
    
    # 初始化 ThinkingStreamHandler
    thinking_handler = ThinkingStreamHandler(thinking_enabled=thinking_enabled)
    
    if thinking_enabled:
        logger.debug("Extended Thinking 已启用，将解析 <thinking> 标签")

    # 根据模型自适应调整超时时间
    adaptive_stream_read_timeout = get_adaptive_timeout(model, stream_read_timeout)

    # Pre-calculate input_tokens (can be determined before stream starts)
    # This ensures message_start event contains real input_tokens value
    pre_calculated_input_tokens = 0
    if request_messages:
        pre_calculated_input_tokens += count_message_tokens(request_messages, apply_claude_correction=False)
    if request_tools:
        pre_calculated_input_tokens += count_tools_tokens(request_tools, apply_claude_correction=False)

    try:
        # message_start
        message_start = {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": pre_calculated_input_tokens,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0
                }
            }
        }

        
        yield f"event: message_start\ndata: {json.dumps(message_start, ensure_ascii=False)}\n\n"

        # Read chunks with adaptive timeout
        # 对于慢模型和大文档，可能需要更长时间等待每个 chunk
        byte_iterator = response.aiter_bytes()
        consecutive_timeouts = 0
        max_consecutive_timeouts = 3  # 允许连续超时次数
        while True:
            try:
                chunk = await _read_chunk_with_timeout(byte_iterator, adaptive_stream_read_timeout)
                consecutive_timeouts = 0  # 重置超时计数器
            except StopAsyncIteration:
                break
            except StreamReadTimeoutError as e:
                consecutive_timeouts += 1
                if consecutive_timeouts <= max_consecutive_timeouts:
                    logger.warning(
                        f"Anthropic stream timeout {consecutive_timeouts}/{max_consecutive_timeouts} "
                        f"after {adaptive_stream_read_timeout}s (model: {model}). "
                        f"Model may be processing large content - continuing to wait..."
                    )
                    continue
                else:
                    logger.error(f"Anthropic stream read timeout after {max_consecutive_timeouts} consecutive timeouts (model: {model}): {e}")
                    raise

            if debug_logger:
                debug_logger.log_raw_chunk(chunk)

            events = parser.feed(chunk)

            for event in events:
                if event["type"] == "content":
                    content = event["data"]
                    content_parts.append(content)
                    
                    # 使用 ThinkingStreamHandler 处理内容
                    thinking_events = thinking_handler.process_content(content)
                    
                    for te in thinking_events:
                        if te["type"] == "thinking":
                            if te["action"] == "start":
                                # 先关闭当前的 text block（如果有）
                                if text_block_started:
                                    block_stop = {
                                        "type": "content_block_stop",
                                        "index": content_block_index
                                    }
                                    yield f"event: content_block_stop\ndata: {json.dumps(block_stop, ensure_ascii=False)}\n\n"
                                    content_block_index += 1
                                    text_block_started = False
                                
                                # 开始 thinking block
                                block_start = {
                                    "type": "content_block_start",
                                    "index": content_block_index,
                                    "content_block": {"type": "thinking", "thinking": ""}
                                }
                                yield f"event: content_block_start\ndata: {json.dumps(block_start, ensure_ascii=False)}\n\n"
                                thinking_block_started = True
                                
                            elif te["action"] == "delta" and te["content"]:
                                # thinking delta
                                if thinking_block_started:
                                    delta = {
                                        "type": "content_block_delta",
                                        "index": content_block_index,
                                        "delta": {"type": "thinking_delta", "thinking": te["content"]}
                                    }
                                    yield f"event: content_block_delta\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n"
                                    
                            elif te["action"] == "stop":
                                # 关闭 thinking block
                                if thinking_block_started:
                                    block_stop = {
                                        "type": "content_block_stop",
                                        "index": content_block_index
                                    }
                                    yield f"event: content_block_stop\ndata: {json.dumps(block_stop, ensure_ascii=False)}\n\n"
                                    content_block_index += 1
                                    thinking_block_started = False
                        
                        elif te["type"] == "text" and te["content"]:
                            # 普通文本内容
                            if not text_block_started:
                                block_start = {
                                    "type": "content_block_start",
                                    "index": content_block_index,
                                    "content_block": {"type": "text", "text": ""}
                                }
                                yield f"event: content_block_start\ndata: {json.dumps(block_start, ensure_ascii=False)}\n\n"
                                text_block_started = True
                            
                            # text_delta
                            delta = {
                                "type": "content_block_delta",
                                "index": content_block_index,
                                "delta": {"type": "text_delta", "text": te["content"]}
                            }
                            yield f"event: content_block_delta\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n"
                            
                            if debug_logger:
                                debug_logger.log_modified_chunk(f"event: content_block_delta\ndata: {json.dumps(delta)}\n\n".encode('utf-8'))

                elif event["type"] == "usage":
                    metering_data = event["data"]

                elif event["type"] == "context_usage":
                    context_usage_percentage = event["data"]
        
        # 刷新 thinking handler 中剩余的内容
        flush_events = thinking_handler.flush()
        for te in flush_events:
            if te["type"] == "thinking" and te["content"] and thinking_block_started:
                delta = {
                    "type": "content_block_delta",
                    "index": content_block_index,
                    "delta": {"type": "thinking_delta", "thinking": te["content"]}
                }
                yield f"event: content_block_delta\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n"
            elif te["type"] == "text" and te["content"]:
                if not text_block_started:
                    block_start = {
                        "type": "content_block_start",
                        "index": content_block_index,
                        "content_block": {"type": "text", "text": ""}
                    }
                    yield f"event: content_block_start\ndata: {json.dumps(block_start, ensure_ascii=False)}\n\n"
                    text_block_started = True
                
                delta = {
                    "type": "content_block_delta",
                    "index": content_block_index,
                    "delta": {"type": "text_delta", "text": te["content"]}
                }
                yield f"event: content_block_delta\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n"
        
        # 关闭所有未关闭的块
        if thinking_block_started:
            block_stop = {
                "type": "content_block_stop",
                "index": content_block_index
            }
            yield f"event: content_block_stop\ndata: {json.dumps(block_stop, ensure_ascii=False)}\n\n"
            content_block_index += 1
            
        if text_block_started:
            block_stop = {
                "type": "content_block_stop",
                "index": content_block_index
            }
            yield f"event: content_block_stop\ndata: {json.dumps(block_stop, ensure_ascii=False)}\n\n"
            content_block_index += 1

        # 合并 content 部分（比字符串拼接更高效）
        full_content = ''.join(content_parts)

        # Обрабатываем tool calls
        bracket_tool_calls = parse_bracket_tool_calls(full_content)
        all_tool_calls = parser.get_tool_calls() + bracket_tool_calls
        all_tool_calls = deduplicate_tool_calls(all_tool_calls)

        # Отправляем tool_use blocks
        for tc in all_tool_calls:
            func = tc.get("function") or {}
            tool_name = func.get("name") or ""
            tool_args_str = func.get("arguments") or "{}"
            tool_id = tc.get("id") or f"toolu_{generate_completion_id()[8:]}"

            try:
                tool_input = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_input = {}

            # content_block_start для tool_use
            tool_block_start = {
                "type": "content_block_start",
                "index": content_block_index,
                "content_block": {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool_name,
                    "input": {}
                }
            }
            yield f"event: content_block_start\ndata: {json.dumps(tool_block_start, ensure_ascii=False)}\n\n"

            # input_json_delta
            if tool_input:
                input_delta = {
                    "type": "content_block_delta",
                    "index": content_block_index,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(tool_input, ensure_ascii=False)
                    }
                }
                yield f"event: content_block_delta\ndata: {json.dumps(input_delta, ensure_ascii=False)}\n\n"

            # content_block_stop
            tool_block_stop = {
                "type": "content_block_stop",
                "index": content_block_index
            }
            yield f"event: content_block_stop\ndata: {json.dumps(tool_block_stop, ensure_ascii=False)}\n\n"

            content_block_index += 1

        # Определяем stop_reason
        stop_reason = "tool_use" if all_tool_calls else "end_turn"

        # 使用统一的 token 计算函数（消除重复代码）
        usage_info = _calculate_usage_tokens(
            full_content, context_usage_percentage, model_cache, model,
            request_messages, request_tools
        )
        input_tokens = usage_info["prompt_tokens"]
        completion_tokens = usage_info["completion_tokens"]

        # Отправляем message_delta
        message_delta = {
            "type": "message_delta",
            "delta": {
                "stop_reason": stop_reason,
                "stop_sequence": None
            },
            "usage": {
                "output_tokens": completion_tokens
            }
        }
        yield f"event: message_delta\ndata: {json.dumps(message_delta, ensure_ascii=False)}\n\n"

        # Отправляем message_stop
        yield f"event: message_stop\ndata: {{\"type\": \"message_stop\"}}\n\n"

        logger.debug(
            f"[Anthropic Usage] {model}: input_tokens={input_tokens}, output_tokens={completion_tokens}"
        )

    except Exception as e:
        # 确保错误信息不为空
        error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
        logger.error(f"Error during Anthropic streaming: {error_msg}", exc_info=True)
        # Отправляем error event
        error_event = {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": error_msg
            }
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    finally:
        await response.aclose()
        logger.debug("Anthropic streaming completed")


async def collect_anthropic_response(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager",
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None,
    stream_read_timeout: float = settings.stream_read_timeout
) -> dict:
    """
    Собирает полный ответ из streaming потока и преобразует в формат Anthropic.

    Args:
        client: HTTP клиент
        response: HTTP ответ с потоком
        model: Имя модели
        model_cache: Кэш моделей
        auth_manager: Менеджер аутентификации
        request_messages: Сообщения запроса
        request_tools: Инструменты запроса
        stream_read_timeout: Stream read timeout for each chunk (seconds)

    Returns:
        Словарь с ответом в формате Anthropic Messages API
    """
    message_id = generate_anthropic_message_id()
    parser = AwsEventStreamParser()
    metering_data = None
    context_usage_percentage = None
    content_parts: list[str] = []  # 使用 list 替代字符串拼接，提升性能

    # 根据模型自适应调整超时时间
    adaptive_stream_read_timeout = get_adaptive_timeout(model, stream_read_timeout)

    try:
        # Read chunks with adaptive timeout
        # 对于慢模型和大文档，可能需要更长时间等待每个 chunk
        byte_iterator = response.aiter_bytes()
        consecutive_timeouts = 0
        max_consecutive_timeouts = 3  # 允许连续超时次数
        while True:
            try:
                chunk = await _read_chunk_with_timeout(byte_iterator, adaptive_stream_read_timeout)
                consecutive_timeouts = 0  # 重置超时计数器
            except StopAsyncIteration:
                break
            except StreamReadTimeoutError as e:
                consecutive_timeouts += 1
                if consecutive_timeouts <= max_consecutive_timeouts:
                    logger.warning(
                        f"Anthropic collect timeout {consecutive_timeouts}/{max_consecutive_timeouts} "
                        f"after {adaptive_stream_read_timeout}s (model: {model}). "
                        f"Model may be processing large content - continuing to wait..."
                    )
                    continue
                else:
                    logger.error(f"Anthropic collect stream read timeout after {max_consecutive_timeouts} consecutive timeouts (model: {model}): {e}")
                    raise

            if debug_logger:
                debug_logger.log_raw_chunk(chunk)

            events = parser.feed(chunk)

            for event in events:
                if event["type"] == "content":
                    content_parts.append(event["data"])
                elif event["type"] == "usage":
                    metering_data = event["data"]
                elif event["type"] == "context_usage":
                    context_usage_percentage = event["data"]

    finally:
        await response.aclose()

    # 合并 content 部分（比字符串拼接更高效）
    full_content = ''.join(content_parts)

    # Обрабатываем tool calls
    bracket_tool_calls = parse_bracket_tool_calls(full_content)
    all_tool_calls = parser.get_tool_calls() + bracket_tool_calls
    all_tool_calls = deduplicate_tool_calls(all_tool_calls)

    # Формируем content blocks
    content_blocks = []

    # Добавляем text block если есть контент
    if full_content:
        content_blocks.append({
            "type": "text",
            "text": full_content
        })

    # Добавляем tool_use blocks
    for tc in all_tool_calls:
        func = tc.get("function") or {}
        tool_name = func.get("name") or ""
        tool_args_str = func.get("arguments") or "{}"
        tool_id = tc.get("id") or f"toolu_{generate_completion_id()[8:]}"

        try:
            tool_input = json.loads(tool_args_str)
        except json.JSONDecodeError:
            tool_input = {}

        content_blocks.append({
            "type": "tool_use",
            "id": tool_id,
            "name": tool_name,
            "input": tool_input
        })

    # Определяем stop_reason
    stop_reason = "tool_use" if all_tool_calls else "end_turn"

    # 使用统一的 token 计算函数（消除重复代码）
    usage_info = _calculate_usage_tokens(
        full_content, context_usage_percentage, model_cache, model,
        request_messages, request_tools
    )
    input_tokens = usage_info["prompt_tokens"]
    completion_tokens = usage_info["completion_tokens"]

    logger.debug(
        f"[Anthropic Usage] {model}: input_tokens={input_tokens}, output_tokens={completion_tokens}"
    )

    return {
        "id": message_id,
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": completion_tokens
        }
    }
