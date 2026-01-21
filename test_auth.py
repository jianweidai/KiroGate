#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 Kiro 认证配置

运行方式: python3 test_auth.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from kiro_gateway.auth import KiroAuthManager


async def test_auth():
    """测试认证配置"""
    print("=" * 60)
    print("测试 Kiro 认证配置")
    print("=" * 60)
    
    # 加载环境变量
    load_dotenv()
    
    # 读取配置
    refresh_token = os.getenv("REFRESH_TOKEN")
    profile_arn = os.getenv("PROFILE_ARN")
    region = os.getenv("KIRO_REGION", "us-east-1")
    creds_file = os.getenv("KIRO_CREDS_FILE")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    print("\n当前配置:")
    print(f"  REFRESH_TOKEN: {'✓ 已配置' if refresh_token else '✗ 未配置'}")
    print(f"  PROFILE_ARN: {profile_arn if profile_arn else '✗ 未配置'}")
    print(f"  KIRO_REGION: {region}")
    print(f"  KIRO_CREDS_FILE: {creds_file if creds_file else '✗ 未配置'}")
    print(f"  CLIENT_ID: {'✓ 已配置' if client_id else '✗ 未配置'}")
    print(f"  CLIENT_SECRET: {'✓ 已配置' if client_secret else '✗ 未配置'}")
    
    # 检查必要配置
    if not refresh_token and not creds_file:
        print("\n❌ 错误: 缺少必要的凭证配置！")
        print("\n你需要配置以下之一：")
        print("  1. KIRO_CREDS_FILE - 指向 Kiro IDE 凭证文件")
        print("  2. REFRESH_TOKEN - 手动配置 refresh token")
        print("\n示例配置 (.env 文件):")
        print('  KIRO_CREDS_FILE="~/.kiro/sso/cache/xxxxx.json"')
        print("  或")
        print('  REFRESH_TOKEN="your_refresh_token_here"')
        print('  PROFILE_ARN="arn:aws:codewhisperer:us-east-1:..."')
        return False
    
    # 创建认证管理器
    print("\n创建认证管理器...")
    try:
        auth_manager = KiroAuthManager(
            refresh_token=refresh_token,
            profile_arn=profile_arn,
            region=region,
            creds_file=creds_file,
            client_id=client_id,
            client_secret=client_secret,
        )
        print("✓ 认证管理器创建成功")
    except Exception as e:
        print(f"❌ 创建认证管理器失败: {e}")
        return False
    
    # 显示认证类型
    print(f"\n认证类型: {auth_manager.auth_type.value}")
    print(f"API Host: {auth_manager.api_host}")
    print(f"Q Host: {auth_manager.q_host}")
    
    # 检查 profile_arn
    if auth_manager.profile_arn:
        print(f"Profile ARN: {auth_manager.profile_arn}")
    else:
        print("⚠️  Profile ARN: 未配置（将在首次刷新 token 时自动获取）")
    
    # 尝试获取 access token
    print("\n尝试获取 access token...")
    try:
        access_token = await auth_manager.get_access_token()
        print(f"✓ 成功获取 access token: {access_token[:20]}...")
        
        # 显示更新后的 profile_arn
        if auth_manager.profile_arn:
            print(f"✓ Profile ARN: {auth_manager.profile_arn}")
        else:
            print("⚠️  Profile ARN 仍未获取到")
        
        print("\n✓ 认证配置测试通过！")
        print("\n建议在 .env 文件中添加以下配置（如果还没有）:")
        if auth_manager.profile_arn:
            print(f'PROFILE_ARN="{auth_manager.profile_arn}"')
        
        return True
        
    except Exception as e:
        print(f"❌ 获取 access token 失败: {e}")
        print("\n可能的原因:")
        print("  1. refresh_token 无效或已过期")
        print("  2. 网络连接问题")
        print("  3. 凭证文件格式不正确")
        return False


async def main():
    """主函数"""
    print("\n🔐 Kiro 认证测试工具\n")
    
    success = await test_auth()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ 测试完成 - 认证配置正常")
    else:
        print("✗ 测试失败 - 请检查配置")
    print("=" * 60 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
