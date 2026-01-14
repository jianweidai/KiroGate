# IDC 认证模式 & OAuth2 State 验证修复文档

## 修复日期
2026-01-13

## 问题描述

用户通过 **IDC (AWS Builder ID)** 方式登录 Kiro IDE，但系统在刷新 Token 时错误地使用了 **Social (Kiro Desktop Auth)** 模式，导致 `401 Unauthorized` 错误：

```
通过 Social (Kiro Desktop Auth) 刷新 Token...
ERROR - Client error '401 Unauthorized' for url 'https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken'
```

## 根本原因分析

### 1. 认证类型检测逻辑

`KiroAuthManager` 类通过 `_detect_auth_type()` 方法判断认证类型：

```python
def _detect_auth_type(self) -> None:
    if self._client_id and self._client_secret:
        self._auth_type = AuthType.IDC  # 使用 AWS SSO OIDC 端点
    else:
        self._auth_type = AuthType.SOCIAL  # 默认使用 Kiro Desktop 端点
```

### 2. 缺失的配置传递

存在以下问题：

1. **配置文件未定义 IDC 变量**：`Settings` 类中没有定义 `CLIENT_ID` 和 `CLIENT_SECRET` 环境变量
2. **全局 AuthManager 未传递凭证**：`main.py` 创建 `KiroAuthManager` 时未传递 `client_id` 和 `client_secret`
3. **Token 分配器未读取 IDC 凭证**：`token_allocator.py` 只获取 `refresh_token`，忽略了 IDC 凭证
4. **健康检查器未读取 IDC 凭证**：`health_checker.py` 同样只获取 `refresh_token`

## 修复内容

### 1. `kiro_gateway/config.py`

**新增 IDC 模式环境变量配置**

```python
# IDC 模式凭证（AWS Builder ID 登录）
# 从 Kiro IDE 凭证文件中获取
client_id: str = Field(default="", alias="CLIENT_ID")
client_secret: str = Field(default="", alias="CLIENT_SECRET")
```

### 2. `main.py`

**创建全局 AuthManager 时传递 IDC 凭证**

```python
auth_manager = KiroAuthManager(
    refresh_token=settings.refresh_token,
    profile_arn=settings.profile_arn,
    region=settings.region,
    creds_file=settings.kiro_creds_file if settings.kiro_creds_file else None,
    client_id=settings.client_id if settings.client_id else None,      # 新增
    client_secret=settings.client_secret if settings.client_secret else None,  # 新增
)
```

### 3. `kiro_gateway/token_allocator.py`

**使用 `get_token_credentials()` 获取完整凭证**

```python
async def _get_manager(self, token: DonatedToken) -> KiroAuthManager:
    # 获取完整凭证信息（包括 IDC 的 client_id 和 client_secret）
    credentials = user_db.get_token_credentials(token.id)
    if not credentials or not credentials.get("refresh_token"):
        raise NoTokenAvailable(f"Failed to get credentials for token {token.id}")

    # 创建 AuthManager，传递完整凭证以支持 IDC 认证模式
    manager = KiroAuthManager(
        refresh_token=credentials["refresh_token"],
        region=settings.region,
        profile_arn=settings.profile_arn,
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
    )
    return manager
```

### 4. `kiro_gateway/health_checker.py`

**同样使用 `get_token_credentials()` 获取完整凭证**

```python
async def check_token(self, token_id: int) -> bool:
    # 获取完整凭证信息（包括 IDC 的 client_id 和 client_secret）
    credentials = user_db.get_token_credentials(token_id)
    if not credentials or not credentials.get("refresh_token"):
        user_db.record_health_check(token_id, False, "Failed to get token credentials")
        return False

    # 创建 AuthManager，传递完整凭证以支持 IDC 认证模式
    manager = KiroAuthManager(
        refresh_token=credentials["refresh_token"],
        region=settings.region,
        profile_arn=settings.profile_arn,
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
    )
    # ...
```

### 5. `kiro_gateway/auth_cache.py`

**扩展 `get_or_create()` 方法支持 IDC 凭证**

```python
async def get_or_create(
    self,
    refresh_token: str,
    region: Optional[str] = None,
    profile_arn: Optional[str] = None,
    client_id: Optional[str] = None,      # 新增
    client_secret: Optional[str] = None   # 新增
) -> KiroAuthManager:
    # ...
    auth_manager = KiroAuthManager(
        refresh_token=refresh_token,
        region=region or settings.region,
        profile_arn=profile_arn or settings.profile_arn,
        client_id=client_id,
        client_secret=client_secret,
    )
```

## 配置说明

### `.env` 文件配置示例

对于 IDC (AWS Builder ID) 登录用户，需要在 `.env` 中配置：

```bash
# ===========================================
# 方式三: IDC 登录 (AWS Builder ID)
# ===========================================

# OAuth Client ID（从 Kiro IDE 凭证文件获取）
CLIENT_ID="your_client_id_here"

# OAuth Client Secret（从 Kiro IDE 凭证文件获取）
CLIENT_SECRET="your_client_secret_here"

# Refresh Token
REFRESH_TOKEN="your_refresh_token_here"
```

### 凭证文件位置

IDC 凭证可以从 Kiro IDE 的凭证文件中获取：

- **Windows**: `%APPDATA%\Kiro\credentials.json`
- **macOS**: `~/Library/Application Support/Kiro/credentials.json`
- **Linux**: `~/.config/Kiro/credentials.json`

## 认证流程对比

| 认证类型 | 端点 | 请求格式 |
|---------|------|---------|
| **Social** | `https://prod.{region}.auth.desktop.kiro.dev/refreshToken` | `{"refreshToken": "..."}` |
| **IDC** | `https://oidc.{region}.amazonaws.com/token` | `{"clientId": "...", "clientSecret": "...", "grantType": "refresh_token", "refreshToken": "..."}` |

