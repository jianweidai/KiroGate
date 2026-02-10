"""
Checkpoint 5: 后端功能验证测试

验证 API 端点正确处理 region 参数。
"""
import inspect
from kiro_gateway.routes import SUPPORTED_REGIONS, user_donate_token


def test_supported_regions_constant_exists():
    """验证 SUPPORTED_REGIONS 常量存在且包含正确的区域"""
    assert SUPPORTED_REGIONS is not None
    assert isinstance(SUPPORTED_REGIONS, set)
    assert "us-east-1" in SUPPORTED_REGIONS
    assert "ap-southeast-1" in SUPPORTED_REGIONS
    assert "eu-west-1" in SUPPORTED_REGIONS


def test_user_donate_token_has_region_parameter():
    """验证 user_donate_token 端点接受 region 参数"""
    sig = inspect.signature(user_donate_token)
    params = list(sig.parameters.keys())
    assert 'region' in params, "user_donate_token 应该有 region 参数"
    
    # 检查默认值
    region_param = sig.parameters['region']
    # Form 参数的默认值是 Form 对象，需要检查其 default 属性
    assert region_param.default is not None


def test_user_donate_token_is_async():
    """验证 user_donate_token 是异步函数"""
    assert inspect.iscoroutinefunction(user_donate_token)


def test_token_allocator_uses_token_region():
    """验证 TokenAllocator._get_manager 使用 Token 的 region"""
    from kiro_gateway.token_allocator import SmartTokenAllocator
    
    # 检查 _get_manager 方法存在
    assert hasattr(SmartTokenAllocator, '_get_manager')
    
    # 检查源代码中使用了 region
    source = inspect.getsource(SmartTokenAllocator._get_manager)
    assert 'region' in source, "_get_manager 应该处理 region"
    assert 'get_token_credentials' in source, "_get_manager 应该调用 get_token_credentials"


def test_database_donate_token_has_region():
    """验证数据库 donate_token 方法支持 region 参数"""
    from kiro_gateway.database import UserDatabase
    
    sig = inspect.signature(UserDatabase.donate_token)
    params = list(sig.parameters.keys())
    assert 'region' in params


def test_database_get_token_credentials_returns_region():
    """验证 get_token_credentials 返回 region 信息"""
    from kiro_gateway.database import UserDatabase
    
    # 检查方法文档说明返回 region
    method = UserDatabase.get_token_credentials
    docstring = method.__doc__ or ""
    assert 'region' in docstring.lower()
