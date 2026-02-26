"""
Custom API 格式转换器
- 将 Claude API 格式转换为 OpenAI API 格式 (请求)
- 将 OpenAI API 格式转换为 Claude API 格式 (响应)
"""
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Union, AsyncIterator, Tuple

from kiro_gateway.models import AnthropicMessagesRequest, AnthropicTool

logger = logging.getLogger(__name__)

# Thinking 模式相关常量
THINKING_START_TAG = "<thinking>"
THINKING_END_TAG = "</thinking>"
THINKING_HINT = "<thinking_mode>interleaved</thinking_mode><max_thinking_length>16000</max_thinking_length>"


# ============================================================================
# OpenAI → Claude 响应转换
# ============================================================================

class OpenAIStreamState:
    """OpenAI 流式响应状态管理"""

    def __init__(self, model: str = "claude-sonnet-4.5", request_id: Optional[str] = None, thinking_enabled: bool = False):
        self.model = model
        self.request_id = request_id or f"msg_{uuid.uuid4().hex[:24]}"
        self.content_block_index = -1
        self.current_tool_call_index = -1
        self.tool_calls: Dict[int, Dict[str, Any]] = {}
        self.message_started = False
        self.content_block_started = False
        self.input_tokens = 0
        self.output_tokens = 0
        self.finish_reason: Optional[str] = None
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0
        self.thinking_enabled = thinking_enabled
        self.in_thinking_block = False
        self.thinking_buffer = ""
        self.current_block_type: Optional[str] = None  # "text" or "thinking"


async def convert_openai_stream_to_claude(
    openai_stream: AsyncIterator[bytes],
    model: str = "claude-sonnet-4.5",
    input_tokens: int = 0,
    thinking_enabled: bool = False,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0
) -> AsyncIterator[str]:
    """将 OpenAI SSE 流转换为 Claude SSE 流"""
    state = OpenAIStreamState(model=model, thinking_enabled=thinking_enabled)
    state.input_tokens = input_tokens
    state.cache_creation_input_tokens = cache_creation_input_tokens
    state.cache_read_input_tokens = cache_read_input_tokens
    buffer = ""

    try:
        async for chunk in openai_stream:
            try:
                text = chunk.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning("Failed to decode chunk as UTF-8")
                continue

            buffer += text

            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()

                if not line or line.startswith(':'):
                    continue

                if line.startswith('data:'):
                    data_str = line[5:].strip()

                    if data_str == '[DONE]':
                        if state.content_block_started:
                            yield _build_content_block_stop(state.content_block_index)
                            state.content_block_started = False

                        yield _build_message_stop(
                            state.input_tokens,
                            state.output_tokens,
                            state.finish_reason,
                            state.cache_creation_input_tokens,
                            state.cache_read_input_tokens
                        )
                        return

                    try:
                        openai_event = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse OpenAI event: {data_str}")
                        continue

                    for claude_event in convert_openai_delta_to_claude_events(openai_event, state):
                        yield claude_event

        if buffer.strip():
            line = buffer.strip()
            if line.startswith('data:'):
                data_str = line[5:].strip()
                if data_str != '[DONE]':
                    try:
                        openai_event = json.loads(data_str)
                        for claude_event in convert_openai_delta_to_claude_events(openai_event, state):
                            yield claude_event
                    except json.JSONDecodeError:
                        pass

        if state.content_block_started:
            yield _build_content_block_stop(state.content_block_index)

        if state.message_started:
            yield _build_message_stop(
                state.input_tokens,
                state.output_tokens,
                state.finish_reason,
                state.cache_creation_input_tokens,
                state.cache_read_input_tokens
            )

    except Exception as e:
        logger.error(f"Error converting OpenAI stream: {e}", exc_info=True)
        raise


