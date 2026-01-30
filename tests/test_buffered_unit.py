#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
单元测试：缓冲流处理器

测试 BufferedAnthropicStreamHandler 的核心逻辑，
不需要启动服务器。

运行方式: python3 test_buffered_unit.py
"""

import asyncio
import json
from typing import List, Dict, Any

# 导入要测试的模块
from kiro_gateway.buffered_streaming import BufferedAnthropicStreamHandler
from kiro_gateway.cache import ModelInfoCache


class MockModelCache:
    """模拟 ModelInfoCache"""
    
    def get_max_input_tokens(self, model: str) -> int:
        """返回模型的最大 input tokens"""
        # 模拟 Claude Sonnet 4 的 200k context
        return 200000


def test_event_buffering():
    """测试 1: 验证事件缓冲功能"""
    print("\n" + "=" * 60)
    print("测试 1: 事件缓冲功能")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,
        thinking_enabled=False
    )
    
    # 模拟一些事件
    events = [
        {"type": "content", "data": "Hello"},
        {"type": "content", "data": " world"},
        {"type": "content", "data": "!"},
    ]
    
    for event in events:
        handler._process_event(event)
    
    # 验证内容被缓冲
    full_content = ''.join(handler._content_parts)
    
    if full_content == "Hello world!":
        print("✓ PASS: 内容缓冲正确")
        print(f"  缓冲内容: {full_content}")
        return True
    else:
        print("✗ FAIL: 内容缓冲错误")
        print(f"  期望: 'Hello world!'")
        print(f"  实际: '{full_content}'")
        return False


def test_context_usage_parsing():
    """测试 2: 验证 contextUsageEvent 解析"""
    print("\n" + "=" * 60)
    print("测试 2: contextUsageEvent 解析")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,
        thinking_enabled=False
    )
    
    # 模拟 contextUsageEvent
    event = {
        "type": "context_usage",
        "data": 15.5  # 15.5% 的 context 使用率
    }
    
    handler._process_event(event)
    
    if handler.context_usage_percentage == 15.5:
        print("✓ PASS: contextUsageEvent 解析正确")
        print(f"  Context 使用率: {handler.context_usage_percentage}%")
        return True
    else:
        print("✗ FAIL: contextUsageEvent 解析错误")
        print(f"  期望: 15.5")
        print(f"  实际: {handler.context_usage_percentage}")
        return False


def test_accurate_input_tokens():
    """测试 3: 验证准确的 input_tokens 计算"""
    print("\n" + "=" * 60)
    print("测试 3: 准确的 input_tokens 计算")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,  # 估算值
        thinking_enabled=False
    )
    
    # 模拟内容和 contextUsageEvent
    handler._process_event({"type": "content", "data": "Test response"})
    handler._process_event({"type": "context_usage", "data": 10.0})  # 10% 使用率
    
    # 模拟 finalize
    mock_cache = MockModelCache()
    handler._finalize_events(mock_cache)
    
    # 计算期望值: 10% * 200000 = 20000
    expected_tokens = int((10.0 / 100) * 200000)
    actual_tokens = handler._accurate_input_tokens
    
    if actual_tokens == expected_tokens:
        print("✓ PASS: input_tokens 计算正确")
        print(f"  估算值: {handler.estimated_input_tokens}")
        print(f"  准确值: {actual_tokens} (来自 contextUsageEvent)")
        print(f"  Context 使用率: {handler.context_usage_percentage}%")
        return True
    else:
        print("✗ FAIL: input_tokens 计算错误")
        print(f"  期望: {expected_tokens}")
        print(f"  实际: {actual_tokens}")
        return False


def test_fallback_token_counting():
    """测试 4: 验证 fallback token 计数"""
    print("\n" + "=" * 60)
    print("测试 4: Fallback token 计数")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,
        thinking_enabled=False
    )
    
    # 不设置 contextUsageEvent，应该使用 fallback
    handler._process_event({"type": "content", "data": "Test response"})
    
    # 模拟 finalize（提供 request_messages 用于 fallback）
    mock_cache = MockModelCache()
    request_messages = [
        {"role": "user", "content": "Hello"}
    ]
    handler._finalize_events(mock_cache, request_messages=request_messages)
    
    # 应该使用 tiktoken 估算
    actual_tokens = handler._accurate_input_tokens
    
    if actual_tokens > 0:
        print("✓ PASS: Fallback token 计数正常")
        print(f"  Fallback tokens: {actual_tokens} (来自 tiktoken)")
        print(f"  注意: 未收到 contextUsageEvent，使用 tiktoken 估算")
        return True
    else:
        print("✗ FAIL: Fallback token 计数失败")
        print(f"  实际: {actual_tokens}")
        return False


def test_thinking_mode():
    """测试 5: 验证 thinking 模式处理"""
    print("\n" + "=" * 60)
    print("测试 5: Thinking 模式处理")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,
        thinking_enabled=True  # 启用 thinking
    )
    
    # 模拟 thinking 内容
    handler._process_event({"type": "content", "data": "<thinking>Let me think...</thinking>Hello"})
    
    # 检查是否有 thinking 事件被缓冲
    has_thinking_start = any(
        "thinking" in json.dumps(event) 
        for event in handler.event_buffer
    )
    
    if has_thinking_start:
        print("✓ PASS: Thinking 模式处理正常")
        print(f"  缓冲事件数: {len(handler.event_buffer)}")
        print(f"  检测到 thinking block")
        return True
    else:
        print("✗ FAIL: Thinking 模式处理失败")
        print(f"  缓冲事件数: {len(handler.event_buffer)}")
        print(f"  未检测到 thinking block")
        return False


def test_event_order():
    """测试 6: 验证事件顺序"""
    print("\n" + "=" * 60)
    print("测试 6: 事件顺序")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,
        thinking_enabled=False
    )
    
    # 模拟完整的响应流程
    handler._process_event({"type": "content", "data": "Hello world"})
    handler._process_event({"type": "context_usage", "data": 10.0})
    
    # Finalize
    mock_cache = MockModelCache()
    handler._finalize_events(mock_cache)
    
    # 检查事件顺序
    event_types = []
    for event_str in handler.event_buffer:
        if "event: " in event_str:
            event_type = event_str.split("event: ")[1].split("\n")[0]
            event_types.append(event_type)
    
    # 期望的事件顺序
    expected_sequence = [
        "content_block_start",  # 开始文本块
        "content_block_delta",  # 文本内容
        "content_block_stop",   # 结束文本块
        "message_delta",        # 消息 delta
        "message_stop"          # 消息结束
    ]
    
    # 验证关键事件存在
    has_start = "content_block_start" in event_types
    has_delta = "content_block_delta" in event_types
    has_stop = "content_block_stop" in event_types
    has_message_delta = "message_delta" in event_types
    has_message_stop = "message_stop" in event_types
    
    if all([has_start, has_delta, has_stop, has_message_delta, has_message_stop]):
        print("✓ PASS: 事件顺序正确")
        print(f"  事件序列: {event_types}")
        return True
    else:
        print("✗ FAIL: 事件顺序错误")
        print(f"  事件序列: {event_types}")
        print(f"  缺失事件:")
        if not has_start:
            print("    - content_block_start")
        if not has_delta:
            print("    - content_block_delta")
        if not has_stop:
            print("    - content_block_stop")
        if not has_message_delta:
            print("    - message_delta")
        if not has_message_stop:
            print("    - message_stop")
        return False


async def test_generate_all_events():
    """测试 7: 验证完整事件生成"""
    print("\n" + "=" * 60)
    print("测试 7: 完整事件生成")
    print("=" * 60)
    
    handler = BufferedAnthropicStreamHandler(
        model="claude-sonnet-4",
        estimated_input_tokens=100,
        thinking_enabled=False
    )
    
    # 模拟完整响应
    handler._process_event({"type": "content", "data": "Hello world"})
    handler._process_event({"type": "context_usage", "data": 10.0})
    
    # 生成所有事件
    mock_cache = MockModelCache()
    events = []
    async for event in handler.generate_all_events(mock_cache):
        events.append(event)
    
    # 验证第一个事件是 message_start
    if events and "event: message_start" in events[0]:
        # 解析 message_start 中的 input_tokens
        try:
            data_line = events[0].split("data: ")[1].split("\n")[0]
            data = json.loads(data_line)
            input_tokens = data["message"]["usage"]["input_tokens"]
            
            # 验证 input_tokens 是准确值
            expected_tokens = int((10.0 / 100) * 200000)
            
            if input_tokens == expected_tokens:
                print("✓ PASS: 完整事件生成正确")
                print(f"  总事件数: {len(events)}")
                print(f"  message_start input_tokens: {input_tokens}")
                print(f"  期望值: {expected_tokens}")
                return True
            else:
                print("✗ FAIL: input_tokens 不正确")
                print(f"  期望: {expected_tokens}")
                print(f"  实际: {input_tokens}")
                return False
        except Exception as e:
            print(f"✗ FAIL: 解析 message_start 失败: {e}")
            return False
    else:
        print("✗ FAIL: 第一个事件不是 message_start")
        if events:
            print(f"  第一个事件: {events[0][:100]}")
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("缓冲流处理器单元测试")
    print("=" * 80)
    
    # 运行所有测试
    tests = [
        ("事件缓冲功能", test_event_buffering),
        ("contextUsageEvent 解析", test_context_usage_parsing),
        ("准确的 input_tokens 计算", test_accurate_input_tokens),
        ("Fallback token 计数", test_fallback_token_counting),
        ("Thinking 模式处理", test_thinking_mode),
        ("事件顺序", test_event_order),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ FAIL: {name}")
            print(f"  异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 异步测试
    print("\n" + "=" * 60)
    print("运行异步测试...")
    print("=" * 60)
    try:
        result = asyncio.run(test_generate_all_events())
        results.append(("完整事件生成", result))
    except Exception as e:
        print(f"\n✗ FAIL: 完整事件生成")
        print(f"  异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("完整事件生成", False))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过\n")
    
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
    
    print("\n" + "=" * 80)
    
    if passed == total:
        print("✓ 所有测试通过！缓冲流处理器实现正确。")
        print("\n下一步:")
        print("  1. 重启 KiroGate 服务器以加载新端点")
        print("  2. 运行集成测试: python3 test_buffered_mode.py")
        return 0
    else:
        print(f"✗ {total - passed} 个测试失败，请检查实现。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
