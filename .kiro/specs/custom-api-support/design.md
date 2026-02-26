# Custom API Support - Technical Design

## Architecture Overview

```
User API Key Request (sk-xxx)
    ↓
routes.py: verify_api_key()
    ↓
request_handler.py: handle_request()
    ↓
token_allocator.py: get_account_for_user()  ← 扩展：同时考虑 custom_api_accounts
    ↓ (if custom api account selected)
kiro_gateway/custom_api/handler.py: handle_custom_api_request()
    ↓
  [format=openai] → converter.py: convert_anthropic_to_openai() → OpenAI API
  [format=claude]  → 透传/清理 → Claude-compatible API
    ↓
SSE Response → Client
```

## 1. Database Layer

### 新表：`custom_api_accounts`

```sql
CREATE TABLE IF NOT EXISTS custom_api_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    api_base TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'openai',   -- 'openai' | 'claude'
    provider TEXT,                            -- 'azure' | null
    model TEXT,
    status TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'disabled'
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

加密方式：复用现有 `encrypt_token()` / `decrypt_token()` 函数（Fernet 对称加密，密钥来自 `TOKEN_ENCRYPT_KEY`）。

### database.py 新增函数

```python
def create_custom_api_accounts_table(conn)

def add_custom_api_account(conn, user_id, name, api_base, api_key, format, provider, model) -> int
def get_custom_api_accounts_by_user(conn, user_id, page, page_size) -> list[dict]
def get_active_custom_api_accounts_by_user(conn, user_id) -> list[dict]
def update_custom_api_account_status(conn, account_id, user_id, status)
def delete_custom_api_account(conn, account_id, user_id)
def increment_custom_api_success(conn, account_id)
def increment_custom_api_fail(conn, account_id)

# Admin
def admin_get_all_custom_api_accounts(conn, page, page_size) -> list[dict]
def admin_delete_custom_api_account(conn, account_id)
def admin_update_custom_api_account_status(conn, account_id, status)
```

## 2. Custom API Handler Module

新建 `KiroGate/kiro_gateway/custom_api/` 模块，从 amq2api 迁移并适配：

```
KiroGate/kiro_gateway/custom_api/
├── __init__.py
├── converter.py    # Anthropic ↔ OpenAI 格式转换（从 amq2api 迁移适配）
└── handler.py      # 请求处理入口
```

### 关键适配点

amq2api 的入口是 Claude 格式（`/v1/messages`），KiroGate 的 `request_handler.py` 在调用前已经将 OpenAI 格式转换为 Anthropic 格式（`ClaudeRequest`）。因此 custom_api handler 的输入统一为 `ClaudeRequest`（Anthropic 格式），与 amq2api 一致，无需额外适配。

### handler.py 主入口

```python
async def handle_custom_api_request(
    request: ClaudeRequest,
    account: dict,          # custom_api_accounts 表的一行记录（api_key 已解密）
    response_format: str,   # 'anthropic' | 'openai'（由调用方传入）
) -> AsyncGenerator[str, None]:
    """
    根据 account['format'] 分发：
    - format='openai': handle_openai_format_stream()
    - format='claude': handle_claude_format_stream()
    """
```

### converter.py 主要函数（从 amq2api 迁移）

```python
def convert_anthropic_to_openai_request(request: ClaudeRequest, account: dict) -> dict
def convert_openai_stream_chunk_to_anthropic(chunk: str, state: dict) -> list[str]
def clean_request_for_azure(request: ClaudeRequest) -> ClaudeRequest
```

### Thinking 支持

与 amq2api 完全一致：
- `format=openai`：在 system prompt 注入 `THINKING_HINT`，响应流中解析 `<thinking>` 标签转换为 Anthropic thinking content block
- `format=claude`：直接传递 thinking 参数
- `provider=azure`：调用 `clean_request_for_azure()` 清理不支持字段

## 3. Request Routing Layer

### token_allocator.py 修改

扩展账号选择逻辑，同时考虑 Kiro token 和 Custom API 账号：

```python
async def get_account_for_user(user_id: int, conn) -> tuple[str, dict]:
    """
    Returns: (account_type, account_data)
    account_type: 'kiro' | 'custom_api'
    """
    kiro_tokens = get_active_tokens_by_user(conn, user_id)
    custom_accounts = get_active_custom_api_accounts_by_user(conn, user_id)

    all_accounts = (
        [('kiro', t) for t in kiro_tokens] +
        [('custom_api', a) for a in custom_accounts]
    )

    if not all_accounts:
        raise NoAvailableTokenError()

    return random.choice(all_accounts)
```

### request_handler.py 修改

在 `handle_request()` 中，根据 `account_type` 分发：

```python
if account_type == 'kiro':
    # 现有逻辑不变
    ...
elif account_type == 'custom_api':
    account['api_key'] = decrypt_token(account['api_key_encrypted'])
    async for chunk in handle_custom_api_request(claude_request, account, response_format):
        yield chunk
```

## 4. Frontend UI

### pages.py 修改

在现有 Token 列表下方新增独立的「Custom API 账号」区块：

- 「添加 Custom API」按钮
- Custom API 账号列表（表格：name/api_base、format、provider、model、状态、操作）
- 添加弹窗（字段：name、api_base、api_key、format、provider、model）

api_key 在列表中脱敏显示（只显示前4位 + `****`）。

## 5. API Routes

### 用户路由（新增到 routes.py）

```
GET    /user/api/custom-apis              # 获取列表（分页）
POST   /user/api/custom-apis              # 添加账号
PATCH  /user/api/custom-apis/{id}/status  # 启用/禁用
DELETE /user/api/custom-apis/{id}         # 删除
```

### Admin 路由（新增到 routes.py）

```
GET    /admin/api/custom-apis             # 获取所有账号（分页）
DELETE /admin/api/custom-apis/{id}        # 删除
PATCH  /admin/api/custom-apis/{id}/status # 启用/禁用
```

## 6. Files to Create/Modify

### 新建文件
- `KiroGate/kiro_gateway/custom_api/__init__.py`
- `KiroGate/kiro_gateway/custom_api/converter.py`
- `KiroGate/kiro_gateway/custom_api/handler.py`

### 修改文件
- `KiroGate/kiro_gateway/database.py` — 新增表和 CRUD 函数
- `KiroGate/kiro_gateway/token_allocator.py` — 扩展账号选择逻辑
- `KiroGate/kiro_gateway/request_handler.py` — 新增 custom_api 分发路径
- `KiroGate/kiro_gateway/routes.py` — 新增用户和 Admin API 路由
- `KiroGate/kiro_gateway/pages.py` — 新增 Custom API UI 区块

## 7. Error Handling

- `api_base` URL 格式校验（必须是有效 HTTP/HTTPS URL）
- `api_key` 不能为空
- `format` 只接受 `openai` / `claude`
- Custom API 请求失败：记录 fail_count，返回 502 错误给客户端
- 用户无可用账号（Kiro token 和 Custom API 都没有）：返回 403
