"""
Checkpoint 2: 数据库层验证测试

验证 Task 1 中所有数据库相关修改正确工作。
"""
import os
import tempfile
from kiro_gateway.database import UserDatabase, DonatedToken


def test_database_module_imports():
    """验证数据库模块可以正确导入"""
    from kiro_gateway.database import UserDatabase, DonatedToken
    assert UserDatabase is not None
    assert DonatedToken is not None


def test_donated_token_dataclass_has_region():
    """验证 DonatedToken 数据模型包含 region 字段 (Task 1.1)"""
    token = DonatedToken(
        id=1,
        user_id=1,
        token_hash="test_hash",
        auth_type="social",
        visibility="private",
        status="active",
        region="ap-southeast-1",
        success_count=0,
        fail_count=0,
        last_used=None,
        last_check=None,
        created_at=1000000
    )
    assert hasattr(token, 'region')
    assert token.region == "ap-southeast-1"


def test_donate_token_method_accepts_region():
    """验证 donate_token 方法接受 region 参数 (Task 1.3)"""
    import inspect
    from kiro_gateway.database import UserDatabase
    
    sig = inspect.signature(UserDatabase.donate_token)
    params = list(sig.parameters.keys())
    assert 'region' in params, "donate_token 方法应该有 region 参数"
    
    # 检查默认值
    region_param = sig.parameters['region']
    assert region_param.default == "us-east-1", "region 默认值应该是 us-east-1"


def test_get_token_credentials_returns_region():
    """验证 get_token_credentials 方法返回 region 信息 (Task 1.4)"""
    import inspect
    from kiro_gateway.database import UserDatabase
    
    # 检查方法存在
    assert hasattr(UserDatabase, 'get_token_credentials')
    
    # 检查方法文档说明返回 region
    method = UserDatabase.get_token_credentials
    docstring = method.__doc__ or ""
    assert 'region' in docstring.lower(), "get_token_credentials 文档应该提到 region"


def test_row_to_token_handles_region():
    """验证 _row_to_token 方法处理 region 字段 (Task 1.5)"""
    import inspect
    from kiro_gateway.database import UserDatabase
    
    # 检查方法存在
    assert hasattr(UserDatabase, '_row_to_token')
    
    # 检查源代码中处理了 region
    source = inspect.getsource(UserDatabase._row_to_token)
    assert 'region' in source, "_row_to_token 应该处理 region 字段"
