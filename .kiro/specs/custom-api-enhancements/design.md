# 设计文档：Custom API 增强功能

## 概述

本文档描述 KiroGate Custom API 模块的三项增强功能的技术设计：

1. **编辑 Custom API 账号**：新增 `PUT /user/api/custom-apis/{account_id}` 接口及对应数据库方法，允许用户就地修改账号配置。
2. **多模型绑定**：将 `model` 字段从单一字符串扩展为逗号分隔的多模型列表，在应用层解析，无需数据库 schema 变更。
3. **Pro+ 模型轮询扩展**：修改 `SmartTokenAllocator.get_best_token()`，使绑定了 Pro+ 专属模型的 Custom API 账号与 Pro+ Kiro Token 共同参与候选池。

这三项功能相互独立，可以分别实现，但在 Token 分配逻辑中会协同工作。

---

## 架构

### 整体请求流

```
用户请求 (PUT /user/api/custom-apis/{id})
    ↓
kiro_gateway/routes.py  ← 新增 PUT 路由，验证字段
    ↓
kiro_gateway/database.py  ← 新增 update_custom_api_account()
    ↓
SQLite custom_api_accounts 表（model 字段存储逗号分隔字符串）

API 请求 (POST /v1/messages)
    ↓
kiro_gateway/routes.py → RequestHandler
    ↓
kiro_gateway/token_allocator.py  ← 修改 get_best_token()
    │
    ├── 若 Pro+ 模型：合并 Pro+ Token + 绑定该模型的 Custom API 账号
    └── 否则：合并全部活跃 Token + 全部活跃 Custom API 账号
```

### 模块变更范围

| 模块 | 变更类型 | 说明 |
|------|----------|------|
| `database.py` | 新增方法 | `update_custom_api_account()` |
| `routes.py` | 新增路由 | `PUT /user/api/custom-apis/{account_id}` |
| `token_allocator.py` | 修改逻辑 | Pro+ 分支纳入 Custom API 账号 |
| `pages.py` | 修改前端 | 编辑弹窗、多模型 placeholder |

---

## 组件与接口

### 1. Database 层：`update_custom_api_account()`

新增方法签名：

```python
def update_custom_api_account(
    self,
    account_id: int,
    user_id: int,
    name: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,   # 空字符串 → 不更新
    format: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> bool:
    """
    更新指定账号的字段（仅当 user_id 匹配时）。
    api_key 为空字符串时保留原值。
    返回 True 表示更新成功，False 表示账号不存在或不属于该用户。
    """
```

实现要点：
- 动态构建 `SET` 子句，只更新调用方传入的非 `None` 字段
- `api_key` 非空时重新加密后存储
- `WHERE id = ? AND user_id = ?` 保证用户隔离
- 使用 `self._lock` 保证线程安全

### 2. Router 层：`PUT /user/api/custom-apis/{account_id}`

```
PUT /user/api/custom-apis/{account_id}
Content-Type: application/json

{
  "name": "My API",
  "api_base": "https://api.example.com/v1",
  "api_key": "",          // 留空则不更新
  "format": "openai",
  "provider": "openai",
  "model": "claude-sonnet-4-6, claude-opus-4-6"
}
```

验证规则（与 POST 路由保持一致）：
- `api_base` 必须匹配 `^https?://`，否则返回 422
- `format` 必须为 `openai` 或 `claude`，否则返回 422
- 账号不属于当前用户时返回 404
- 成功时返回 `{"success": true}`

### 3. Token Allocator：Pro+ 分支扩展

当前逻辑（仅 Pro+ Kiro Token）：

```python
if requesting_pro_plus and active_kiro_tokens:
    pro_tokens = [t for t in active_kiro_tokens if t.opus_enabled]
    if pro_tokens:
        best = self._weighted_random_choice(pro_tokens)
        ...
```

新逻辑（Pro+ Token + 绑定该模型的 Custom API 账号）：

```python
if requesting_pro_plus:
    pro_tokens = [t for t in active_kiro_tokens if t.opus_enabled]
    pro_custom = [a for a in custom_api_accounts if _account_matches_model(a, model)]

    if pro_tokens or pro_custom:
        # Pro+ Token 加权随机 + Custom API 等权随机，合并后选择
        selected = _select_from_pro_plus_pool(pro_tokens, pro_custom)
        ...
        logger.info(f"Pro+ 轮询: {len(pro_tokens)} 个 Pro+ Token, {len(pro_custom)} 个 Custom API 账号")
        return selected
    else:
        # 回退：使用全部活跃 Token + 全部 Custom API 账号
        logger.warning(f"用户 {user_id} 无 Pro+ 候选，回退到全量池")
```