## 验证方法

重启应用后，观察日志输出：

**修复前（错误）**：
```
检测到认证类型: Social (Kiro Desktop)
通过 Social (Kiro Desktop Auth) 刷新 Token...
ERROR - 401 Unauthorized
```

**修复后（正确）**：
```
检测到认证类型: IDC (AWS SSO OIDC)
通过 IDC (AWS SSO OIDC) 刷新 Token...
Token 刷新成功
```

## 受影响的文件

| 文件 | 修改类型 |
|------|---------|
| `kiro_gateway/config.py` | 新增 `CLIENT_ID` 和 `CLIENT_SECRET` 配置 |
| `main.py` | 传递 IDC 凭证给全局 AuthManager |
| `kiro_gateway/token_allocator.py` | 使用 `get_token_credentials()` 获取完整凭证 |
| `kiro_gateway/health_checker.py` | 使用 `get_token_credentials()` 获取完整凭证 |
| `kiro_gateway/auth_cache.py` | 扩展方法支持 IDC 凭证参数 |

## 备注

- 数据库中已正确存储 `client_id_encrypted` 和 `client_secret_encrypted` 字段
- `database.py` 中的 `get_token_credentials()` 方法已存在，只是之前未被使用
- 此修复同时影响全局模式和多租户模式的 Token 刷新

---

# OAuth2 State 验证修复

## 问题描述

用户在使用 LinuxDo 或 GitHub OAuth2 登录时，回调页面显示 **"无效的 state 参数"** 错误。

这是因为原有实现使用 **Cookie** 存储 OAuth state 参数，在以下场景会失效：
1. 跨站请求时浏览器不发送 Cookie（SameSite 策略）
2. 用户使用隐私模式或禁用第三方 Cookie
3. OAuth 提供商重定向时 Cookie 丢失

## 根本原因

原有代码在 OAuth 回调时从 Cookie 读取 state：

```python
# 修复前（有问题）
cookie_state = request.cookies.get("oauth_state")
if not state or state != cookie_state:
    return HTMLResponse(content="无效的 state 参数", status_code=400)
```

## 修复方案

将 OAuth state 验证从 **Cookie 验证** 改为 **服务端验证**：

### `kiro_gateway/routes.py`

**LinuxDo OAuth2 回调**（第 2013-2017 行）：

```python
# 修复前
cookie_state = request.cookies.get("oauth_state")
if not state or state != cookie_state:
    return HTMLResponse(content="无效的 state 参数", status_code=400)

# 修复后
if not state or not user_manager.session.verify_oauth_state(state):
    return HTMLResponse(content="无效的 state 参数", status_code=400)
```

**GitHub OAuth2 回调**（第 2093-2097 行）：

```python
# 修复前
cookie_state = request.cookies.get("github_oauth_state")
if not state or state != cookie_state:
    return HTMLResponse(content="无效的 state 参数", status_code=400)

# 修复后
if not state or not user_manager.session.verify_oauth_state(state):
    return HTMLResponse(content="无效的 state 参数", status_code=400)
```

### `kiro_gateway/user_manager.py`

服务端 OAuth state 管理已实现（无需修改）：

```python
class UserSessionManager:
    def __init__(self):
        self._oauth_states: dict[str, int] = {}  # state -> timestamp

    def create_oauth_state(self) -> str:
        """Create a random state for OAuth2 CSRF protection."""
        state = secrets.token_urlsafe(32)
        self._oauth_states[state] = int(time.time())
        # Clean old states (> 10 minutes)
        cutoff = int(time.time()) - 600
        self._oauth_states = {k: v for k, v in self._oauth_states.items() if v > cutoff}
        return state

    def verify_oauth_state(self, state: str) -> bool:
        """Verify OAuth2 state parameter."""
        if state in self._oauth_states:
            del self._oauth_states[state]  # 一次性使用
            return True
        return False
```

## 服务端 State 验证优势

| 特性 | Cookie 验证 | 服务端验证 |
|------|------------|-----------|
| 跨站兼容性 | ❌ 受 SameSite 限制 | ✅ 不受影响 |
| 隐私模式支持 | ❌ 可能失效 | ✅ 正常工作 |
| 安全性 | ⚠️ 依赖客户端 | ✅ 服务端控制 |
| 一次性使用 | ❌ 需额外实现 | ✅ 内置支持 |
| 自动过期清理 | ❌ 需额外实现 | ✅ 10 分钟过期 |

## 受影响的文件

| 文件 | 修改类型 |
|------|---------|
| `kiro_gateway/routes.py` | OAuth2 回调 state 验证方式改为服务端验证 |

## 验证方法

1. 访问登录页面，点击 "LinuxDo 登录" 或 "GitHub 登录"
2. 完成 OAuth 授权
3. 回调应成功返回，不再显示 "无效的 state 参数" 错误

---

# 完整修改文件列表

| 文件 | 修改内容 |
|------|---------|
| `kiro_gateway/config.py` | 新增 `CLIENT_ID` 和 `CLIENT_SECRET` 环境变量配置 |
| `main.py` | 创建全局 AuthManager 时传递 IDC 凭证 |
| `kiro_gateway/token_allocator.py` | 使用 `get_token_credentials()` 获取完整 IDC 凭证 |
| `kiro_gateway/health_checker.py` | 使用 `get_token_credentials()` 获取完整 IDC 凭证 |
| `kiro_gateway/auth_cache.py` | 扩展 `get_or_create()` 方法支持 IDC 凭证参数 |
| `kiro_gateway/routes.py` | OAuth2 回调 state 验证改为服务端验证 |
