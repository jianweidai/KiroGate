# 需求文档

## 简介

本功能为 KiroGate 的 Custom API 模块新增三项增强：

1. **编辑 Custom API 账号**：允许用户修改已有账号的各字段（name、api_base、api_key、format、provider、model），无需删除后重建。
2. **Custom API 账号绑定多个模型**：将 `model` 字段从单一字符串扩展为逗号分隔的多模型字符串，使一个账号可同时绑定多个模型。
3. **Custom API 与 Pro+ Token 按模型轮询**：当请求的模型属于 `PRO_PLUS_MODELS` 时，绑定了该模型的 Custom API 账号与 Pro+ Kiro Token 共同参与随机轮询。

## 词汇表

- **Custom_API_Account**：用户在 `custom_api_accounts` 表中配置的第三方 API 账号记录，包含 api_base、api_key、format、provider、model 等字段。
- **Pro_Plus_Model**：属于 `PRO_PLUS_MODELS` 集合的模型（如 `claude-sonnet-4-6`、`claude-opus-4-6`），需要 `opus_enabled=True` 的 Kiro Token 或绑定了该模型的 Custom API 账号才能处理。
- **Pro_Plus_Token**：`opus_enabled=True` 且 `status='active'` 的 Kiro Token。
- **Token_Allocator**：`SmartTokenAllocator`，负责为每次请求选择最优的 Kiro Token 或 Custom API 账号。
- **Model_List**：Custom_API_Account 的 `model` 字段中以英文逗号分隔的模型名称列表，每个名称去除首尾空格后进行匹配。
- **Router**：FastAPI 路由层，位于 `kiro_gateway/routes.py`，负责暴露 REST 接口。
- **Database**：`UserDatabase`，位于 `kiro_gateway/database.py`，负责所有持久化操作。
- **Frontend**：用户控制台页面，由 `kiro_gateway/pages.py` 中的 `render_user_page` 生成。

---

## 需求

### 需求 1：编辑 Custom API 账号

**用户故事：** 作为已登录用户，我希望能够编辑已有的 Custom API 账号字段，以便在不删除重建的情况下修正配置错误或更新密钥。

#### 验收标准

1. THE Database SHALL 提供 `update_custom_api_account(account_id, user_id, **fields)` 方法，支持更新 name、api_base、api_key、format、provider、model 字段，且仅当 `user_id` 匹配时才执行更新。
2. WHEN 调用 `update_custom_api_account` 且 `account_id` 与 `user_id` 均匹配时，THE Database SHALL 将提供的字段持久化到数据库，并返回 `True`。
3. WHEN 调用 `update_custom_api_account` 且 `account_id` 不属于该 `user_id` 时，THE Database SHALL 不修改任何记录，并返回 `False`。
4. THE Router SHALL 提供 `PUT /user/api/custom-apis/{account_id}` 接口，接受 JSON 请求体，包含 name、api_base、api_key、format、provider、model 字段（api_key 为空字符串时保留原值不更新）。
5. WHEN `PUT /user/api/custom-apis/{account_id}` 请求中 `api_base` 不是合法的 HTTP/HTTPS URL 时，THE Router SHALL 返回 HTTP 422 及描述性错误信息。
6. WHEN `PUT /user/api/custom-apis/{account_id}` 请求中 `format` 不是 `openai` 或 `claude` 时，THE Router SHALL 返回 HTTP 422 及描述性错误信息。
7. WHEN `PUT /user/api/custom-apis/{account_id}` 请求成功时，THE Router SHALL 返回 HTTP 200 及 `{"success": true}`。
8. WHEN `PUT /user/api/custom-apis/{account_id}` 请求中账号不属于当前用户时，THE Router SHALL 返回 HTTP 404。
9. THE Frontend SHALL 在 Custom API 账号列表的每行操作列中提供"编辑"按钮，点击后弹出预填当前字段值的编辑弹窗（api_key 字段显示为空，提示用户留空则不修改）。
10. WHEN 用户在编辑弹窗中提交时，THE Frontend SHALL 调用 `PUT /user/api/custom-apis/{account_id}` 接口，成功后刷新列表并关闭弹窗。

---

### 需求 2：Custom API 账号绑定多个模型

**用户故事：** 作为已登录用户，我希望一个 Custom API 账号能绑定多个模型名称，以便该账号可以响应多种模型的请求。

#### 验收标准

1. THE Database SHALL 将 `custom_api_accounts.model` 字段解释为以英文逗号分隔的模型名称列表，每个名称在比较前去除首尾空格。
2. WHEN `model` 字段为空字符串或 NULL 时，THE Database SHALL 将其视为"不绑定任何模型"。
3. THE Frontend SHALL 在添加和编辑弹窗的 Model 输入框中，通过 placeholder 提示用户可输入多个模型（如 `claude-sonnet-4-6, claude-opus-4-6`）。
4. WHEN 用户提交包含多个模型的 Custom API 账号时，THE Router SHALL 将完整的逗号分隔字符串原样存储，不做拆分或去重。
5. THE Token_Allocator SHALL 在判断某 Custom_API_Account 是否绑定了指定模型时，将 `model` 字段按逗号拆分并逐项去除空格后进行精确匹配。

---

### 需求 3：Custom API 与 Pro+ Token 按模型轮询

**用户故事：** 作为已登录用户，我希望绑定了 Pro+ 专属模型的 Custom API 账号能与 Pro+ Kiro Token 一起参与轮询，以便充分利用我配置的所有后端资源。

#### 验收标准

1. WHEN 请求的模型属于 `PRO_PLUS_MODELS` 且用户存在 Pro_Plus_Token 或绑定了该模型的 Custom_API_Account 时，THE Token_Allocator SHALL 仅从这两类候选中随机选择，不使用普通 Kiro Token。
2. WHEN 请求的模型属于 `PRO_PLUS_MODELS` 且用户同时拥有 Pro_Plus_Token 和绑定了该模型的 Custom_API_Account 时，THE Token_Allocator SHALL 将两类候选合并后随机选择（Pro_Plus_Token 使用加权随机，Custom_API_Account 使用等权随机）。
3. WHEN 请求的模型属于 `PRO_PLUS_MODELS` 且用户没有 Pro_Plus_Token 也没有绑定该模型的 Custom_API_Account 时，THE Token_Allocator SHALL 回退到使用用户的全部活跃 Kiro Token 和全部活跃 Custom_API_Account 进行选择。
4. WHEN Custom_API_Account 的 `model` 字段为空或 NULL 时，THE Token_Allocator SHALL 不将该账号纳入任何 Pro+ 模型的候选池。
5. WHEN Custom_API_Account 的 `model` 字段包含请求模型名称（精确匹配，忽略首尾空格）时，THE Token_Allocator SHALL 将该账号纳入该模型的 Pro+ 候选池。
6. THE Token_Allocator SHALL 在日志中记录 Pro+ 轮询时的候选来源（Pro_Plus_Token 数量、Custom_API_Account 数量及所选账号类型）。
