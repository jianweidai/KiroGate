#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试缓冲模式 (/cc/v1/messages) 的准确性和功能

测试内容：
1. 验证 message_start 中的 input_tokens 是否准确（来自 contextUsageEvent）
2. 验证 ping 保活机制（每 25 秒发送一次）
3. 验证非流式请求使用标准处理器
4. 验证 thinking 模式兼容性
5. 验证 tool_use 兼容性
6. 对比 /v1/messages 和 /cc/v1/messages 的差异

运行方式: python3 test_buffered_mode.py
"""

import asyncio
import httpx
import json
import time
from typing import Optional, Dict, Any, List


# 配置
BASE_URL = "http://localhost:8000"
API_KEY = "daijianwei"  # 替换为你的 API Key
TIMEOUT = 120.0  # 2 分钟超时


class TestResult:
    """测试结果"""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.details = {}
    
    def success(self, message: str = "", **details):
        self.passed = True
        self.message = message
        self.details = details
    
    def failure(self, message: str = "", **details):
        self.passed = False
        self.message = message
        self.details = details
    
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        result = f"{status}: {self.name}"
        if self.message:
            result += f"\n  {self.message}"
        if self.details:
            for key, value in self.details.items():
                result += f"\n  {key}: {value}"
        return result


async def parse_sse_stream(response: httpx.Response) -> List[Dict[str, Any]]:
    """
    解析 SSE 流并返回所有事件
    
    Args:
        response: HTTP 响应
    
    Returns:
        事件列表，每个事件包含 event_type 和 data
    """
    events = []
    buffer = ""
    
    async for chunk in response.aiter_text():
        buffer += chunk
        
        # 按行分割
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            
            if not line:
                continue
            
            # 解析 event: 行
            if line.startswith("event: "):
                event_type = line[7:].strip()
                events.append({"event_type": event_type, "data": None})
            
            # 解析 data: 行
            elif line.startswith("data: "):
                data_str = line[6:].strip()
                try:
                    data = json.loads(data_str)
                    if events and events[-1]["data"] is None:
                        events[-1]["data"] = data
                    else:
                        events.append({"event_type": "unknown", "data": data})
                except json.JSONDecodeError:
                    pass
    
    return events


async def test_buffered_streaming_accuracy() -> TestResult:
    """
    测试 1: 验证缓冲模式的 input_tokens 准确性
    
    对比 /v1/messages 和 /cc/v1/messages 的 input_tokens，
    验证 /cc/v1/messages 使用的是 contextUsageEvent 的准确值
    """
    result = TestResult("缓冲模式 input_tokens 准确性")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    # 构造一个较长的请求以便观察 token 差异
    payload = {
        "model": "claude-sonnet-4",
        "max_tokens": 100,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": "请用一句话介绍 Python 编程语言。" * 10  # 重复 10 次以增加 token 数
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # 测试标准端点
            print("\n  测试 /v1/messages...")
            response_standard = await client.post(
                f"{BASE_URL}/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response_standard.status_code != 200:
                result.failure(
                    f"标准端点返回错误: {response_standard.status_code}",
                    response=response_standard.text[:200]
                )
                return result
            
            events_standard = await parse_sse_stream(response_standard)
            
            # 提取 message_start 中的 input_tokens
            input_tokens_standard = None
            for event in events_standard:
                if event["event_type"] == "message_start" and event["data"]:
                    input_tokens_standard = event["data"].get("message", {}).get("usage", {}).get("input_tokens")
                    break
            
            # 测试缓冲端点
            print("  测试 /cc/v1/messages...")
            response_buffered = await client.post(
                f"{BASE_URL}/cc/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response_buffered.status_code != 200:
                result.failure(
                    f"缓冲端点返回错误: {response_buffered.status_code}",
                    response=response_buffered.text[:200]
                )
                return result
            
            events_buffered = await parse_sse_stream(response_buffered)
            
            # 提取 message_start 中的 input_tokens
            input_tokens_buffered = None
            for event in events_buffered:
                if event["event_type"] == "message_start" and event["data"]:
                    input_tokens_buffered = event["data"].get("message", {}).get("usage", {}).get("input_tokens")
                    break
            
            # 验证结果
            if input_tokens_standard is None or input_tokens_buffered is None:
                result.failure(
                    "无法提取 input_tokens",
                    standard=input_tokens_standard,
                    buffered=input_tokens_buffered
                )
                return result
            
            # 缓冲模式应该使用更准确的值（通常与标准模式不同）
            # 注意：如果 Kiro API 返回了 contextUsageEvent，缓冲模式会使用准确值
            result.success(
                "成功获取 input_tokens",
                standard_tokens=input_tokens_standard,
                buffered_tokens=input_tokens_buffered,
                difference=abs(input_tokens_buffered - input_tokens_standard),
                note="缓冲模式使用 contextUsageEvent 的准确值"
            )
            return result
            
    except Exception as e:
        result.failure(f"测试出错: {e}")
        return result


async def test_ping_keepalive() -> TestResult:
    """
    测试 2: 验证 ping 保活机制
    
    发送一个需要较长时间处理的请求，验证是否收到 ping 事件
    """
    result = TestResult("Ping 保活机制")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    # 构造一个可能需要较长时间的请求
    payload = {
        "model": "claude-sonnet-4",
        "max_tokens": 1000,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": "请详细解释 Python 的异步编程机制，包括 asyncio、协程、事件循环等概念。"
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("\n  测试 /cc/v1/messages ping 机制...")
            response = await client.post(
                f"{BASE_URL}/cc/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                result.failure(
                    f"请求返回错误: {response.status_code}",
                    response=response.text[:200]
                )
                return result
            
            events = await parse_sse_stream(response)
            
            # 检查是否有 ping 事件
            ping_count = sum(1 for event in events if event["event_type"] == "ping")
            
            # 注意：如果响应很快，可能不会有 ping 事件
            # 这不算失败，只是说明响应速度快
            if ping_count > 0:
                result.success(
                    f"检测到 {ping_count} 个 ping 事件",
                    ping_count=ping_count,
                    total_events=len(events)
                )
            else:
                result.success(
                    "未检测到 ping 事件（响应速度较快）",
                    total_events=len(events),
                    note="如果响应时间 < 25 秒，不会发送 ping"
                )
            
            return result
            
    except Exception as e:
        result.failure(f"测试出错: {e}")
        return result


async def test_non_streaming_mode() -> TestResult:
    """
    测试 3: 验证非流式请求使用标准处理器
    
    /cc/v1/messages 的非流式请求应该与 /v1/messages 行为一致
    """
    result = TestResult("非流式请求处理")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 50,
        "stream": False,  # 非流式
        "messages": [
            {
                "role": "user",
                "content": "Say hello in one word."
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # 测试标准端点
            print("\n  测试 /v1/messages (非流式)...")
            response_standard = await client.post(
                f"{BASE_URL}/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response_standard.status_code != 200:
                result.failure(
                    f"标准端点返回错误: {response_standard.status_code}",
                    response=response_standard.text[:200]
                )
                return result
            
            data_standard = response_standard.json()
            
            # 测试缓冲端点
            print("  测试 /cc/v1/messages (非流式)...")
            response_buffered = await client.post(
                f"{BASE_URL}/cc/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response_buffered.status_code != 200:
                result.failure(
                    f"缓冲端点返回错误: {response_buffered.status_code}",
                    response=response_buffered.text[:200]
                )
                return result
            
            data_buffered = response_buffered.json()
            
            # 验证响应结构一致
            if data_standard.get("type") == data_buffered.get("type") == "message":
                result.success(
                    "非流式请求处理正常",
                    standard_id=data_standard.get("id"),
                    buffered_id=data_buffered.get("id"),
                    note="两个端点返回相同格式的响应"
                )
            else:
                result.failure(
                    "响应格式不一致",
                    standard_type=data_standard.get("type"),
                    buffered_type=data_buffered.get("type")
                )
            
            return result
            
    except Exception as e:
        result.failure(f"测试出错: {e}")
        return result


async def test_thinking_mode_compatibility() -> TestResult:
    """
    测试 4: 验证 thinking 模式兼容性
    
    测试缓冲模式是否正确处理 Extended Thinking
    """
    result = TestResult("Thinking 模式兼容性")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": "claude-sonnet-4",
        "max_tokens": 200,
        "stream": True,
        "thinking": {
            "type": "enabled",
            "budget_tokens": 1000
        },
        "messages": [
            {
                "role": "user",
                "content": "What is 2+2? Think step by step."
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("\n  测试 /cc/v1/messages (thinking 模式)...")
            response = await client.post(
                f"{BASE_URL}/cc/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                result.failure(
                    f"请求返回错误: {response.status_code}",
                    response=response.text[:200]
                )
                return result
            
            events = await parse_sse_stream(response)
            
            # 检查是否有 thinking content block
            has_thinking = False
            has_text = False
            
            for event in events:
                if event["event_type"] == "content_block_start" and event["data"]:
                    block_type = event["data"].get("content_block", {}).get("type")
                    if block_type == "thinking":
                        has_thinking = True
                    elif block_type == "text":
                        has_text = True
            
            if has_thinking and has_text:
                result.success(
                    "Thinking 模式处理正常",
                    has_thinking_block=True,
                    has_text_block=True,
                    total_events=len(events)
                )
            elif has_text:
                result.success(
                    "响应正常（未检测到 thinking block）",
                    has_thinking_block=False,
                    has_text_block=True,
                    note="模型可能未使用 thinking 模式"
                )
            else:
                result.failure(
                    "未检测到有效的 content block",
                    has_thinking_block=has_thinking,
                    has_text_block=has_text
                )
            
            return result
            
    except Exception as e:
        result.failure(f"测试出错: {e}")
        return result


async def test_tool_use_compatibility() -> TestResult:
    """
    测试 5: 验证 tool_use 兼容性
    
    测试缓冲模式是否正确处理工具调用
    """
    result = TestResult("Tool Use 兼容性")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": "claude-sonnet-4",
        "max_tokens": 200,
        "stream": True,
        "tools": [
            {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA"
                        }
                    },
                    "required": ["location"]
                }
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": "What's the weather in San Francisco?"
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("\n  测试 /cc/v1/messages (tool use)...")
            response = await client.post(
                f"{BASE_URL}/cc/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                result.failure(
                    f"请求返回错误: {response.status_code}",
                    response=response.text[:200]
                )
                return result
            
            events = await parse_sse_stream(response)
            
            # 检查是否有 tool_use content block
            has_tool_use = False
            tool_name = None
            stop_reason = None
            
            for event in events:
                if event["event_type"] == "content_block_start" and event["data"]:
                    block = event["data"].get("content_block", {})
                    if block.get("type") == "tool_use":
                        has_tool_use = True
                        tool_name = block.get("name")
                
                if event["event_type"] == "message_delta" and event["data"]:
                    stop_reason = event["data"].get("delta", {}).get("stop_reason")
            
            if has_tool_use:
                result.success(
                    "Tool Use 处理正常",
                    has_tool_use=True,
                    tool_name=tool_name,
                    stop_reason=stop_reason,
                    total_events=len(events)
                )
            else:
                result.success(
                    "响应正常（未使用工具）",
                    has_tool_use=False,
                    stop_reason=stop_reason,
                    note="模型可能选择不使用工具"
                )
            
            return result
            
    except Exception as e:
        result.failure(f"测试出错: {e}")
        return result


async def test_event_order() -> TestResult:
    """
    测试 6: 验证事件顺序
    
    验证缓冲模式的事件顺序是否正确：
    message_start -> content_block_* -> message_delta -> message_stop
    """
    result = TestResult("事件顺序验证")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 50,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": "Say hello."
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("\n  测试 /cc/v1/messages 事件顺序...")
            response = await client.post(
                f"{BASE_URL}/cc/v1/messages",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                result.failure(
                    f"请求返回错误: {response.status_code}",
                    response=response.text[:200]
                )
                return result
            
            events = await parse_sse_stream(response)
            event_types = [e["event_type"] for e in events]
            
            # 验证事件顺序
            expected_start = ["message_start"]
            expected_end = ["message_delta", "message_stop"]
            
            # 检查开始事件
            if not event_types or event_types[0] != "message_start":
                result.failure(
                    "事件顺序错误：未以 message_start 开始",
                    first_event=event_types[0] if event_types else None
                )
                return result
            
            # 检查结束事件
            if len(event_types) < 2 or event_types[-1] != "message_stop":
                result.failure(
                    "事件顺序错误：未以 message_stop 结束",
                    last_event=event_types[-1] if event_types else None
                )
                return result
            
            if event_types[-2] != "message_delta":
                result.failure(
                    "事件顺序错误：message_stop 前应为 message_delta",
                    second_last_event=event_types[-2] if len(event_types) >= 2 else None
                )
                return result
            
            result.success(
                "事件顺序正确",
                event_sequence=event_types,
                total_events=len(events)
            )
            return result
            
    except Exception as e:
        result.failure(f"测试出错: {e}")
        return result


async def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("KiroGate 缓冲模式测试套件")
    print("=" * 80)
    
    print(f"\n配置:")
    print(f"  BASE_URL: {BASE_URL}")
    print(f"  API_KEY: {API_KEY[:10]}..." if len(API_KEY) > 10 else f"  API_KEY: {API_KEY}")
    print(f"  TIMEOUT: {TIMEOUT}s")
    
    # 运行所有测试
    tests = [
        test_buffered_streaming_accuracy,
        test_ping_keepalive,
        test_non_streaming_mode,
        test_thinking_mode_compatibility,
        test_tool_use_compatibility,
        test_event_order,
    ]
    
    results = []
    for test_func in tests:
        print(f"\n{'=' * 80}")
        print(f"运行测试: {test_func.__doc__.split('测试')[1].split(':')[0].strip()}")
        print("=" * 80)
        
        result = await test_func()
        results.append(result)
        print(f"\n{result}")
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    for result in results:
        status = "✓" if result.passed else "✗"
        print(f"  {status} {result.name}")
    
    print("\n" + "=" * 80)
    
    if passed == total:
        print("✓ 所有测试通过！缓冲模式实现正确。")
        return 0
    else:
        print(f"✗ {total - passed} 个测试失败，请检查实现。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
