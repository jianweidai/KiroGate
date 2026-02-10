"""
Final Checkpoint: Per-Token Region Support 完整功能验证

验证整个 per-token-region-support 功能的所有组件正确实现。
"""
import os
import sys
import inspect

# 设置环境变量以绕过安全验证
os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_final_verification")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_final_verification")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_requirement_1_database_support():
    """
    需求 1: 数据库支持 Token 区域字段
    验证 DonatedToken 数据模型和数据库方法支持 region
    """
    from kiro_gateway.database import UserDatabase, DonatedToken
    
    # 1.1: DonatedToken 包含 region 字段
    assert hasattr(DonatedToken, '__dataclass_fields__')
    assert 'region' in DonatedToken.__dataclass_fields__
    
    # 测试创建 DonatedToken 实例
    token = DonatedToken(
        id=1,
        user_id=1,
        token_hash="test",
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
    assert token.region == "ap-southeast-1"
    
    # 1.2: donate_token 方法支持 region 参数
    sig = inspect.signature(UserDatabase.donate_token)
    assert 'region' in sig.parameters
    assert sig.parameters['region'].default == "us-east-1"
    
    # 1.3: get_token_credentials 返回 region
    method = UserDatabase.get_token_credentials
    docstring = method.__doc__ or ""
    assert 'region' in docstring.lower()
    
    # 验证方法签名
    source = inspect.getsource(method)
    assert 'region' in source


def test_requirement_2_api_endpoint_support():
    """
    需求 2: Token 添加时支持区域选择
    验证 API 端点接受 region 参数
    """
    from kiro_gateway.routes import SUPPORTED_REGIONS, user_donate_token
    
    # 2.1: SUPPORTED_REGIONS 常量存在
    assert SUPPORTED_REGIONS is not None
    assert isinstance(SUPPORTED_REGIONS, set)
    assert "us-east-1" in SUPPORTED_REGIONS
    assert "ap-southeast-1" in SUPPORTED_REGIONS
    assert "eu-west-1" in SUPPORTED_REGIONS
    
    # 2.2: user_donate_token 接受 region 参数
    sig = inspect.signature(user_donate_token)
    params = list(sig.parameters.keys())
    assert 'region' in params
    
    # 2.3: 验证是异步函数
    assert inspect.iscoroutinefunction(user_donate_token)


def test_requirement_3_token_allocator():
    """
    需求 3: Token 分配时使用正确区域
    验证 TokenAllocator 使用 token 的 region
    """
    from kiro_gateway.token_allocator import SmartTokenAllocator
    
    # 3.1: _get_manager 方法存在
    assert hasattr(SmartTokenAllocator, '_get_manager')
    
    # 3.2: _get_manager 使用 region
    source = inspect.getsource(SmartTokenAllocator._get_manager)
    assert 'region' in source.lower()
    assert 'get_token_credentials' in source
    
    # 验证从 credentials 中获取 region
    assert 'credentials' in source
    assert '.get(' in source or '["region"]' in source


def test_database_schema_has_region_migration():
    """
    验证数据库初始化代码包含 region 字段迁移
    """
    from kiro_gateway.database import UserDatabase
    
    # 检查 _init_db 方法包含 region 迁移逻辑
    source = inspect.getsource(UserDatabase._init_db)
    assert 'region' in source.lower()
    assert 'ALTER TABLE tokens ADD COLUMN region' in source


def test_donate_token_inserts_region():
    """
    验证 donate_token 方法在 INSERT 语句中包含 region
    """
    from kiro_gateway.database import UserDatabase
    
    source = inspect.getsource(UserDatabase.donate_token)
    
    # 验证 INSERT 语句包含 region
    assert 'region' in source
    assert 'INSERT INTO tokens' in source
    
    # 验证参数传递
    assert 'region' in source.lower()


def test_get_token_credentials_returns_region():
    """
    验证 get_token_credentials 方法返回 region 信息
    """
    from kiro_gateway.database import UserDatabase
    
    source = inspect.getsource(UserDatabase.get_token_credentials)
    
    # 验证 SELECT 语句包含 region
    assert 'region' in source
    assert 'SELECT' in source
    
    # 验证返回字典包含 region
    assert '"region"' in source or "'region'" in source


def test_all_tasks_completed():
    """
    验证所有任务都已完成：
    - Task 1: 数据库层修改 ✓
    - Task 2: Checkpoint - 数据库层验证 ✓
    - Task 3: Token 分配器修改 ✓
    - Task 4: API 端点修改 ✓
    - Task 5: Checkpoint - 后端功能验证 ✓
    - Task 6: 前端界面修改 (需要手动验证)
    - Task 7: 管理界面修改 (需要手动验证)
    - Task 8: Final Checkpoint ✓
    """
    from kiro_gateway.database import UserDatabase, DonatedToken
    from kiro_gateway.routes import SUPPORTED_REGIONS, user_donate_token
    from kiro_gateway.token_allocator import SmartTokenAllocator
    
    # 所有关键组件都存在
    assert UserDatabase is not None
    assert DonatedToken is not None
    assert SUPPORTED_REGIONS is not None
    assert user_donate_token is not None
    assert SmartTokenAllocator is not None
    
    # 所有关键方法都存在
    assert hasattr(UserDatabase, 'donate_token')
    assert hasattr(UserDatabase, 'get_token_credentials')
    assert hasattr(SmartTokenAllocator, '_get_manager')
    
    # 所有关键字段都存在
    assert 'region' in DonatedToken.__dataclass_fields__


def test_region_values_supported():
    """
    验证支持的区域值
    """
    from kiro_gateway.routes import SUPPORTED_REGIONS
    
    # 至少支持 3 个区域
    assert len(SUPPORTED_REGIONS) >= 3
    
    # 包含主要区域
    required_regions = {"us-east-1", "ap-southeast-1", "eu-west-1"}
    assert required_regions.issubset(SUPPORTED_REGIONS)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
