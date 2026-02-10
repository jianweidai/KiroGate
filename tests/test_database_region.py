"""
测试数据库层的 region 字段支持

验证 DonatedToken 数据模型和数据库操作正确处理 region 字段。
"""
from kiro_gateway.database import DonatedToken


def test_donated_token_has_region_field():
    """测试 DonatedToken 数据模型包含 region 字段"""
    token = DonatedToken(
        id=1,
        user_id=1,
        token_hash="test_hash",
        auth_type="social",
        visibility="private",
        status="active",
        region="us-east-1",
        success_count=0,
        fail_count=0,
        last_used=None,
        last_check=None,
        created_at=1000000
    )
    assert hasattr(token, 'region')
    assert token.region == "us-east-1"


def test_donated_token_region_different_values():
    """测试 DonatedToken 支持不同的 region 值"""
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
        assert token.region == region