def convert_openai_delta_to_claude_events(
    openai_event: Dict[str, Any],
    state: OpenAIStreamState
) -> List[str]:
    """将 OpenAI delta 事件转换为 Claude SSE 事件列表"""
    events: List[str] = []

    if not state.message_started:
        events.append(_build_message_start(
            state.request_id,
            state.model,
            state.input_tokens,
            state.cache_creation_input_tokens,
            state.cache_read_input_tokens
        ))
        events.append(_build_ping())
        state.message_started = True

    choices = openai_event.get('choices', [])
    if not choices:
        usage = openai_event.get('usage')
        if usage:
            claude_usage = convert_openai_usage_to_claude(usage)
            state.input_tokens = claude_usage.get('input_tokens', state.input_tokens)
            state.output_tokens = claude_usage.get('output_tokens', state.output_tokens)
        return events

    choice = choices[0]
    delta = choice.get('delta', {})
    finish_reason = choice.get('finish_reason')

    if finish_reason:
        state.finish_reason = _convert_finish_reason(finish_reason)

    content = delta.get('content')
    if content:
        if state.current_tool_call_index >= 0 and state.content_block_started:
            events.append(_build_content_block_stop(state.content_block_index))
            state.content_block_started = False
            state.current_tool_call_index = -1

        if state.thinking_enabled:
            thinking_events = _process_thinking_content(content, state)
            events.extend(thinking_events)
        else:
            if not state.content_block_started or state.current_tool_call_index >= 0:
                state.content_block_index += 1
                events.append(_build_content_block_start(state.content_block_index, "text"))
                state.content_block_started = True
                state.current_tool_call_index = -1
                state.current_block_type = "text"

            events.append(_build_text_delta(state.content_block_index, content))

    tool_calls = delta.get('tool_calls', [])
    for tc in tool_calls:
        tc_index = tc.get('index', 0)
        tc_id = tc.get('id')
        tc_function = tc.get('function', {})
        tc_name = tc_function.get('name')
        tc_arguments = tc_function.get('arguments', '')

        if tc_id or tc_name:
            if state.content_block_started:
                events.append(_build_content_block_stop(state.content_block_index))
                state.content_block_started = False

            state.content_block_index += 1
            state.current_tool_call_index = tc_index

            tool_use_id = tc_id or f"toolu_{uuid.uuid4().hex[:24]}"
            state.tool_calls[tc_index] = {
                'id': tool_use_id,
                'name': tc_name or '',
                'arguments': ''
            }

            events.append(_build_tool_use_start(
                state.content_block_index,
                tool_use_id,
                tc_name or ''
            ))
            state.content_block_started = True

        if tc_arguments and tc_index in state.tool_calls:
            state.tool_calls[tc_index]['arguments'] += tc_arguments
            events.append(_build_tool_use_delta(state.content_block_index, tc_arguments))

    usage = openai_event.get('usage')
    if usage:
        claude_usage = convert_openai_usage_to_claude(usage)
        state.input_tokens = claude_usage.get('input_tokens', state.input_tokens)
        state.output_tokens = claude_usage.get('output_tokens', state.output_tokens)

    return events


def convert_openai_usage_to_claude(openai_usage: Dict[str, Any]) -> Dict[str, int]:
    """将 OpenAI usage 转换为 Claude usage 格式"""
    return {
        "input_tokens": openai_usage.get("prompt_tokens", 0),
        "output_tokens": openai_usage.get("completion_tokens", 0)
    }


def convert_openai_error_to_claude(
    openai_error: Dict[str, Any],
    status_code: int = 500
) -> Dict[str, Any]:
    """将 OpenAI 错误格式转换为 Claude 错误格式"""
    error_data = openai_error.get('error', {})
    openai_type = error_data.get('type', '')
    openai_code = error_data.get('code', '')
    message = error_data.get('message', 'Unknown error')

    error_type_map = {
        'invalid_request_error': 'invalid_request_error',
        'authentication_error': 'authentication_error',
        'permission_error': 'permission_error',
        'not_found_error': 'not_found_error',
        'rate_limit_error': 'rate_limit_error',
        'server_error': 'api_error',
        'service_unavailable': 'overloaded_error',
    }

    status_type_map = {
        400: 'invalid_request_error',
        401: 'authentication_error',
        403: 'permission_error',
        404: 'not_found_error',
        429: 'rate_limit_error',
        500: 'api_error',
        502: 'api_error',
        503: 'overloaded_error',
    }

    claude_type = error_type_map.get(openai_type) or \
                  error_type_map.get(openai_code) or \
                  status_type_map.get(status_code, 'api_error')

    return {
        "type": "error",
        "error": {
            "type": claude_type,
            "message": message
        }
    }


# ============================================================================
# Claude SSE 事件构建辅助函数
# ============================================================================

def _build_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _build_message_start(
    request_id: str,
    model: str,
    input_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0
) -> str:
    data = {
        "type": "message_start",
        "message": {
            "id": request_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": 0,
                "cache_creation_input_tokens": cache_creation_input_tokens,
                "cache_read_input_tokens": cache_read_input_tokens
            }
        }
    }
    return _build_sse_event("message_start", data)


