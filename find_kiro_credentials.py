#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
查找 Kiro IDE 凭证文件并提取配置信息

运行方式: python3 find_kiro_credentials.py
"""

import json
import os
from pathlib import Path


def find_kiro_credentials():
    """查找并显示 Kiro 凭证信息"""
    print("=" * 60)
    print("查找 Kiro IDE 凭证")
    print("=" * 60)
    
    # 查找 Kiro 配置目录
    home = Path.home()
    kiro_dir = home / ".kiro" / "sso" / "cache"
    
    if not kiro_dir.exists():
        print(f"\n❌ 未找到 Kiro 配置目录: {kiro_dir}")
        print("\n可能的原因：")
        print("1. 你还没有安装或登录 Kiro IDE")
        print("2. Kiro IDE 使用了不同的配置路径")
        print("\n建议：")
        print("1. 安装并登录 Kiro IDE")
        print("2. 或者从其他已配置的项目复制凭证")
        return
    
    print(f"\n✓ 找到 Kiro 配置目录: {kiro_dir}")
    
    # 查找所有 JSON 文件
    json_files = list(kiro_dir.glob("*.json"))
    
    if not json_files:
        print(f"\n❌ 配置目录中没有找到凭证文件")
        return
    
    print(f"\n✓ 找到 {len(json_files)} 个凭证文件")
    
    # 读取并显示凭证信息
    for json_file in json_files:
        print(f"\n{'=' * 60}")
        print(f"文件: {json_file.name}")
        print(f"{'=' * 60}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取关键信息
            profile_arn = data.get('profileArn') or data.get('profile_arn')
            refresh_token = data.get('refreshToken') or data.get('refresh_token')
            region = data.get('region', 'us-east-1')
            
            # IDC 模式的额外字段
            client_id = data.get('clientId') or data.get('client_id')
            client_secret = data.get('clientSecret') or data.get('client_secret')
            
            if profile_arn:
                print(f"\n✓ 找到有效凭证！")
                print(f"\n配置信息：")
                print(f"  PROFILE_ARN=\"{profile_arn}\"")
                print(f"  KIRO_REGION=\"{region}\"")
                
                if refresh_token:
                    print(f"  REFRESH_TOKEN=\"{refresh_token[:20]}...\"")
                
                if client_id:
                    print(f"  CLIENT_ID=\"{client_id}\"")
                
                if client_secret:
                    print(f"  CLIENT_SECRET=\"{client_secret[:20]}...\"")
                
                print(f"\n推荐配置方式 1 - 使用凭证文件（最简单）：")
                print(f"  在 .env 文件中添加：")
                print(f"  KIRO_CREDS_FILE=\"{json_file}\"")
                
                print(f"\n推荐配置方式 2 - 手动配置：")
                print(f"  在 .env 文件中添加：")
                print(f"  PROFILE_ARN=\"{profile_arn}\"")
                print(f"  KIRO_REGION=\"{region}\"")
                if refresh_token:
                    print(f"  REFRESH_TOKEN=\"{refresh_token}\"")
                if client_id:
                    print(f"  CLIENT_ID=\"{client_id}\"")
                if client_secret:
                    print(f"  CLIENT_SECRET=\"{client_secret}\"")
                
                return True
            else:
                print(f"\n⚠️  文件中没有找到 profileArn")
                
        except json.JSONDecodeError as e:
            print(f"\n❌ 无法解析 JSON: {e}")
        except Exception as e:
            print(f"\n❌ 读取文件失败: {e}")
    
    return False


def check_current_env():
    """检查当前 .env 配置"""
    print(f"\n{'=' * 60}")
    print("检查当前 .env 配置")
    print(f"{'=' * 60}")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("\n❌ 未找到 .env 文件")
        return
    
    print(f"\n✓ 找到 .env 文件")
    
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键配置
    configs = {
        'PROFILE_ARN': False,
        'KIRO_CREDS_FILE': False,
        'REFRESH_TOKEN': False,
        'CLIENT_ID': False,
        'CLIENT_SECRET': False,
    }
    
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        
        for key in configs:
            if line.startswith(f"{key}="):
                configs[key] = True
                value = line.split('=', 1)[1].strip('"').strip("'")
                if value:
                    print(f"  ✓ {key}: 已配置")
                else:
                    print(f"  ⚠️  {key}: 已定义但为空")
    
    # 显示未配置的项
    missing = [k for k, v in configs.items() if not v]
    if missing:
        print(f"\n未配置的项: {', '.join(missing)}")
    
    # 检查是否有足够的配置
    has_creds_file = configs['KIRO_CREDS_FILE']
    has_manual_config = configs['PROFILE_ARN'] or configs['REFRESH_TOKEN']
    
    if not has_creds_file and not has_manual_config:
        print(f"\n❌ 缺少必要的凭证配置！")
        print(f"   需要配置 KIRO_CREDS_FILE 或 PROFILE_ARN/REFRESH_TOKEN")
    else:
        print(f"\n✓ 凭证配置看起来正常")


def main():
    """主函数"""
    print("\n🔍 Kiro 凭证查找工具\n")
    
    # 检查当前配置
    check_current_env()
    
    # 查找 Kiro 凭证
    found = find_kiro_credentials()
    
    if not found:
        print(f"\n{'=' * 60}")
        print("未找到可用的 Kiro 凭证")
        print(f"{'=' * 60}")
        print("\n建议：")
        print("1. 确保已安装并登录 Kiro IDE")
        print("2. 或者从其他已配置的项目（如 amq2api）复制凭证")
        print("3. 或者联系管理员获取凭证信息")
    
    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
