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
请求处理公共函数。

提取 /v1/chat/completions 和 /v1/messages 端点的公共逻辑，
减少代码重复，提高可维护性。
"""

import json
import time
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from kiro_gateway.auth import KiroAuthManager
from kiro_gateway.cache import ModelInfoCache
from kiro_gateway.converters import build_kiro_payload, convert_anthropic_to_openai_request, _is_thinking_enabled
from kiro_gateway.config import settings
from kiro_gateway.http_client import KiroHttpClient
from kiro_gateway.models import (
    ChatCompletionRequest,
    AnthropicMessagesRequest,
)
from kiro_gateway.streaming import (
    stream_kiro_to_openai,
    collect_stream_response,
    stream_kiro_to_anthropic,
    collect_anthropic_response,
)
from kiro_gateway.utils import generate_conversation_id, get_kiro_headers
from kiro_gateway.config import settings, AUTO_CHUNKING_ENABLED, AUTO_CHUNK_THRESHOLD
from kiro_gateway.metrics import metrics


# 导入可选的自动分片处理器
try:
    from kiro_gateway.auto_chunked_handler import process_with_auto_chunking
    auto_chunking_available = True
except ImportError:
    auto_chunking_available = False


# 导入 debug_logger
try:
    from kiro_gateway.debug_logger import debug_logger
except ImportError:
    debug_logger = None


def _assemble_anthropic_response(sse_chunks: list, model: str) -> dict:
    """
    从 SSE 事件块列表中重建 Anthropic non-streaming 响应 JSON。

    解析 message_start、content_block_delta、message_delta 等事件，
    拼装成完整的 /v1/messages 响应格式。
    """
    response = {
        "id": f"msg_{int(time.time())}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }

    text_blocks: dict[int, str] = {}
    thinking_blocks: dict[int, str] = {}
    tool_use_blocks: dict[int, dict] = {}

    for chunk in sse_chunks:
        for line in chunk.splitlines():
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            if etype == "message_start":
                msg = event.get("message", {})
                if "id" in msg:
                    response["id"] = msg["id"]
                if "model" in msg:
                    response["model"] = msg["model"]
                usage = msg.get("usage", {})
                if "input_tokens" in usage:
                    response["usage"]["input_tokens"] = usage["input_tokens"]

            elif etype == "content_block_start":
                idx = event.get("index", 0)
                block = event.get("content_block", {})
                btype = block.get("type", "text")
                if btype == "text":
                    text_blocks[idx] = ""
                elif btype == "thinking":
                    thinking_blocks[idx] = block.get("thinking", "")
                elif btype == "tool_use":
                    tool_use_blocks[idx] = {
                        "type": "tool_use",
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": {},
                        "_input_json": "",
                    }

            elif etype == "content_block_delta":
                idx = event.get("index", 0)
                delta = event.get("delta", {})
                dtype = delta.get("type", "")
                if dtype == "text_delta" and idx in text_blocks:
                    text_blocks[idx] += delta.get("text", "")
                elif dtype == "thinking_delta" and idx in thinking_blocks:
                    thinking_blocks[idx] += delta.get("thinking", "")
                elif dtype == "input_json_delta" and idx in tool_use_blocks:
                    tool_use_blocks[idx]["_input_json"] += delta.get("partial_json", "")

            elif etype == "message_delta":
                delta = event.get("delta", {})
                if "stop_reason" in delta:
                    response["stop_reason"] = delta["stop_reason"]
                if "stop_sequence" in delta:
                    response["stop_sequence"] = delta["stop_sequence"]
                usage = event.get("usage", {})
                if "output_tokens" in usage:
                    response["usage"]["output_tokens"] = usage["output_tokens"]

    # 按 index 顺序组装 content 块
    all_indices = sorted(
        set(list(text_blocks.keys()) + list(thinking_blocks.keys()) + list(tool_use_blocks.keys()))
    )
    for idx in all_indices:
        if idx in thinking_blocks:
            response["content"].append({"type": "thinking", "thinking": thinking_blocks[idx]})
        if idx in text_blocks:
            response["content"].append({"type": "text", "text": text_blocks[idx]})
        if idx in tool_use_blocks:
            block = tool_use_blocks[idx]
            try:
                input_data = json.loads(block["_input_json"]) if block["_input_json"] else {}
            except json.JSONDecodeError:
                input_data = {}
            response["content"].append({
                "type": "tool_use",
                "id": block["id"],
                "name": block["name"],
                "input": input_data,
            })

    return response


class RequestHandler:
    """
    请求处理器基类，封装公共逻辑。
    """

    @staticmethod
    def prepare_request_logging(request_data: Union[ChatCompletionRequest, AnthropicMessagesRequest]) -> None:
        """
        准备请求日志记录。

        Args:
            request_data: 请求数据
        """
        if debug_logger:
            debug_logger.prepare_new_request()

        try:
            request_body = json.dumps(request_data.model_dump(), ensure_ascii=False, indent=2).encode('utf-8')
            if debug_logger:
                debug_logger.log_request_body(request_body)
        except Exception as e:
            logger.warning(f"Failed to log request body: {e}")

    @staticmethod
    def log_kiro_request(kiro_payload: dict) -> None:
        """
        记录 Kiro 请求。

        Args:
            kiro_payload: Kiro 请求 payload
        """
        try:
            kiro_request_body = json.dumps(kiro_payload, ensure_ascii=False, indent=2).encode('utf-8')
            if debug_logger:
                debug_logger.log_kiro_request_body(kiro_request_body)
        except Exception as e:
            logger.warning(f"Failed to log Kiro request: {e}")

    @staticmethod
    async def handle_api_error(
        response,
        http_client: KiroHttpClient,
        endpoint_name: str,
        error_format: str = "openai",
        request: Optional[Request] = None
    ) -> JSONResponse:
        """
        处理 API 错误。

        Args:
            response: HTTP 响应
            http_client: HTTP 客户端
            endpoint_name: 端点名称（用于日志）
            error_format: 错误格式（"openai" 或 "anthropic"）

        Returns:
            JSONResponse 错误响应
        """
        try:
            error_content = await response.aread()
        except Exception:
            error_content = "未知错误".encode("utf-8")
        finally:
            try:
                await response.aclose()
            except Exception:
                pass

        await http_client.close()
        error_text = error_content.decode('utf-8', errors='replace')
        logger.error(f"Error from Kiro API: {response.status_code} - {error_text}")

        # 尝试解析 JSON 错误响应
        error_message = error_text
        error_reason = None
        try:
            error_json = json.loads(error_text)
            if isinstance(error_json, dict):
                if "reason" in error_json:
                    error_reason = str(error_json["reason"])
                if "message" in error_json:
                    error_message = error_json["message"]
                elif "error" in error_json and isinstance(error_json["error"], dict):
                    if "message" in error_json["error"]:
                        error_message = error_json["error"]["message"]
                    if not error_reason and "reason" in error_json["error"]:
                        error_reason = str(error_json["error"]["reason"])
                if error_reason:
                    error_message = f"{error_message} (reason: {error_reason})"
        except (json.JSONDecodeError, KeyError):
            pass

        logger.warning(f"HTTP {response.status_code} - POST {endpoint_name} - {error_message[:100]}")

        if debug_logger:
            debug_logger.flush_on_error(response.status_code, error_message)

        if request and hasattr(request.state, "donated_token_id"):
            reason_text = error_reason or error_message
            if "MONTHLY_REQUEST_COUNT" in reason_text:
                try:
                    from kiro_gateway.database import user_db
                    token_id = request.state.donated_token_id
                    user_db.set_token_status(token_id, "expired")
                    logger.warning(f"Token {token_id} marked expired due to monthly limit")
                except Exception as e:
                    logger.warning(f"Failed to mark token expired: {e}")

        # 上下文窗口满 / 输入过长 → 返回 400 invalid_request_error（不应重试）
        combined_error = (error_reason or "") + error_message
        if "CONTENT_LENGTH_EXCEEDS_THRESHOLD" in combined_error:
            if error_format == "anthropic":
                return JSONResponse(
                    status_code=400,
                    content={"type": "error", "error": {"type": "invalid_request_error", "message": "Context window is full. Reduce conversation history, system prompt, or tools."}}
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": {"message": "Context window is full. Reduce conversation history, system prompt, or tools.", "type": "invalid_request_error", "code": 400}}
                )
        if "Input is too long" in combined_error:
            if error_format == "anthropic":
                return JSONResponse(
                    status_code=400,
                    content={"type": "error", "error": {"type": "invalid_request_error", "message": "Input is too long. Reduce the size of your messages."}}
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": {"message": "Input is too long. Reduce the size of your messages.", "type": "invalid_request_error", "code": 400}}
                )

        # 根据格式返回错误
        if error_format == "anthropic":
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": error_message
                    }
                }
            )
        else:
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "error": {
                        "message": error_message,
                        "type": "kiro_api_error",
                        "code": response.status_code
                    }
                }
            )

    @staticmethod
    def log_success(endpoint_name: str, is_streaming: bool = False) -> None:
        """
        记录成功日志。

        Args:
            endpoint_name: 端点名称
            is_streaming: 是否为流式响应
        """
        mode = "streaming" if is_streaming else "non-streaming"
        logger.info(f"HTTP 200 - POST {endpoint_name} ({mode}) - completed")

    @staticmethod
    def log_error(endpoint_name: str, error: Union[str, Exception], status_code: int = 500) -> None:
        """
        记录错误日志。

        Args:
            endpoint_name: 端点名称
            error: 错误信息
            status_code: HTTP 状态码
        """
        if isinstance(error, Exception):
            error_msg = str(error) if str(error) else f"{type(error).__name__}: {repr(error)}"
        else:
            error_msg = error
        logger.error(f"HTTP {status_code} - POST {endpoint_name} - {error_msg[:100]}")

    @staticmethod
    def handle_streaming_error(error: Exception, endpoint_name: str) -> str:
        """
        处理流式错误，确保错误信息不为空。

        Args:
            error: 异常
            endpoint_name: 端点名称

        Returns:
            错误信息字符串
        """
        error_msg = str(error) if str(error) else f"{type(error).__name__}: {repr(error)}"
        RequestHandler.log_error(endpoint_name, error_msg, 500)
        return error_msg

    @staticmethod
    def prepare_tokenizer_data(request_data: ChatCompletionRequest) -> tuple:
        """
        准备用于 token 计数的数据。

        Args:
            request_data: 请求数据

        Returns:
            (messages_for_tokenizer, tools_for_tokenizer)
        """
        messages_for_tokenizer = [msg.model_dump() for msg in request_data.messages]
        tools_for_tokenizer = [tool.model_dump() for tool in request_data.tools] if request_data.tools else None
        return messages_for_tokenizer, tools_for_tokenizer

    @staticmethod
    async def create_stream_response(
        http_client: KiroHttpClient,
        response,
        model: str,
        model_cache: ModelInfoCache,
        auth_manager: KiroAuthManager,
        stream_func: Callable,
        endpoint_name: str,
        messages_for_tokenizer: Optional[List] = None,
        tools_for_tokenizer: Optional[List] = None,
        **kwargs
    ) -> StreamingResponse:
        """
        创建流式响应。

        Args:
            http_client: HTTP 客户端
            response: Kiro API 响应
            model: 模型名称
            model_cache: 模型缓存
            auth_manager: 认证管理器
            stream_func: 流式处理函数
            endpoint_name: 端点名称
            messages_for_tokenizer: 消息数据（用于 token 计数）
            tools_for_tokenizer: 工具数据（用于 token 计数）
            **kwargs: 其他参数

        Returns:
            StreamingResponse
        """
        async def stream_wrapper():
            streaming_error = None
            try:
                async for chunk in stream_func(
                    http_client.client,
                    response,
                    model,
                    model_cache,
                    auth_manager,
                    request_messages=messages_for_tokenizer,
                    request_tools=tools_for_tokenizer,
                    **kwargs
                ):
                    yield chunk
            except Exception as e:
                streaming_error = e
                raise
            finally:
                await http_client.close()
                if streaming_error:
                    RequestHandler.handle_streaming_error(streaming_error, endpoint_name)
                else:
                    RequestHandler.log_success(endpoint_name, is_streaming=True)
                if debug_logger:
                    if streaming_error:
                        error_msg = RequestHandler.handle_streaming_error(streaming_error, endpoint_name)
                        debug_logger.flush_on_error(500, error_msg)
                    else:
                        debug_logger.discard_buffers()

        return StreamingResponse(stream_wrapper(), media_type="text/event-stream")

    @staticmethod
    def should_enable_auto_chunking(messages: List) -> bool:
        """
        检查是否应该启用自动分片功能。

        Args:
            messages: 消息列表

        Returns:
            是否启用自动分片
        """
        if not AUTO_CHUNKING_ENABLED or not auto_chunking_available:
            return False

        # 检查消息内容是否超过阈值
        total_chars = 0
        for msg in messages:
            if hasattr(msg, 'content'):
                content = msg.content
            elif isinstance(msg, dict):
                content = msg.get("content", "")
            else:
                continue

            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total_chars += len(block.get("text", ""))

        return total_chars > AUTO_CHUNK_THRESHOLD

    @staticmethod
    async def create_non_stream_response(
        http_client: KiroHttpClient,
        response,
        model: str,
        model_cache: ModelInfoCache,
        auth_manager: KiroAuthManager,
        collect_func: Callable,
        endpoint_name: str,
        messages_for_tokenizer: Optional[List] = None,
        tools_for_tokenizer: Optional[List] = None,
        **kwargs
    ) -> JSONResponse:
        """
        创建非流式响应。

        Args:
            http_client: HTTP 客户端
            response: Kiro API 响应
            model: 模型名称
            model_cache: 模型缓存
            auth_manager: 认证管理器
            collect_func: 收集响应函数
            endpoint_name: 端点名称
            messages_for_tokenizer: 消息数据（用于 token 计数）
            tools_for_tokenizer: 工具数据（用于 token 计数）
            **kwargs: 其他参数

        Returns:
            JSONResponse
        """
        collected_response = await collect_func(
            http_client.client,
            response,
            model,
            model_cache,
            auth_manager,
            request_messages=messages_for_tokenizer,
            request_tools=tools_for_tokenizer,
            **kwargs
        )

        await http_client.close()
        RequestHandler.log_success(endpoint_name, is_streaming=False)

        if debug_logger:
            debug_logger.discard_buffers()

        return JSONResponse(content=collected_response)

    @staticmethod
    async def _handle_custom_api(
        request: Request,
        request_data: Union[ChatCompletionRequest, AnthropicMessagesRequest],
        account: dict,
        response_format: str,
        endpoint_name: str,
    ) -> Union[StreamingResponse, JSONResponse]:
        """
        将请求路由到 Custom API 账号。

        Args:
            request: FastAPI Request
            request_data: 请求数据（AnthropicMessagesRequest）
            account: custom_api_accounts 记录（api_key 已解密）
            response_format: 响应格式（"openai" 或 "anthropic"）
            endpoint_name: 端点名称（用于日志）

        Returns:
            StreamingResponse 或 JSONResponse
        """
        from kiro_gateway.custom_api.handler import handle_custom_api_request
        from kiro_gateway.database import user_db

        # 将请求转换为 AnthropicMessagesRequest（如果还不是的话）
        if isinstance(request_data, ChatCompletionRequest):
            from kiro_gateway.converters import convert_anthropic_to_openai_request
            # ChatCompletionRequest 已经是 OpenAI 格式，需要先转为 Anthropic
            # 但 process_request 在 convert_to_openai=True 时才会转换
            # 这里 request_data 应该已经是 AnthropicMessagesRequest
            logger.warning("Custom API 路径收到 ChatCompletionRequest，预期 AnthropicMessagesRequest")

        # 构建原始请求 dict（供 format=claude 透传使用）
        raw_request_data = request_data.model_dump(exclude_none=True)

        account_id = account.get("id")

        def on_success(aid):
            try:
                user_db.increment_custom_api_success(aid)
            except Exception as e:
                logger.error(f"increment_custom_api_success 失败: {e}")

        def on_fail(aid):
            try:
                user_db.increment_custom_api_fail(aid)
            except Exception as e:
                logger.error(f"increment_custom_api_fail 失败: {e}")

        logger.info(
            f"Custom API 路由: 账号 {account_id}, format={account.get('format')}, "
            f"provider={account.get('provider')}, endpoint={endpoint_name}"
        )

        if request_data.stream:
            async def stream_wrapper():
                try:
                    async for chunk in handle_custom_api_request(
                        account=account,
                        claude_req=request_data,
                        request_data=raw_request_data,
                        on_success=on_success,
                        on_fail=on_fail,
                    ):
                        yield chunk
                except Exception as e:
                    error_msg = str(e) if str(e) else repr(e)
                    logger.error(f"Custom API 流式错误: {error_msg}")
                    on_fail(account_id)

            return StreamingResponse(stream_wrapper(), media_type="text/event-stream")
        else:
            # 非流式：收集所有 SSE 事件，拼装成完整响应
            # 强制 stream=True 向上游请求，然后在本地收集
            import copy
            streaming_request = copy.copy(request_data)
            streaming_request.stream = True
            raw_streaming = streaming_request.model_dump(exclude_none=True)

            chunks = []
            try:
                async for chunk in handle_custom_api_request(
                    account=account,
                    claude_req=streaming_request,
                    request_data=raw_streaming,
                    on_success=on_success,
                    on_fail=on_fail,
                ):
                    chunks.append(chunk)
            except Exception as e:
                error_msg = str(e) if str(e) else repr(e)
                logger.error(f"Custom API 非流式错误: {error_msg}")
                if response_format == "anthropic":
                    return JSONResponse(
                        status_code=502,
                        content={"type": "error", "error": {"type": "api_error", "message": error_msg}}
                    )
                else:
                    return JSONResponse(
                        status_code=502,
                        content={"error": {"message": error_msg, "type": "api_error", "code": 502}}
                    )

            # 从 SSE 事件流中提取最终的 message_stop 或 content
            # 返回原始 SSE 内容拼接（客户端期望非流式时返回完整 JSON）
            # 解析 SSE 流，重建 Anthropic non-streaming 响应
            assembled = _assemble_anthropic_response(chunks, request_data.model)
            return JSONResponse(content=assembled)

    @staticmethod
    async def process_request(
        request: Request,
        request_data: Union[ChatCompletionRequest, AnthropicMessagesRequest],
        endpoint_name: str,
        convert_to_openai: bool = False,
        response_format: str = "openai",
        buffered_mode: bool = False
    ) -> Union[StreamingResponse, JSONResponse]:
        """
        处理请求的核心逻辑。

        Args:
            request: FastAPI Request
            request_data: 请求数据
            endpoint_name: 端点名称
            convert_to_openai: 是否需要将 Anthropic 请求转换为 OpenAI 格式
            response_format: 响应格式（"openai" 或 "anthropic"）
            buffered_mode: 是否启用缓冲模式（仅对 Anthropic 流式响应有效）

        Returns:
            StreamingResponse 或 JSONResponse
        """
        start_time = time.time()
        api_type = "anthropic" if response_format == "anthropic" else "openai"

        # Check if we need deferred token selection (user API key mode)
        needs_token_selection = getattr(request.state, 'needs_token_selection', False)
        user_id = getattr(request.state, 'user_id', None)
        
        if needs_token_selection and user_id:
            # Deferred token selection based on model
            from kiro_gateway.token_allocator import token_allocator, NoTokenAvailable
            try:
                account_type, account_data, auth_manager = await token_allocator.get_best_token(
                    user_id=user_id,
                    model=request_data.model
                )
            except NoTokenAvailable as e:
                logger.warning(f"用户可用 Token 不足: 用户ID={user_id}, 模型={request_data.model}, 错误={e}")
                raise HTTPException(status_code=503, detail="该用户暂无可用的 Token")

            if account_type == 'custom_api':
                # Route to Custom API
                return await RequestHandler._handle_custom_api(
                    request, request_data, account_data, response_format, endpoint_name
                )

            # Kiro token path
            request.state.auth_manager = auth_manager
            request.state.donated_token_id = account_data.id
            logger.info(f"延迟 Token 选择: 用户 {user_id}, 模型 {request_data.model}, Token {account_data.id}")

        # Use auth_manager from request.state if available (multi-tenant mode)
        # Otherwise fall back to global auth_manager
        auth_manager: KiroAuthManager = getattr(request.state, 'auth_manager', None) or request.app.state.auth_manager
        model_cache: ModelInfoCache = request.app.state.model_cache

        # 准备日志
        RequestHandler.prepare_request_logging(request_data)

        # 如果需要，转换 Anthropic 请求为 OpenAI 格式
        if convert_to_openai:
            try:
                openai_request = convert_anthropic_to_openai_request(request_data)
            except Exception as e:
                logger.error(f"Failed to convert Anthropic request: {e}")
                raise HTTPException(status_code=400, detail=f"请求格式无效: {str(e)}")
        else:
            openai_request = request_data

        # 生成会话 ID
        conversation_id = generate_conversation_id()

        # 检测是否启用 Extended Thinking
        thinking_param = getattr(request_data, 'thinking', None)
        thinking_enabled = _is_thinking_enabled(thinking_param)
        
        # 获取 profile_arn
        profile_arn = auth_manager.profile_arn or ""
        
        # 构建 Kiro payload
        try:
            kiro_payload = build_kiro_payload(
                openai_request,
                conversation_id,
                profile_arn,
                thinking_enabled=thinking_enabled
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 记录 Kiro 请求
        RequestHandler.log_kiro_request(kiro_payload)

        # 创建 HTTP 客户端
        http_client = KiroHttpClient(auth_manager)
        url = f"{auth_manager.api_host}/generateAssistantResponse"

        try:
            # 发送请求到 Kiro API
            response = await http_client.request_with_retry(
                "POST",
                url,
                kiro_payload,
                stream=True,
                model=request_data.model
            )

            if response.status_code != 200:
                duration_ms = (time.time() - start_time) * 1000
                metrics.record_request(
                    endpoint=endpoint_name,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    model=request_data.model,
                    is_stream=request_data.stream,
                    api_type=api_type
                )
                return await RequestHandler.handle_api_error(
                    response,
                    http_client,
                    endpoint_name,
                    response_format,
                    request=request
                )

            # 准备 token 计数数据
            messages_for_tokenizer, tools_for_tokenizer = RequestHandler.prepare_tokenizer_data(openai_request)

            # 记录成功请求
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_request(
                endpoint=endpoint_name,
                status_code=200,
                duration_ms=duration_ms,
                model=request_data.model,
                is_stream=request_data.stream,
                api_type=api_type
            )

            # 根据请求类型和响应格式处理
            if request_data.stream:
                if response_format == "anthropic":
                    # 如果启用缓冲模式，使用缓冲流处理器
                    if buffered_mode:
                        from kiro_gateway.buffered_streaming import stream_kiro_to_anthropic_buffered
                        return await RequestHandler.create_stream_response(
                            http_client,
                            response,
                            request_data.model,
                            model_cache,
                            auth_manager,
                            stream_kiro_to_anthropic_buffered,
                            endpoint_name,
                            messages_for_tokenizer,
                            tools_for_tokenizer,
                            thinking_enabled=thinking_enabled
                        )
                    else:
                        return await RequestHandler.create_stream_response(
                            http_client,
                            response,
                            request_data.model,
                            model_cache,
                            auth_manager,
                            stream_kiro_to_anthropic,
                            endpoint_name,
                            messages_for_tokenizer,
                            tools_for_tokenizer,
                            thinking_enabled=thinking_enabled  # 使用已计算的 thinking_enabled
                        )
                else:
                    return await RequestHandler.create_stream_response(
                        http_client,
                        response,
                        request_data.model,
                        model_cache,
                        auth_manager,
                        stream_kiro_to_openai,
                        endpoint_name,
                        messages_for_tokenizer,
                        tools_for_tokenizer,
                        thinking_enabled=thinking_enabled
                    )
            else:
                if response_format == "anthropic":
                    return await RequestHandler.create_non_stream_response(
                        http_client,
                        response,
                        request_data.model,
                        model_cache,
                        auth_manager,
                        collect_anthropic_response,
                        endpoint_name,
                        messages_for_tokenizer,
                        tools_for_tokenizer
                    )
                else:
                    return await RequestHandler.create_non_stream_response(
                        http_client,
                        response,
                        request_data.model,
                        model_cache,
                        auth_manager,
                        collect_stream_response,
                        endpoint_name,
                        messages_for_tokenizer,
                        tools_for_tokenizer,
                        thinking_enabled=thinking_enabled
                    )

        except HTTPException as e:
            await http_client.close()
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_request(
                endpoint=endpoint_name,
                status_code=e.status_code,
                duration_ms=duration_ms,
                model=request_data.model,
                is_stream=request_data.stream,
                api_type=api_type
            )
            RequestHandler.log_error(endpoint_name, e.detail, e.status_code)
            if debug_logger:
                debug_logger.flush_on_error(e.status_code, str(e.detail))
            raise
        except Exception as e:
            await http_client.close()
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_request(
                endpoint=endpoint_name,
                status_code=500,
                duration_ms=duration_ms,
                model=request_data.model,
                is_stream=request_data.stream,
                api_type=api_type
            )
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Internal error: {error_msg}", exc_info=True)
            RequestHandler.log_error(endpoint_name, error_msg, 500)
            if debug_logger:
                debug_logger.flush_on_error(500, error_msg)
            if settings.debug_mode == "off":
                detail = "服务器内部错误"
            else:
                detail = f"服务器内部错误: {error_msg}"
            raise HTTPException(status_code=500, detail=detail)
