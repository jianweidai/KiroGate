# Custom API Support Requirements

## Overview

在 KiroGate 用户 Token 界面中，增加添加 Custom API 账号的功能。用户可以配置第三方 OpenAI 兼容或 Claude 兼容的 API 端点，KiroGate 将这些账号纳入请求路由池，与 Kiro token 账号并列使用。

## User Stories

### US-1: 添加 Custom API 账号

**作为** 已登录用户
**我希望** 在 Token 管理界面添加一个 Custom API 账号
**以便** 我的 API key 请求可以路由到我配置的第三方 API 端点

**验收标准：**
- [ ] 用户 Token 界面有「添加 Custom API」入口（按钮）
- [ ] 表单包含以下字段：
  - `api_base`：API 基础 URL（必填，如 `https://api.openai.com`）
  - `api_key`：API 密钥（必填）
  - `format`：格式类型（必填，选项：`openai` / `claude`）
  - `provider`：提供商（可选，如 `azure`，默认空）
  - `model`：指定模型（可选，留空则使用请求中的模型名）
  - `name`：账号备注名（可选）
- [ ] 提交后账号保存到数据库 `custom_api_accounts` 表
- [ ] 保存成功后在列表中显示新账号

### US-2: 查看 Custom API 账号列表

**作为** 已登录用户
**我希望** 查看我添加的所有 Custom API 账号
**以便** 了解当前配置状态

**验收标准：**
- [ ] 列表显示账号的 name/api_base（脱敏显示 api_key）、format、provider、model、状态
- [ ] 支持分页（与现有 token 列表一致）

### US-3: 删除 Custom API 账号

**作为** 已登录用户
**我希望** 删除不再需要的 Custom API 账号
**以便** 清理配置

**验收标准：**
- [ ] 每条账号有删除按钮
- [ ] 删除后从列表移除，不再参与请求路由

### US-4: 启用/禁用 Custom API 账号

**作为** 已登录用户
**我希望** 临时禁用某个 Custom API 账号而不删除
**以便** 灵活控制路由

**验收标准：**
- [ ] 每条账号有启用/禁用开关
- [ ] 禁用后该账号不参与请求路由

### US-5: 请求路由到 Custom API

**作为** API 使用者
**我希望** 使用我的 `sk-xxx` API key 发起请求时，系统能路由到我配置的 Custom API
**以便** 透明地使用第三方 API

**验收标准：**
- [ ] 当用户有可用的 Custom API 账号时，请求可以路由到 Custom API
- [ ] `format=openai`：将 Anthropic 格式请求转换为 OpenAI 格式，响应转换回 Anthropic SSE 格式
- [ ] `format=claude`：将请求透传（或做必要清理后）转发到目标 API
- [ ] `provider=azure`：对请求做 Azure 特殊清理（移除不支持字段、处理 thinking 块）
- [ ] 支持 thinking 模式（与 amq2api 实现一致）
- [ ] 请求失败时返回合适的错误响应

### US-6: Admin 管理 Custom API 账号

**作为** 管理员
**我希望** 在 Admin 界面查看和管理所有用户的 Custom API 账号
**以便** 监控和维护

**验收标准：**
- [ ] Admin 界面可以查看所有 Custom API 账号（含用户信息）
- [ ] Admin 可以删除任意账号
- [ ] Admin 可以启用/禁用任意账号

## Non-Functional Requirements

- `api_key` 存储时必须加密（使用现有的 `TOKEN_ENCRYPT_KEY`）
- Custom API 账号与现有 Kiro token 账号独立存储（新建 `custom_api_accounts` 表）
- 请求路由逻辑：用户同时有 Kiro token 和 Custom API 账号时，两者都参与随机选择
- 错误处理：Custom API 请求失败时，记录失败次数，不影响其他账号

## Out of Scope

- Custom API 账号的健康检查
- Custom API 账号的权重配置
- 批量导入 Custom API 账号
