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
Buffered streaming response processing for /cc/v1/messages endpoint.

This module implements buffered streaming mode similar to kiro.rs:
- Buffers all events until stream completes
- Waits for contextUsageEvent to get accurate input_tokens
- Corrects message_start event with accurate input_tokens
- Sends all events at once after stream completion
- Sends ping keepalive every 25 seconds during buffering
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING, AsyncGenerator, Optional, List, Dict, Any

import httpx
from loguru import logger

from kiro_gateway.parsers import AwsEventStreamParser, parse_bracket_tool_calls, deduplicate_tool_calls
from kiro_gateway.streaming import (
    ThinkingStreamHandler,
    StreamReadTimeoutError,
    _read_chunk_with_timeout,
    generate_anthropic_message_id
)
from kiro_gateway.tokenizer import count_message_tokens, count_tools_tokens
from kiro_gateway.config import settings, get_adaptive_timeout

if TYPE_CHECKING:
    from kiro_gateway.cache import ModelInfoCache

try:
    from kiro_gateway.debug_logger import debug_logger
except ImportError:
    debug_logger = None


# Ping interval in seconds (send keepalive every 25 seconds)
PING_INTERVAL_SECONDS = 25


class BufferedAnthropicStreamHandler:
    """
    Buffered stream handler for /cc/v1/messages endpoint.
    
    Unlike standard streaming, this handler:
    1. Buffers all events until stream completes
    2. Waits for contextUsageEvent to get accurate input_tokens
    3. Corrects message_start event with accurate input_tokens
    4. Sends all events at once after stream completion
    
    This ensures message_start contains accurate input_tokens from Kiro API,
    which is important for Claude Code CLI and other clients that rely on
    accurate token counting for billing and quota management.
    
    Attributes:
        model: Model name
        estimated_input_tokens: Estimated input tokens (fallback)
        thinking_enabled: Whether thinking mode is enabled
        event_buffer: Buffer for all SSE events
        context_usage_percentage: Context usage percentage from Kiro API
        message_id: Generated message ID
    """
    
    def __init__(
        self,
        model: str,
        estimated_input_tokens: int,
        thinking_enabled: bool = False
    ):
        """
        Initialize buffered stream handler.
        
        Args:
            model: Model name
            estimated_input_tokens: Estimated input tokens (used as fallback)
            thinking_enabled: Whether thinking mode is enabled
        """
        self.model = model
        self.estimated_input_tokens = estimated_input_tokens
        self.thinking_enabled = thinking_enabled
        self.event_buffer: List[str] = []  # Buffer for SSE event strings
        self.context_usage_percentage: Optional[float] = None
        self.message_id = generate_anthropic_message_id()
        
        # Internal state for event processing
        self._parser = AwsEventStreamParser()
        self._thinking_handler = ThinkingStreamHandler(thinking_enabled=thinking_enabled)
        self._content_parts: List[str] = []
        self._content_block_index = 0
        self._text_block_started = False
        self._thinking_block_started = False
        self._metering_data: Optional[Any] = None
        
        logger.debug(
            f"BufferedAnthropicStreamHandler initialized: "
            f"model={model}, estimated_tokens={estimated_input_tokens}, "
            f"thinking={thinking_enabled}"
        )
    
    async def process_stream(
        self,
        response: httpx.Response,
        stream_read_timeout: float = settings.stream_read_timeout
    ) -> None:
        """
        Process upstream stream and buffer all events.
        
        This method reads the entire stream, processes all events,
        and buffers them for later output.
        
        Args:
            response: HTTP response with stream
            stream_read_timeout: Timeout for reading each chunk
        """
        # Adaptive timeout based on model
        adaptive_timeout = get_adaptive_timeout(self.model, stream_read_timeout)
        
        try:
            byte_iterator = response.aiter_bytes()
            consecutive_timeouts = 0
            max_consecutive_timeouts = 3
            
            while True:
                try:
                    chunk = await _read_chunk_with_timeout(byte_iterator, adaptive_timeout)
                    consecutive_timeouts = 0
                except StopAsyncIteration:
                    break
                except StreamReadTimeoutError as e:
                    consecutive_timeouts += 1
                    if consecutive_timeouts <= max_consecutive_timeouts:
                        logger.warning(
                            f"Buffered stream timeout {consecutive_timeouts}/{max_consecutive_timeouts} "
                            f"after {adaptive_timeout}s (model: {self.model})"
                        )
                        continue
                    else:
                        logger.error(
                            f"Buffered stream timeout after {max_consecutive_timeouts} "
                            f"consecutive timeouts (model: {self.model}): {e}"
                        )
                        raise
                
                if debug_logger:
                    debug_logger.log_raw_chunk(chunk)
                
                # Parse events from chunk
                events = self._parser.feed(chunk)
                
                # Process each event
                for event in events:
                    self._process_event(event)
        
        finally:
            await response.aclose()
            logger.debug("Buffered stream processing completed")
    
    def _process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single event and buffer corresponding SSE events.
        
        Args:
            event: Parsed event from AwsEventStreamParser
        """
        if event["type"] == "content":
            content = event["data"]
            self._content_parts.append(content)
            
            # Process content through thinking handler
            thinking_events = self._thinking_handler.process_content(content)
            
            for te in thinking_events:
                if te["type"] == "thinking":
                    self._process_thinking_event(te)
                elif te["type"] == "text" and te["content"]:
                    self._process_text_event(te)
        
        elif event["type"] == "usage":
            self._metering_data = event["data"]
        
        elif event["type"] == "context_usage":
            self.context_usage_percentage = event["data"]
            logger.debug(
                f"Received contextUsageEvent: {self.context_usage_percentage}%"
            )
    
    def _process_thinking_event(self, te: Dict[str, Any]) -> None:
        """Process thinking-related events."""
        if te["action"] == "start":
            # Close current text block if open
            if self._text_block_started:
                self._buffer_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": self._content_block_index
                })
                self._content_block_index += 1
                self._text_block_started = False
            
            # Start thinking block
            self._buffer_event("content_block_start", {
                "type": "content_block_start",
                "index": self._content_block_index,
                "content_block": {"type": "thinking", "thinking": ""}
            })
            self._thinking_block_started = True
        
        elif te["action"] == "delta" and te["content"]:
            if self._thinking_block_started:
                self._buffer_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": self._content_block_index,
                    "delta": {"type": "thinking_delta", "thinking": te["content"]}
                })
        
        elif te["action"] == "stop":
            if self._thinking_block_started:
                self._buffer_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": self._content_block_index
                })
                self._content_block_index += 1
                self._thinking_block_started = False
    
    def _process_text_event(self, te: Dict[str, Any]) -> None:
        """Process text content events."""
        if not self._text_block_started:
            self._buffer_event("content_block_start", {
                "type": "content_block_start",
                "index": self._content_block_index,
                "content_block": {"type": "text", "text": ""}
            })
            self._text_block_started = True
        
        self._buffer_event("content_block_delta", {
            "type": "content_block_delta",
            "index": self._content_block_index,
            "delta": {"type": "text_delta", "text": te["content"]}
        })
    
    def _buffer_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Buffer an SSE event.
        
        Args:
            event_type: Event type (e.g., "content_block_start")
            data: Event data
        """
        sse_event = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.event_buffer.append(sse_event)
    
    def _finalize_events(
        self,
        model_cache: "ModelInfoCache",
        request_messages: Optional[list] = None,
        request_tools: Optional[list] = None
    ) -> None:
        """
        Finalize all events after stream completion.
        
        This method:
        1. Flushes remaining thinking handler content
        2. Closes any open content blocks
        3. Processes tool calls
        4. Calculates accurate input_tokens
        5. Generates message_delta and message_stop events
        
        Args:
            model_cache: Model cache for token limits
            request_messages: Request messages for fallback token counting
            request_tools: Request tools for fallback token counting
        """
        # Flush thinking handler
        flush_events = self._thinking_handler.flush()
        for te in flush_events:
            if te["type"] == "thinking" and te["content"] and self._thinking_block_started:
                self._buffer_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": self._content_block_index,
                    "delta": {"type": "thinking_delta", "thinking": te["content"]}
                })
            elif te["type"] == "text" and te["content"]:
                if not self._text_block_started:
                    self._buffer_event("content_block_start", {
                        "type": "content_block_start",
                        "index": self._content_block_index,
                        "content_block": {"type": "text", "text": ""}
                    })
                    self._text_block_started = True
                
                self._buffer_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": self._content_block_index,
                    "delta": {"type": "text_delta", "text": te["content"]}
                })
        
        # Close open blocks
        if self._thinking_block_started:
            self._buffer_event("content_block_stop", {
                "type": "content_block_stop",
                "index": self._content_block_index
            })
            self._content_block_index += 1
        
        if self._text_block_started:
            self._buffer_event("content_block_stop", {
                "type": "content_block_stop",
                "index": self._content_block_index
            })
            self._content_block_index += 1
        
        # Process tool calls
        full_content = ''.join(self._content_parts)
        bracket_tool_calls = parse_bracket_tool_calls(full_content)
        all_tool_calls = self._parser.get_tool_calls() + bracket_tool_calls
        all_tool_calls = deduplicate_tool_calls(all_tool_calls)
        
        # Add tool_use blocks
        for tc in all_tool_calls:
            func = tc.get("function") or {}
            tool_name = func.get("name") or ""
            tool_args_str = func.get("arguments") or "{}"
            tool_id = tc.get("id") or f"toolu_{self.message_id[4:16]}"
            
            try:
                tool_input = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_input = {}
            
            # content_block_start for tool_use
            self._buffer_event("content_block_start", {
                "type": "content_block_start",
                "index": self._content_block_index,
                "content_block": {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool_name,
                    "input": {}
                }
            })
            
            # input_json_delta
            if tool_input:
                self._buffer_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": self._content_block_index,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(tool_input, ensure_ascii=False)
                    }
                })
            
            # content_block_stop
            self._buffer_event("content_block_stop", {
                "type": "content_block_stop",
                "index": self._content_block_index
            })
            
            self._content_block_index += 1
        
        # Calculate accurate input_tokens
        if self.context_usage_percentage is not None and self.context_usage_percentage > 0:
            max_input_tokens = model_cache.get_max_input_tokens(self.model)
            accurate_input_tokens = int(
                (self.context_usage_percentage / 100) * max_input_tokens
            )
            token_source = "contextUsageEvent"
        else:
            # Fallback to tiktoken estimation
            accurate_input_tokens = 0
            if request_messages:
                accurate_input_tokens += count_message_tokens(
                    request_messages, apply_claude_correction=False
                )
            if request_tools:
                accurate_input_tokens += count_tools_tokens(
                    request_tools, apply_claude_correction=False
                )
            token_source = "tiktoken (fallback)"
        
        # Calculate output tokens
        from kiro_gateway.tokenizer import count_tokens
        output_tokens = count_tokens(full_content)
        
        # Determine stop_reason
        stop_reason = "tool_use" if all_tool_calls else "end_turn"
        
        # Add message_delta event
        self._buffer_event("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": stop_reason,
                "stop_sequence": None
            },
            "usage": {
                "output_tokens": output_tokens
            }
        })
        
        # Add message_stop event
        self._buffer_event("message_stop", {
            "type": "message_stop"
        })
        
        logger.info(
            f"[Buffered Mode] {self.model}: "
            f"input_tokens={accurate_input_tokens} ({token_source}), "
            f"output_tokens={output_tokens}"
        )
        
        # Store accurate input_tokens for message_start correction
        self._accurate_input_tokens = accurate_input_tokens
        self._output_tokens = output_tokens
    
    async def generate_all_events(
        self,
        model_cache: "ModelInfoCache",
        request_messages: Optional[list] = None,
        request_tools: Optional[list] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate all buffered events with corrected message_start.
        
        This method:
        1. Finalizes all events
        2. Sends message_start with accurate input_tokens
        3. Sends all buffered events
        
        Args:
            model_cache: Model cache for token limits
            request_messages: Request messages for fallback token counting
            request_tools: Request tools for fallback token counting
        
        Yields:
            SSE event strings
        """
        # Finalize all events
        self._finalize_events(model_cache, request_messages, request_tools)
        
        # Send message_start with accurate input_tokens
        message_start = {
            "type": "message_start",
            "message": {
                "id": self.message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": self.model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": self._accurate_input_tokens,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0
                }
            }
        }
        
        yield f"event: message_start\ndata: {json.dumps(message_start, ensure_ascii=False)}\n\n"
        
        # Send all buffered events
        for event in self.event_buffer:
            yield event


async def stream_kiro_to_anthropic_buffered(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model: str,
    model_cache: "ModelInfoCache",
    auth_manager: "KiroAuthManager" = None,  # 为了兼容性添加，但不使用
    request_messages: Optional[list] = None,
    request_tools: Optional[list] = None,
    thinking_enabled: bool = False,
    stream_read_timeout: float = settings.stream_read_timeout
) -> AsyncGenerator[str, None]:
    """
    Convert Kiro stream to Anthropic format with buffering (for /cc/v1/messages).
    
    This function implements buffered streaming mode:
    1. Buffers all events until stream completes
    2. Sends ping keepalive every 25 seconds during buffering
    3. Waits for contextUsageEvent to get accurate input_tokens
    4. Corrects message_start with accurate input_tokens
    5. Sends all events at once after stream completion
    
    Args:
        client: HTTP client
        response: HTTP response with stream
        model: Model name
        model_cache: Model cache for token limits
        auth_manager: Auth manager (not used, for compatibility with standard stream function)
        request_messages: Request messages for token counting
        request_tools: Request tools for token counting
        thinking_enabled: Whether thinking mode is enabled
        stream_read_timeout: Timeout for reading each chunk
    
    Yields:
        SSE event strings
    """
    # Pre-calculate estimated input tokens
    estimated_input_tokens = 0
    if request_messages:
        estimated_input_tokens += count_message_tokens(
            request_messages, apply_claude_correction=False
        )
    if request_tools:
        estimated_input_tokens += count_tools_tokens(
            request_tools, apply_claude_correction=False
        )
    
    # Create buffered handler
    handler = BufferedAnthropicStreamHandler(
        model=model,
        estimated_input_tokens=estimated_input_tokens,
        thinking_enabled=thinking_enabled
    )
    
    # Process stream in background task
    stream_task = asyncio.create_task(
        handler.process_stream(response, stream_read_timeout)
    )
    
    # Send ping keepalive while waiting
    last_ping_time = time.time()
    while not stream_task.done():
        await asyncio.sleep(1)  # Check every second
        
        current_time = time.time()
        if current_time - last_ping_time >= PING_INTERVAL_SECONDS:
            yield 'event: ping\ndata: {"type": "ping"}\n\n'
            last_ping_time = current_time
            logger.debug("Sent ping keepalive (buffered mode)")
    
    # Wait for stream processing to complete
    try:
        await stream_task
    except Exception as e:
        logger.error(f"Error during buffered stream processing: {e}", exc_info=True)
        # Send error event
        error_event = {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": str(e) if str(e) else f"{type(e).__name__}"
            }
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        return
    
    # Generate all events with corrected message_start
    async for event in handler.generate_all_events(
        model_cache, request_messages, request_tools
    ):
        yield event
    
    logger.debug("Buffered streaming completed")