def _build_ping() -> str:
    return _build_sse_event("ping", {"type": "ping"})


def _build_content_block_start(index: int, content_type: str) -> str:
    data = {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": content_type, content_type: ""}
    }
    return _build_sse_event("content_block_start", data)


def _build_text_delta(index: int, text: str) -> str:
    data = {
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": text}
    }
    return _build_sse_event("content_block_delta", data)


def _build_content_block_stop(index: int) -> str:
    return _build_sse_event("content_block_stop", {"type": "content_block_stop", "index": index})


def _build_tool_use_start(index: int, tool_use_id: str, name: str) -> str:
    data = {
        "type": "content_block_start",
        "index": index,
        "content_block": {
            "type": "tool_use",
            "id": tool_use_id,
            "name": name
        }
    }
    return _build_sse_event("content_block_start", data)


def _build_tool_use_delta(index: int, partial_json: str) -> str:
    data = {
        "type": "content_block_delta",
        "index": index,
        "delta": {
            "type": "input_json_delta",
            "partial_json": partial_json
        }
    }
    return _build_sse_event("content_block_delta", data)


def _build_message_stop(
    input_tokens: int,
    output_tokens: int,
    stop_reason: Optional[str],
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0
) -> str:
    delta_data = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason or "end_turn", "stop_sequence": None},
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens
        }
    }
    delta_event = _build_sse_event("message_delta", delta_data)
    stop_event = _build_sse_event("message_stop", {"type": "message_stop"})
    return delta_event + stop_event


def _convert_finish_reason(openai_reason: str) -> str:
    reason_map = {
        'stop': 'end_turn',
        'length': 'max_tokens',
        'tool_calls': 'tool_use',
        'content_filter': 'end_turn',
        'function_call': 'tool_use',
    }
    return reason_map.get(openai_reason, 'end_turn')


def _build_thinking_start(index: int) -> str:
    data = {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "thinking", "thinking": ""}
    }
    return _build_sse_event("content_block_start", data)


def _build_thinking_delta(index: int, thinking: str) -> str:
    data = {
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "thinking_delta", "thinking": thinking}
    }
    return _build_sse_event("content_block_delta", data)


def _process_thinking_content(content: str, state: OpenAIStreamState) -> List[str]:
    """处理可能包含 <thinking> 标签的内容，转换为 Claude thinking 内容块"""
    events: List[str] = []
    state.thinking_buffer += content

    while True:
        if state.in_thinking_block:
            end_idx = state.thinking_buffer.find(THINKING_END_TAG)
            if end_idx != -1:
                thinking_content = state.thinking_buffer[:end_idx]
                state.thinking_buffer = state.thinking_buffer[end_idx + len(THINKING_END_TAG):]

                if thinking_content:
                    events.append(_build_thinking_delta(state.content_block_index, thinking_content))

                events.append(_build_content_block_stop(state.content_block_index))
                state.content_block_started = False
                state.in_thinking_block = False
                state.current_block_type = None
            else:
                if state.thinking_buffer:
                    events.append(_build_thinking_delta(state.content_block_index, state.thinking_buffer))
                    state.thinking_buffer = ""
                break
        else:
            start_idx = state.thinking_buffer.find(THINKING_START_TAG)
            if start_idx != -1:
                text_before = state.thinking_buffer[:start_idx]
                state.thinking_buffer = state.thinking_buffer[start_idx + len(THINKING_START_TAG):]

                if text_before:
                    if not state.content_block_started or state.current_block_type != "text":
                        if state.content_block_started:
                            events.append(_build_content_block_stop(state.content_block_index))
                        state.content_block_index += 1
                        events.append(_build_content_block_start(state.content_block_index, "text"))
                        state.content_block_started = True
                        state.current_block_type = "text"
                    events.append(_build_text_delta(state.content_block_index, text_before))

                if state.content_block_started and state.current_block_type == "text":
                    events.append(_build_content_block_stop(state.content_block_index))
                    state.content_block_started = False

                state.content_block_index += 1
                events.append(_build_thinking_start(state.content_block_index))
                state.content_block_started = True
                state.in_thinking_block = True
                state.current_block_type = "thinking"
            else:
                potential_tag_start = -1
                for i in range(1, len(THINKING_START_TAG)):
                    if state.thinking_buffer.endswith(THINKING_START_TAG[:i]):
                        potential_tag_start = len(state.thinking_buffer) - i
                        break

                if potential_tag_start >= 0:
                    text_to_send = state.thinking_buffer[:potential_tag_start]
                    state.thinking_buffer = state.thinking_buffer[potential_tag_start:]
                else:
                    text_to_send = state.thinking_buffer
                    state.thinking_buffer = ""

                if text_to_send:
                    if not state.content_block_started or state.current_block_type != "text":
                        if state.content_block_started:
                            events.append(_build_content_block_stop(state.content_block_index))
                        state.content_block_index += 1
                        events.append(_build_content_block_start(state.content_block_index, "text"))
                        state.content_block_started = True
                        state.current_block_type = "text"
                    events.append(_build_text_delta(state.content_block_index, text_to_send))
                break

    return events


