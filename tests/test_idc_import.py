# -*- coding: utf-8 -*-

"""
针对 IDC 凭证导入兼容性修复的单元测试（PR #27 迁移）

覆盖以下场景：
1. 驼峰命名（原有）：refreshToken / clientId / clientSecret
2. 蛇形命名（新增）：refresh_token / client_id / client_secret
3. credentials_kiro_rs 嵌套结构（新增）
4. credentials 嵌套结构（原有）
5. 纯字符串 token
6. 混合列表
7. 缺少 token 时的错误计数
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiro_gateway.routes import _extract_refresh_tokens


class TestExtractRefreshTokensCamelCase:
    """原有驼峰命名格式，确保没有被改坏。"""

    def test_single_camel_case_object(self):
        payload = {"refreshToken": "token-abc"}
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].refresh_token == "token-abc"
        assert creds[0].auth_type == "social"
        assert missing == 0

    def test_idc_camel_case_top_level(self):
        payload = {
            "refreshToken": "token-idc",
            "clientId": "cid-123",
            "clientSecret": "csec-456",
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].auth_type == "idc"
        assert creds[0].client_id == "cid-123"
        assert creds[0].client_secret == "csec-456"

    def test_credentials_nested_camel_case(self):
        payload = {
            "credentials": {
                "refreshToken": "token-nested",
                "clientId": "cid-nested",
                "clientSecret": "csec-nested",
            }
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].refresh_token == "token-nested"
        assert creds[0].auth_type == "idc"

    def test_list_of_camel_case_objects(self):
        payload = [
            {"refreshToken": "token-1"},
            {"refreshToken": "token-2"},
        ]
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 2
        assert missing == 0


class TestExtractRefreshTokensSnakeCase:
    """新增蛇形命名支持。"""

    def test_single_snake_case_object(self):
        payload = {"refresh_token": "token-snake"}
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].refresh_token == "token-snake"
        assert creds[0].auth_type == "social"
        assert missing == 0

    def test_idc_snake_case_top_level(self):
        payload = {
            "refresh_token": "token-idc-snake",
            "client_id": "cid-snake",
            "client_secret": "csec-snake",
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].auth_type == "idc"
        assert creds[0].client_id == "cid-snake"
        assert creds[0].client_secret == "csec-snake"

    def test_credentials_nested_snake_case(self):
        payload = {
            "credentials": {
                "refresh_token": "token-nested-snake",
                "client_id": "cid-nested-snake",
                "client_secret": "csec-nested-snake",
            }
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].refresh_token == "token-nested-snake"
        assert creds[0].auth_type == "idc"

    def test_list_of_snake_case_objects(self):
        payload = [
            {"refresh_token": "token-s1"},
            {"refresh_token": "token-s2"},
        ]
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 2
        assert missing == 0


class TestExtractRefreshTokensKiroRsFormat:
    """新增 credentials_kiro_rs 嵌套结构支持（Kiro Account Manager 导出格式）。"""

    def test_credentials_kiro_rs_camel_case(self):
        payload = {
            "credentials_kiro_rs": {
                "refreshToken": "token-kiro-rs",
                "clientId": "cid-kiro-rs",
                "clientSecret": "csec-kiro-rs",
            }
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].refresh_token == "token-kiro-rs"
        assert creds[0].auth_type == "idc"
        assert creds[0].client_id == "cid-kiro-rs"

    def test_credentials_kiro_rs_snake_case(self):
        payload = {
            "credentials_kiro_rs": {
                "refresh_token": "token-kiro-rs-snake",
                "client_id": "cid-kiro-rs-snake",
                "client_secret": "csec-kiro-rs-snake",
            }
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].refresh_token == "token-kiro-rs-snake"
        assert creds[0].auth_type == "idc"

    def test_credentials_kiro_rs_social_only(self):
        """只有 refresh_token，没有 client 信息，应识别为 social。"""
        payload = {
            "credentials_kiro_rs": {
                "refresh_token": "token-social-kiro-rs",
            }
        }
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 1
        assert creds[0].auth_type == "social"
        assert creds[0].client_id is None

    def test_list_with_credentials_kiro_rs(self):
        payload = [
            {"credentials_kiro_rs": {"refresh_token": "t1", "client_id": "c1", "client_secret": "s1"}},
            {"credentials_kiro_rs": {"refresh_token": "t2"}},
        ]
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 2
        assert creds[0].auth_type == "idc"
        assert creds[1].auth_type == "social"


class TestExtractRefreshTokensEdgeCases:
    """边界情况和错误处理。"""

    def test_plain_string_token(self):
        payload = ["token-plain-1", "token-plain-2"]
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 2
        assert creds[0].refresh_token == "token-plain-1"

    def test_missing_token_counted(self):
        payload = [{"some_other_field": "value"}]
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 0
        assert missing == 1

    def test_empty_refresh_token_counted(self):
        payload = {"refresh_token": "   "}
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 0
        assert missing == 1

    def test_mixed_camel_and_snake_in_list(self):
        payload = [
            {"refreshToken": "token-camel"},
            {"refresh_token": "token-snake"},
        ]
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert len(creds) == 2
        assert missing == 0

    def test_whitespace_stripped_from_token(self):
        payload = {"refresh_token": "  token-with-spaces  "}
        creds, missing, _ = _extract_refresh_tokens(payload)
        assert creds[0].refresh_token == "token-with-spaces"

    def test_empty_list(self):
        creds, missing, _ = _extract_refresh_tokens([])
        assert len(creds) == 0
        assert missing == 0