辅助函数：

```python
def _account_matches_model(account: dict, model: str) -> bool:
    """判断 Custom API 账号是否绑定了指定模型（逗号分隔，精确匹配，忽略首尾空格）。"""
    raw = (account.get("model") or "").strip()
    if not raw:
        return False
    return model in {m.strip() for m in raw.split(",")}
```

### 4. Frontend：编辑弹窗与多模型 placeholder

用户页面（`pages.py` 中的 `render_user_page`）需要：

- 在 Custom API 账号列表每行操作列新增"编辑"按钮
- 点击后弹出预填当前字段值的编辑弹窗（`api_key` 字段显示为空，placeholder 提示留空则不修改）
- Model 输入框的 placeholder 更新为 `claude-sonnet-4-6, claude-opus-4-6`（添加和编辑弹窗均需更新）
- 提交时调用 `PUT /user/api/custom-apis/{id}`，成功后刷新列表并关闭弹窗

---

## 数据模型

### `custom_api_accounts` 表（无 schema 变更）

```sql
CREATE TABLE IF NOT EXISTS custom_api_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    api_base TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'openai',
    provider TEXT,
    model TEXT,          -- 逗号分隔的模型名称列表，如 "claude-sonnet-4-6, claude-opus-4-6"
    status TEXT NOT NULL DEFAULT 'active',
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

`model` 字段语义变更（应用层处理，无需迁移）：
- 旧语义：单个模型名称字符串
- 新语义：英文逗号分隔的模型名称列表，每项去除首尾空格后精确匹配
- 空字符串或 NULL：不绑定任何模型，不参与任何 Pro+ 候选池

### 模型匹配规则

```python
# 解析示例
model_field = "claude-sonnet-4-6, claude-opus-4-6 "
models = {m.strip() for m in model_field.split(",")}
# → {"claude-sonnet-4-6", "claude-opus-4-6"}

# 匹配
"claude-sonnet-4-6" in models  # → True
"claude-haiku-4-5" in models   # → False
```

---

## 正确性属性

*属性（Property）是在系统所有合法执行路径上都应成立的特征或行为——本质上是对系统应做什么的形式化陈述。属性是人类可读规范与机器可验证正确性保证之间的桥梁。*


### 属性 1：update 用户隔离

*对于任意* Custom API 账号和任意用户，调用 `update_custom_api_account(account_id, user_id, ...)` 的返回值应当等于该账号是否属于该用户；且当账号不属于该用户时，数据库中的记录不应发生任何变化。

**验证：需求 1.1、1.3**

---

### 属性 2：update round-trip

*对于任意* 属于用户的 Custom API 账号，调用 `update_custom_api_account` 更新若干字段后，再通过 `get_custom_api_accounts_by_user` 查询，应当能读回所有被更新的字段值（api_key 以脱敏形式验证前缀）。

**验证：需求 1.2**

---

### 属性 3：非法输入返回 422

*对于任意* 不以 `http://` 或 `https://` 开头的 `api_base` 字符串，或任意不是 `openai`/`claude` 的 `format` 值，向 `PUT /user/api/custom-apis/{id}` 发送请求应当返回 HTTP 422。

**验证：需求 1.5、1.6**

---

### 属性 4：非所有者返回 404

*对于任意* 已登录用户，当请求更新不属于该用户的账号时，`PUT /user/api/custom-apis/{id}` 应当返回 HTTP 404，且数据库记录不变。

**验证：需求 1.8**

---

### 属性 5：模型字段解析与匹配

*对于任意* 逗号分隔的模型名称字符串（含任意首尾空格），`_account_matches_model(account, model)` 应当当且仅当 `model` 在去除空格后的模型集合中时返回 `True`；当 `model` 字段为空字符串或 `None` 时，对任意模型名称均返回 `False`。

**验证：需求 2.1、2.2、3.4、3.5**

---

### 属性 6：多模型字符串原样存储

*对于任意* 包含多个模型名称的逗号分隔字符串，通过 `add_custom_api_account` 或 `update_custom_api_account` 存储后，再通过查询接口读回的 `model` 字段应当与原始字符串完全一致（不拆分、不去重、不修改）。

