#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 assistant 消息处理（修复空 content 问题）

运行方式: python3 test_assistant_message.py
"""

import asyncio
import httpx


async def test_assistant_message():
    """测试包含 assistant 消息的请求"""
    print("=" * 60)
    print("测试 Assistant 消息处理")
    print("=" * 60)
    
    url = "http://localhost:8000/v1/messages"
    api_key = "daijianwei"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01",
    }
    
    # 模拟一个包含 assistant 消息的对话
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 128,
        "messages": [
            {
                "role": "user",
                "content": "Generate ultra-concise status updates describing the current high-level task or goal."
            },
            {
                "role": "assistant",
                "content": "Here is the status:\n\n<status>"
            }
        ]
    }
    
    print("\n发送测试请求...")
    print(f"URL: {url}")
    print(f"Model: {payload['model']}")
    print(f"消息数量: {len(payload['messages'])}")
    print(f"最后一条消息角色: {payload['messages'][-1]['role']}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"\n响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n✓ 请求成功！")
                print(f"\nResponse ID: {data.get('id')}")
                print(f"Model: {data.get('model')}")
                print(f"Stop Reason: {data.get('stop_reason')}")
                
                if data.get('content'):
                    content = data['content'][0]
                    if content.get('type') == 'text':
                        text = content.get('text', '')
                        print(f"\n回复内容（前 200 字符）:\n{text[:200]}...")
                
                if data.get('usage'):
                    usage = data['usage']
                    print(f"\nToken 使用:")
                    print(f"  Input: {usage.get('input_tokens')}")
                    print(f"  Output: {usage.get('output_tokens')}")
                
                return True
            else:
                print(f"\n✗ 请求失败")
                print(f"响应内容: {response.text}")
                return False
                
    except httpx.ConnectError:
        print("\n✗ 连接失败 - 请确保 KiroGate 服务正在运行")
        return False
    except Exception as e:
        print(f"\n✗ 请求出错: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("\n🧪 Assistant 消息处理测试\n")
    
    success = await test_assistant_message()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ 测试通过 - Assistant 消息处理正常")
        print("  修复已生效：不再发送空 content")
    else:
        print("✗ 测试失败")
    print("=" * 60 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
