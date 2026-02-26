"""
Custom API 请求处理器
处理自定义 API 的请求和响应流，支持 OpenAI 和 Claude 格式
"""
import json
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional, AsyncIterator, Callable

from kiro_gateway.models import AnthropicMessagesRequest
from kiro_gateway.custom_api.converter import (
    convert_claude_to_openai_request,
    convert_openai_stream_to_claude,
    convert_openai_error_to_claude,
    _clean_claude_request_for_azure,
    _estimate_input_tokens,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0
MAX_RETRIES = 3
BASE_RETRY_DELAY = 5.0
MAX_RETRY_DELAY = 60.0


async def handle_custom_api_request(
    account: Dict[str, Any],
    claude_req: AnthropicMessagesRequest,
    request_data: Dict[str, Any],
    on_success: Optional[Callable] = None,
    on_fail: Optional[Callable] = None,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0
) -> AsyncIterator[str]:
    """
    处理自定义 API 请求的主入口

    根据账号配置的 format 字段决定转换路径：
    - format="openai": 转换为 OpenAI 格式发送，响应转换回 Claude 格式
    - format="claude": 直接透传请求和响应

    Args:
        account: custom_api_accounts 表的一行记录（api_key 已解密）
        claude_req: Claude 请求对象
        request_data: 原始请求数据字典（用于 claude 格式透传）
        on_success: 成功回调，用于 increment_custom_api_success
        on_fail: 失败回调，用于 increment_custom_api_fail
        cache_creation_input_tokens: 缓存创建 token 数
        cache_read_input_tokens: 缓存读取 token 数

    Yields:
        str: Claude 格式的 SSE 事件
    """
    api_format = account.get("format", "openai")
    api_base = account.get("api_base", "")
    model = account.get("model") or claude_req.model
    provider = account.get("provider", "") or ""
    api_key = account.get("api_key", "")
    account_id = account.get("id")

    logger.info(f"Custom API 请求: format={api_format}, provider={provider}, api_base={api_base}, model={model}")

    success = False
    try:
        if api_format == "claude":
            async for event in handle_claude_format_stream(
                api_base=api_base,
                api_key=api_key,
                request_data=request_data,
                account_id=account_id,
                model=claude_req.model,
                provider=provider,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens
            ):
                yield event
        else:
            async for event in handle_openai_format_stream(
                api_base=api_base,
                api_key=api_key,
                model=model,
                claude_req=claude_req,
                account_id=account_id,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens
            ):
                yield event
        success = True
    finally:
        if success and on_success:
            try:
                on_success(account_id)
            except Exception as e:
                logger.error(f"on_success callback failed: {e}")
        elif not success and on_fail:
            try:
                on_fail(account_id)
            except Exception as e:
                logger.error(f"on_fail callback failed: {e}")


async def handle_openai_format_stream(
    api_base: str,
    api_key: str,
    model: str,
    claude_req: AnthropicMessagesRequest,
    account_id: Optional[Any] = None,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0
) -> AsyncIterator[str]:
    """处理 OpenAI 格式的自定义 API 流式响应"""
    openai_request, thinking_enabled = convert_claude_to_openai_request(claude_req, model)

    if thinking_enabled:
        logger.info("Thinking 模式已启用")

    openai_request["stream"] = True
    # Note: stream_options is not supported by all backends (e.g. Bedrock proxies)
    # Only add it for non-Bedrock compatible endpoints if needed

    base = api_base.rstrip('/')
    if not base.endswith('/v1'):
        base = f"{base}/v1"
    api_url = f"{base}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    logger.info(f"发送 OpenAI 格式请求到: {api_url}")
    # Debug: log full request body to diagnose null messages issue
    try:
        import json as _json
        logger.info(f"[custom_api] openai_request messages ({len(openai_request.get('messages', []))} 条):")
        for i, m in enumerate(openai_request.get("messages", [])):
            content_repr = repr(m.get("content"))[:200]
            logger.info(f"  [{i}] role={m.get('role')} content={content_repr}")
        logger.info(f"[custom_api] full request body: {_json.dumps(openai_request, ensure_ascii=False)[:3000]}")
    except Exception as _e:
        logger.warning(f"[custom_api] 无法序列化请求体用于调试: {_e}")
    input_tokens = _estimate_input_tokens(openai_request)

    async def openai_byte_stream() -> AsyncIterator[bytes]:
        retry_count = 0

        while retry_count <= MAX_RETRIES:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                try:
                    async with client.stream("POST", api_url, json=openai_request, headers=headers) as response:
                        if response.status_code == 429:
                            error_text = await response.aread()
                            error_str = error_text.decode() if isinstance(error_text, bytes) else str(error_text)

                            if retry_count < MAX_RETRIES:
                                retry_after = response.headers.get('Retry-After')
                                if retry_after:
                                    try:
                                        delay = min(float(retry_after), MAX_RETRY_DELAY)
                                    except ValueError:
                                        delay = min(BASE_RETRY_DELAY * (2 ** retry_count), MAX_RETRY_DELAY)
                                else:
                                    delay = min(BASE_RETRY_DELAY * (2 ** retry_count), MAX_RETRY_DELAY)

                                retry_count += 1
                                logger.warning(f"Custom API 429，{delay:.1f}秒后重试 ({retry_count}/{MAX_RETRIES})")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                logger.error(f"Custom API 429 重试次数用尽: {error_str}")
                                try:
                                    error_json = json.loads(error_str)
                                except json.JSONDecodeError:
                                    error_json = {"error": {"message": error_str, "type": "rate_limit_error"}}

                                claude_error = convert_openai_error_to_claude(error_json, 429)
                                claude_error["error"]["message"] = "速率限制：请稍后重试。" + claude_error["error"].get("message", "")
                                yield f"event: error\ndata: {json.dumps(claude_error)}\n\n".encode('utf-8')
                                return

                        elif response.status_code != 200:
                            error_text = await response.aread()
                            error_str = error_text.decode() if isinstance(error_text, bytes) else str(error_text)
                            logger.error(f"OpenAI API 错误: {response.status_code} {error_str}")

                            try:
                                error_json = json.loads(error_str)
                            except json.JSONDecodeError:
                                error_json = {"error": {"message": error_str, "type": "api_error"}}

                            claude_error = convert_openai_error_to_claude(error_json, response.status_code)
                            yield f"event: error\ndata: {json.dumps(claude_error)}\n\n".encode('utf-8')
                            return

                        if retry_count > 0:
                            logger.info(f"Custom API 429 重试成功 (第 {retry_count} 次)")
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                yield chunk
                        return

                except httpx.TimeoutException as e:
                    logger.error(f"Custom API 超时: {e}")
                    yield _error_event(f"上游 API 超时: {str(e)}").encode('utf-8')
                    return
                except httpx.ConnectError as e:
                    logger.error(f"Custom API 连接失败: {e}")
                    yield _error_event(f"无法连接到上游 API: {str(e)}").encode('utf-8')
                    return
                except httpx.RequestError as e:
                    logger.error(f"Custom API 请求错误: {e}")
                    yield _error_event(f"上游 API 请求错误: {str(e)}").encode('utf-8')
                    return

    async for claude_event in convert_openai_stream_to_claude(
        openai_byte_stream(),
        model=claude_req.model,
        input_tokens=input_tokens,
        thinking_enabled=thinking_enabled,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens
    ):
        yield claude_event


async def handle_claude_format_stream(
    api_base: str,
    api_key: str,
    request_data: Dict[str, Any],
    account_id: Optional[Any] = None,
    model: str = "claude-sonnet-4.5",
    provider: str = "",
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0
) -> AsyncIterator[str]:
    """处理 Claude 格式的自定义 API 流式响应（透传模式）"""
    if provider == "azure":
        request_data = _clean_claude_request_for_azure(request_data)

    api_url = f"{api_base.rstrip('/')}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    logger.info(f"透传 Claude 格式请求到: {api_url}")

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            async with client.stream("POST", api_url, json=request_data, headers=headers) as response:
                if response.status_code == 429:
                    error_text = await response.aread()
                    error_str = error_text.decode() if isinstance(error_text, bytes) else str(error_text)
                    logger.error(f"Claude API 429 速率限制: {error_str}")
                    yield _error_event("速率限制：请稍后重试", "rate_limit_error")
                    return

                elif response.status_code != 200:
                    error_text = await response.aread()
                    error_str = error_text.decode() if isinstance(error_text, bytes) else str(error_text)
                    logger.error(f"Claude API 错误: {response.status_code} {error_str}")
                    try:
                        error_json = json.loads(error_str)
                        yield f"event: error\ndata: {json.dumps(error_json)}\n\n"
                    except json.JSONDecodeError:
                        yield _error_event(error_str)
                    return

                buffer = ""
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    try:
                        text = chunk.decode('utf-8')
                    except UnicodeDecodeError:
                        logger.warning("Failed to decode chunk as UTF-8")
                        continue

                    buffer += text
                    while '\n\n' in buffer:
                        event_text, buffer = buffer.split('\n\n', 1)
                        if event_text.strip():
                            yield event_text + '\n\n'

                if buffer.strip():
                    yield buffer + '\n\n'

        except httpx.TimeoutException as e:
            logger.error(f"Custom API (Claude format) 超时: {e}")
            yield _error_event(f"上游 API 超时: {str(e)}")
        except httpx.ConnectError as e:
            logger.error(f"Custom API (Claude format) 连接失败: {e}")
            yield _error_event(f"无法连接到上游 API: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"Custom API (Claude format) 请求错误: {e}")
            yield _error_event(f"上游 API 请求错误: {str(e)}")


def _error_event(message: str, error_type: str = "api_error") -> str:
    """构建错误 SSE 事件"""
    payload = {"type": "error", "error": {"type": error_type, "message": message}}
    return f"event: error\ndata: {json.dumps(payload)}\n\n"