# ============================================================================
# Claude → OpenAI 请求转换
# ============================================================================

def convert_claude_to_openai_request(
    claude_req: AnthropicMessagesRequest,
    model: str
) -> Tuple[Dict[str, Any], bool]:
    """
    将 Claude API 请求转换为 OpenAI chat completion 格式

    Returns:
        Tuple[Dict[str, Any], bool]: (OpenAI 请求字典, thinking_enabled)
    """
    openai_request: Dict[str, Any] = {
        "model": model,
        "messages": [],
        "stream": claude_req.stream,
    }

    thinking_enabled = _is_thinking_enabled(claude_req)

    system_content = ""
    if claude_req.system:
        system_content = _extract_system_content(claude_req.system)

    if thinking_enabled:
        system_content = f"{system_content}\n{THINKING_HINT}" if system_content else THINKING_HINT

    if system_content:
        openai_request["messages"].append({"role": "system", "content": system_content})

    openai_messages = convert_claude_messages_to_openai(claude_req.messages, thinking_enabled)
    openai_request["messages"].extend(openai_messages)

    # Bedrock (and some other backends) require at least one non-system message.
    # If all messages got filtered out (e.g. only tool_result blocks with no text),
    # inject a minimal user placeholder so the request is valid.
    non_system = [m for m in openai_request["messages"] if m.get("role") != "system"]
    if not non_system:
        openai_request["messages"].append({"role": "user", "content": "."})

    if claude_req.max_tokens:
        openai_request["max_tokens"] = claude_req.max_tokens

    if claude_req.temperature is not None:
        openai_request["temperature"] = claude_req.temperature

    if claude_req.tools:
        openai_tools = convert_claude_tools_to_openai(claude_req.tools)
        if openai_tools:
            openai_request["tools"] = openai_tools

    return openai_request, thinking_enabled


def _is_thinking_enabled(claude_req: AnthropicMessagesRequest) -> bool:
    thinking_param = getattr(claude_req, 'thinking', None)
    if thinking_param is not None:
        if isinstance(thinking_param, bool):
            return thinking_param
        elif isinstance(thinking_param, dict):
            thinking_type = thinking_param.get('type', 'enabled')
            return thinking_type == 'enabled' or thinking_param.get('enabled', True)
    return True  # 默认启用


def _filter_reserved_keywords(system_prompt: str) -> str:
    """从 system prompt 中过滤掉保留关键字"""
    import re
    if not system_prompt:
        return system_prompt

    reserved_keywords = [
        r"x-anthropic-billing-header",
        r"anthropic-billing",
        r"billing-header",
    ]

    filtered_prompt = system_prompt
    for keyword in reserved_keywords:
        pattern = rf"^.*{keyword}.*$"
        filtered_prompt = re.sub(pattern, "", filtered_prompt, flags=re.IGNORECASE | re.MULTILINE)

    filtered_prompt = re.sub(r'\n\s*\n\s*\n', '\n\n', filtered_prompt)
    return filtered_prompt.strip()


def _extract_system_content(system: Union[str, List[Dict[str, Any]]]) -> str:
    if isinstance(system, str):
        return _filter_reserved_keywords(system)
    elif isinstance(system, list):
        text_parts = [item.get("text", "") for item in system if isinstance(item, dict) and item.get("type") == "text"]
        return _filter_reserved_keywords("\n".join(text_parts))
    return ""


