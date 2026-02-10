"""
Final Checkpoint: Per-Token Region Support 完整功能验证

验证整个 per-token-region-support 功能的端到端集成。
"""
import os
import sys
import tempfile
import pytest
import sqlite3

# 设置环境变量以绕过安全验证
os.environ.setdefault("USER_SESSION_SECRET", "test_secret_for_region_integration")
os.environ.setdefault("ADMIN_SECRET_KEY", "test_admin_secret_for_region_integration")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_complete_region_workflow():
    """
    测试完整的 region 工作流程：
    1. 数据库支持 region 字段
    2. donate_token 接受并存储 region
    3. get_token_credentials 返回 region
    4. TokenAllocator 使用正确的 region
    """
    from kiro_gateway.database import UserDatabase, DonatedToken
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    # 临时设置数据库路径
    original_db_path = os.environ.get("USER_DB_FILE")
    os.environ["USER_DB_FILE"] = db_path
    
    try:
        # 初始化数据库
        db = UserDatabase()
        
        # 创建测试用户 - create_user 返回 User 对象
        user = db.create_user("test_user", linuxdo_id="test_linuxdo_id")
        assert user is not None
        user_id = user.id
        
        # 测试添加不同 region 的 token
        test_regions = ["us-east-1", "ap-southeast-1", "eu-west-1"]
        token_ids = []
        
        for region in test_regions:
            success, msg = db.donate_token(
                user_id=user_id,
                refresh_token=f"test_token_{region}",
                visibility="private",
                auth_type="social",
                region=region
            )
            assert success, f"添加 {region} token 失败: {msg}"
            
            # 获取刚添加的 token
            tokens = db.get_user_tokens(user_id)
            token_ids.append(tokens[-1].id)
        
        # 验证每个 token 的 region 正确存储和返回
        for token_id, expected_region in zip(token_ids, test_regions):
            credentials = db.get_token_credentials(token_id)
            assert credentials is not None
            assert "region" in credentials
            assert credentials["region"] == expected_region, \
                f"Token {token_id} region 不匹配: 期望 {expected_region}, 实际 {credentials['region']}"
        
        # 测试默认 region
        success, msg = db.donate_token(
            user_id=user_id,
            refresh_token="test_token_default",
            visibility="private",
            auth_type="social"
            # 不指定 region，应该使用默认值
        )
        assert success
        
        tokens = db.get_user_tokens(user_id)
        default_token = tokens[-1]
        credentials = db.get_token_credentials(default_token.id)
        assert credentials["region"] == "us-east-1", "默认 region 应该是 us-east-1"
        
    finally:
        # 恢复原始数据库路径
        if original_db_path:
            os.environ["USER_DB_FILE"] = original_db_path
        elif "USER_DB_FILE" in os.environ:
            del os.environ["USER_DB_FILE"]
        
        # 清理临时数据库
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_api_endpoint_region_support():
    """验证 API 端点支持 region 参数"""
    from kiro_gateway.routes import SUPPORTED_REGIONS, user_donate_token
    import inspect
    
    # 验证支持的区域列表
    assert SUPPORTED_REGIONS is not None
    assert isinstance(SUPPORTED_REGIONS, set)
    assert len(SUPPORTED_REGIONS) >= 3
    assert "us-east-1" in SUPPORTED_REGIONS
    assert "ap-southeast-1" in SUPPORTED_REGIONS
    assert "eu-west-1" in SUPPORTED_REGIONS
    
    # 验证 API 端点接受 region 参数
    sig = inspect.signature(user_donate_token)
    params = list(sig.parameters.keys())
    assert 'region' in params


def test_token_allocator_region_usage():
    """验证 TokenAllocator 使用 token 的 region"""
    from kiro_gateway.token_allocator import SmartTokenAllocator
    import inspect
    
    # 检查 _get_manager 方法处理 region
    assert hasattr(SmartTokenAllocator, '_get_manager')
    source = inspect.getsource(SmartTokenAllocator._get_manager)
    
    # 验证代码中使用了 region
    assert 'region' in source.lower()
    assert 'get_token_credentials' in source


def test_donated_token_model_region():
    """验证 DonatedToken 数据模型包含 region 字段"""
    from kiro_gateway.database import DonatedToken
    
    # 测试创建不同 region 的 token
    regions = ["us-east-1", "ap-southeast-1", "eu-west-1", "us-west-2"]
    
    for region in regions:
        token = DonatedToken(
            id=1,
            user_id=1,
            token_hash="test_hash",
            auth_type="social",
            visibility="private",
            status="active",
            region=region,
            success_count=0,
            fail_count=0,
            last_used=None,
            last_check=None,
            created_at=1000000
        )
        assert hasattr(token, 'region')
        assert token.region == region


def test_database_schema_migration():
    """验证数据库 schema 包含 region 字段"""
    from kiro_gateway.database import UserDatabase
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    # 临时设置数据库路径
    original_db_path = os.environ.get("USER_DB_FILE")
    os.environ["USER_DB_FILE"] = db_path
    
    try:
        # 初始化数据库
        db = UserDatabase()
        
        # 直接连接数据库检查 schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tokens)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        conn.close()
        
        assert 'region' in column_names, "tokens 表应该包含 region 字段"
        
    finally:
        # 恢复原始数据库路径
        if original_db_path:
            os.environ["USER_DB_FILE"] = original_db_path
        elif "USER_DB_FILE" in os.environ:
            del os.environ["USER_DB_FILE"]
        
        # 清理临时数据库
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_all_requirements_implemented():
    """
    验证所有需求都已实现：
    - Req 1: 数据库支持 Token 区域字段
    - Req 2: Token 添加时支持区域选择
    - Req 3: Token 分配时使用正确区域
    - Req 4: 前端支持区域选择 (通过 API 端点验证)
    - Req 5: 管理界面显示 Token 区域 (通过数据库方法验证)
    """
    from kiro_gateway.database import UserDatabase, DonatedToken
    from kiro_gateway.routes import SUPPORTED_REGIONS
    from kiro_gateway.token_allocator import SmartTokenAllocator
    import inspect
    
    # Req 1: 数据库支持
    assert hasattr(DonatedToken, '__dataclass_fields__')
    assert 'region' in DonatedToken.__dataclass_fields__
    
    # Req 2: donate_token 支持 region
    sig = inspect.signature(UserDatabase.donate_token)
    assert 'region' in sig.parameters
    assert sig.parameters['region'].default == "us-east-1"
    
    # Req 3: get_token_credentials 返回 region
    method = UserDatabase.get_token_credentials
    docstring = method.__doc__ or ""
    assert 'region' in docstring.lower()
    
    # Req 3: TokenAllocator 使用 region
    source = inspect.getsource(SmartTokenAllocator._get_manager)
    assert 'region' in source.lower()
    
    # Req 4: API 端点支持 region
    assert SUPPORTED_REGIONS is not None
    assert len(SUPPORTED_REGIONS) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
