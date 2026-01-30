#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 Kiro API 请求

运行方式: python3 test_api_request.py
"""

import asyncio
import httpx


async def test_api_request():
    """测试 API 请求"""
    print("=" * 60)
    print("测试 KiroGate API 请求")
    print("=" * 60)
    
    url = "http://localhost:8000/v1/messages"
    
    # 从 .env 读取 API key
    api_key = "daijianwei"  # 你的 PROXY_API_KEY
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01",
    }
    
    payload = {
        "model": "claude-sonnet-4",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": "Hello! Please respond with a simple greeting."
            }
        ]
    }
    
    print("\n发送测试请求...")
    print(f"URL: {url}")
    print(f"Model: {payload['model']}")
    
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
                        print(f"\n回复内容:\n{content.get('text')}")
                
                # 检查 usage
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
        print("   运行命令: python3 main.py")
        return False
    except Exception as e:
        print(f"\n✗ 请求出错: {e}")
        return False


async def main():
    """主函数"""
    print("\n🧪 KiroGate API 测试工具\n")
    
    success = await test_api_request()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ 测试完成 - API 工作正常")
    else:
        print("✗ 测试失败 - 请检查服务和配置")
    print("=" * 60 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