def convert_claude_messages_to_openai(messages: List[Any], thinking_enabled: bool = False) -> List[Dict[str, Any]]:
    """将 Claude 消息列表转换为 OpenAI 消息格式"""
    openai_messages: List[Dict[str, Any]] = []

    for msg in messages:
        role = msg.role
        content = msg.content

        if role == "user":
            openai_messages.extend(_convert_user_message(content))
        elif role == "assistant":
            assistant_msg = _convert_assistant_message(content, thinking_enabled)
            if assistant_msg:
                openai_messages.append(assistant_msg)

    return openai_messages


def _convert_user_message(content: Union[str, List[Any]]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []

    if isinstance(content, str):
        messages.append({"role": "user", "content": content})
    elif isinstance(content, list):
        text_parts: List[str] = []
        tool_results: List[Dict[str, Any]] = []

        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "tool_result":
                    tool_msg = _convert_tool_result_to_openai(block)
                    if tool_msg:
                        tool_results.append(tool_msg)
                elif block_type == "image":
                    image_content = _convert_image_block(block)
                    if image_content:
                        messages.append({"role": "user", "content": [image_content]})
            elif isinstance(block, str):
                text_parts.append(block)

        # tool messages must come before the next user text turn
        messages.extend(tool_results)

        if text_parts:
            combined_text = "\n".join(text_parts)
            if combined_text.strip():
                messages.append({"role": "user", "content": combined_text})

    return messages


def _convert_tool_result_to_openai(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool_use_id = block.get("tool_use_id")
    if not tool_use_id:
        return None

    raw_content = block.get("content", "")
    content_text = ""

    if isinstance(raw_content, str):
        content_text = raw_content
    elif isinstance(raw_content, list):
        text_parts = []
        for item in raw_content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif "text" in item:
                    text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        content_text = "\n".join(text_parts)

    return {"role": "tool", "tool_call_id": tool_use_id, "content": content_text or " "}


def _convert_image_block(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    source = block.get("source", {})
    if source.get("type") == "base64":
        media_type = source.get("media_type", "image/png")
        data = source.get("data", "")
        return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}}
    return None


def _convert_assistant_message(content: Union[str, List[Any]], thinking_enabled: bool = False) -> Optional[Dict[str, Any]]:
    if isinstance(content, str):
        return {"role": "assistant", "content": content}
    elif isinstance(content, list):
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "thinking":
                    if thinking_enabled:
                        thinking_text = block.get("thinking", "")
                        if thinking_text:
                            text_parts.append(f"{THINKING_START_TAG}{thinking_text}{THINKING_END_TAG}")
                elif block_type == "tool_use":
                    tool_call = _convert_tool_use_to_openai(block, len(tool_calls))
                    if tool_call:
                        tool_calls.append(tool_call)
            elif isinstance(block, str):
                text_parts.append(block)

        assistant_msg: Dict[str, Any] = {"role": "assistant"}
        combined_text = "\n".join(text_parts)
        # Use empty string instead of None — Bedrock rejects null content
        assistant_msg["content"] = combined_text.strip() or ""

        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls

        return assistant_msg

    return None


def _convert_tool_use_to_openai(block: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    tool_id = block.get("id")
    name = block.get("name")
    input_data = block.get("input", {})

    if not tool_id or not name:
        return None

    return {
        "id": tool_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)
        }
    }


def convert_claude_tools_to_openai(tools: List[AnthropicTool]) -> List[Dict[str, Any]]:
    """将 Claude 工具定义转换为 OpenAI function 格式"""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema
            }
        }
        for tool in tools
    ]


# ============================================================================
# Azure 请求清理
# ============================================================================