**验证：需求 2.4**

---

### 属性 7：Pro+ 候选池选择

*对于任意* 用户的 Token 池和 Custom API 账号池，当请求的模型属于 `PRO_PLUS_MODELS` 且存在至少一个 Pro+ Token（`opus_enabled=True`）或至少一个绑定了该模型的 Custom API 账号时，`get_best_token` 返回的账号必须来自这两类候选之一，不得选择普通 Kiro Token 或未绑定该模型的 Custom API 账号。

**验证：需求 3.1、3.2、3.5**

---

### 属性 8：Pro+ 回退逻辑

*对于任意* 用户，当请求的模型属于 `PRO_PLUS_MODELS` 但既没有 Pro+ Token 也没有绑定该模型的 Custom API 账号时，`get_best_token` 应当从该用户的全部活跃 Token 和全部活跃 Custom API 账号中选择，而不是抛出 `NoTokenAvailable`。

**验证：需求 3.3**

---

## 错误处理

### Database 层

| 场景 | 处理方式 |
|------|----------|
| `update_custom_api_account` 账号不存在或不属于该用户 | 返回 `False`，不抛出异常 |
| `api_key` 加密失败 | 抛出异常，由调用方处理 |
| 数据库连接超时 | SQLite timeout=30s，超时后抛出异常 |

### Router 层

| 场景 | HTTP 状态码 | 响应体 |
|------|-------------|--------|
| 未登录 | 401 | `{"error": "未登录"}` |
| `api_base` 非法 URL | 422 | `{"error": "api_base 必须是合法的 HTTP/HTTPS URL"}` |
| `format` 非法值 | 422 | `{"error": "format 必须为 openai 或 claude"}` |
| 账号不属于当前用户 | 404 | `{"error": "账号不存在"}` |
| 请求体解析失败 | 400 | `{"error": "无效的请求体"}` |
| 成功 | 200 | `{"success": true}` |

### Token Allocator 层

| 场景 | 处理方式 |
|------|----------|
| Pro+ 模型但无任何候选 | 回退到全量池（不抛出异常） |
| 全量池也为空 | 抛出 `NoTokenAvailable` |
| `_account_matches_model` 解析异常 | 返回 `False`，记录 warning 日志 |

---

## 测试策略

### 双轨测试方法

本功能采用单元测试和基于属性的测试（Property-Based Testing）相结合的方式：

- **单元测试**：验证具体示例、边界情况和错误条件
- **属性测试**：通过随机生成输入验证普遍性属性

两者互补，共同提供全面覆盖。

### 属性测试配置

使用 `hypothesis` 库（项目已有依赖）。每个属性测试最少运行 100 次迭代。

每个属性测试必须包含注释标记：
```python
# Feature: custom-api-enhancements, Property {N}: {property_text}
```

**每个正确性属性对应一个属性测试**：

| 属性 | 测试函数 | 测试文件 |
|------|----------|----------|
| P1: update 用户隔离 | `test_update_user_isolation` | `tests/test_custom_api_enhancements.py` |
| P2: update round-trip | `test_update_round_trip` | 同上 |
| P3: 非法输入返回 422 | `test_invalid_input_returns_422` | 同上 |
| P4: 非所有者返回 404 | `test_non_owner_returns_404` | 同上 |
| P5: 模型字段解析与匹配 | `test_model_field_parsing` | 同上 |
| P6: 多模型字符串原样存储 | `test_multi_model_storage_roundtrip` | 同上 |
| P7: Pro+ 候选池选择 | `test_pro_plus_pool_selection` | 同上 |
| P8: Pro+ 回退逻辑 | `test_pro_plus_fallback` | 同上 |

### 单元测试覆盖

- `test_update_custom_api_account_success`：正常更新流程
- `test_update_custom_api_account_empty_api_key`：api_key 为空时保留原值
- `test_put_route_returns_200_on_success`：路由成功响应（需求 1.7）
- `test_put_route_exists`：路由存在性（需求 1.4）
- `test_model_empty_string_matches_nothing`：空 model 字段 edge case（需求 2.2）
- `test_model_null_matches_nothing`：NULL model 字段 edge case
- `test_pro_plus_empty_model_excluded`：空 model 账号不进入 Pro+ 池（需求 3.4）
- `test_pro_plus_logging`：日志记录验证（需求 3.6）

### 测试文件位置

```
KiroGate/tests/test_custom_api_enhancements.py
```