def _clean_claude_request_for_azure(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    为 Azure Anthropic API 清理 Claude 请求数据

    移除不支持的字段，处理 thinking 块，清理工具格式。
    """
    import copy
    cleaned = copy.deepcopy(request_data)

    # 移除不支持的顶层字段
    for field in ["context_management", "betas", "anthropic_beta"]:
        cleaned.pop(field, None)

    thinking_enabled = (
        "thinking" in cleaned and
        isinstance(cleaned.get("thinking"), dict) and
        cleaned["thinking"].get("type") == "enabled"
    )

    # 检查最后一条 assistant 消息是否以有效 thinking 块开头
    if thinking_enabled and isinstance(cleaned.get("messages"), list):
        last_assistant_msg = next(
            (m for m in reversed(cleaned["messages"]) if isinstance(m, dict) and m.get("role") == "assistant"),
            None
        )
        if last_assistant_msg:
            content = last_assistant_msg.get("content")
            has_valid_thinking = (
                isinstance(content, list) and
                len(content) > 0 and
                isinstance(content[0], dict) and
                content[0].get("type") == "thinking" and
                bool(content[0].get("signature"))
            )
            if not has_valid_thinking:
                logger.info("最后一条 assistant 消息没有有效的 thinking 块开头，禁用 thinking 功能")
                thinking_enabled = False
                cleaned.pop("thinking", None)

    # 清理 messages 中的 thinking/redacted_thinking 块
    if isinstance(cleaned.get("messages"), list):
        cleaned_messages = []
        for idx, msg in enumerate(cleaned["messages"]):
            if not isinstance(msg, dict):
                cleaned_messages.append(msg)
                continue

            content = msg.get("content")
            role = msg.get("role", "")

            if isinstance(content, list):
                cleaned_content = []
                for block in content:
                    if not isinstance(block, dict):
                        cleaned_content.append(block)
                        continue

                    block_type = block.get("type")

                    if block_type == "thinking":
                        if not thinking_enabled:
                            continue
                        elif block.get("signature"):
                            cleaned_content.append(block)
                        else:
                            # 无 signature → 转为 <previous_thinking> 文本
                            cleaned_content.append({
                                "type": "text",
                                "text": f"<previous_thinking>{block.get('thinking', '')}</previous_thinking>"
                            })
                        continue

                    if block_type == "redacted_thinking":
                        if thinking_enabled and block.get("data"):
                            cleaned_content.append(block)
                        continue

                    cleaned_content.append(block)

                content = cleaned_content
                msg = {**msg, "content": content}

            # 跳过空内容消息（最后一条 assistant 消息除外）
            is_empty = (
                content is None or
                (isinstance(content, str) and not content.strip()) or
                (isinstance(content, list) and len(content) == 0)
            )
            is_last = (idx == len(cleaned["messages"]) - 1)
            if is_empty and not (role == "assistant" and is_last):
                continue

            cleaned_messages.append(msg)

        cleaned["messages"] = cleaned_messages

    # 清理 tools 字段
    if isinstance(cleaned.get("tools"), list):
        cleaned_tools = []
        builtin_types = [
            "bash_20250124", "bash_20241022",
            "text_editor_20250124", "text_editor_20250429", "text_editor_20250728", "text_editor_20241022",
            "web_search_20250305", "computer_20241022"
        ]

        for idx, tool in enumerate(cleaned["tools"]):
            if not isinstance(tool, dict):
                continue

            tool_type = tool.get("type")

            if tool_type in builtin_types:
                t = {"type": tool_type}
                if "name" in tool:
                    t["name"] = tool["name"]
                cleaned_tools.append(t)

            elif tool_type == "custom":
                custom_data = tool.get("custom", {})
                t = {}
                for field in ["name", "description", "input_schema"]:
                    if field in custom_data:
                        t[field] = custom_data[field]
                    elif field in tool:
                        t[field] = tool[field]
                if t.get("name"):
                    cleaned_tools.append(t)

            elif tool_type == "function" or "function" in tool:
                func = tool.get("function", {})
                t = {}
                if func:
                    for src, dst in [("name", "name"), ("description", "description"), ("parameters", "input_schema")]:
                        if src in func:
                            t[dst] = func[src]
                if "name" not in t and "name" in tool:
                    t["name"] = tool["name"]
                if t.get("name"):
                    cleaned_tools.append(t)

            elif tool_type is None and "name" in tool:
                t = {"name": tool["name"]}
                if "description" in tool:
                    t["description"] = tool["description"]
                if "input_schema" in tool:
                    t["input_schema"] = tool["input_schema"]
                elif "parameters" in tool:
                    t["input_schema"] = tool["parameters"]
                cleaned_tools.append(t)

        cleaned["tools"] = cleaned_tools

    return cleaned


def _estimate_input_tokens(openai_request: Dict[str, Any]) -> int:
    """估算 OpenAI 请求的输入 token 数量（每 4 字符约 1 token）"""
    total_chars = 0

    for msg in openai_request.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    total_chars += len(item["text"])

    for tool in openai_request.get("tools", []):
        func = tool.get("function", {})
        total_chars += len(func.get("name", ""))
        total_chars += len(func.get("description", ""))
        total_chars += len(json.dumps(func.get("parameters", {})))

    return max(1, total_chars // 4)
