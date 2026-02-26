# Implementation Plan: Custom API Support

## Overview

将 Custom API 账号管理功能集成到 KiroGate，包括数据库层、后端处理模块、路由层和前端 UI。实现步骤从数据库到 handler 模块，再到路由和 UI，最后完成请求路由集成。

## Tasks

- [x] 1. 数据库层：新增 custom_api_accounts 表和 CRUD 方法
  - [x] 1.1 在 `UserDatabase._init_db()` 中新增 `custom_api_accounts` 表的建表 SQL
    - 字段：id, user_id, name, api_base, api_key_encrypted, format, provider, model, status, success_count, fail_count, created_at
    - 添加 migration 检查（如表已存在则跳过）
    - _Requirements: US-1（保存到数据库）_
  - [x] 1.2 在 `UserDatabase` 中实现用户侧 CRUD 方法
    - `add_custom_api_account(user_id, name, api_base, api_key, format, provider, model) -> int`
    - `get_custom_api_accounts_by_user(user_id, page, page_size) -> list[dict]`（api_key 脱敏）
    - `get_active_custom_api_accounts_by_user(user_id) -> list[dict]`（api_key 已解密，供路由使用）
    - `update_custom_api_account_status(account_id, user_id, status)`
    - `delete_custom_api_account(account_id, user_id)`
    - `increment_custom_api_success(account_id)` / `increment_custom_api_fail(account_id)`
    - api_key 使用现有 `_encrypt_token()` / `_decrypt_token()` 加密存储
    - _Requirements: US-1, US-3, US-4, NFR（加密存储）_
  - [x] 1.3 在 `UserDatabase` 中实现 Admin CRUD 方法
    - `admin_get_all_custom_api_accounts(page, page_size) -> list[dict]`（含 username）
    - `admin_delete_custom_api_account(account_id)`
    - `admin_update_custom_api_account_status(account_id, status)`
    - _Requirements: US-6_
  - [ ]* 1.4 为数据库 CRUD 方法编写单元测试
    - 测试文件：`KiroGate/tests/test_custom_api_database.py`
    - 测试 add/get/update/delete 的基本功能
    - 测试 api_key 加密存储和解密读取
    - 测试 user_id 隔离（用户只能操作自己的账号）
    - _Requirements: US-1, US-3, US-4, NFR_

- [x] 2. Custom API Handler 模块
  - [x] 2.1 创建 `KiroGate/kiro_gateway/custom_api/__init__.py`
    - 空文件，标记为 Python 包
    - _Requirements: US-5_
  - [x] 2.2 创建 `KiroGate/kiro_gateway/custom_api/converter.py`
    - 从 `amq2api/src/custom_api/converter.py` 迁移，将 `from src.models` 改为 `from kiro_gateway.models`（或项目实际 models 路径）
    - 保留所有核心函数：`convert_claude_to_openai_request`, `convert_openai_stream_to_claude`, `convert_openai_error_to_claude`, `_clean_claude_request_for_azure` 等
    - 移除对 `src.processing.model_mapper` 的依赖（KiroGate 无此模块）
    - _Requirements: US-5（format=openai 转换，provider=azure 清理）_
  - [ ]* 2.3 为 converter 编写属性测试
    - 测试文件：`KiroGate/tests/test_custom_api_converter.py`
    - **Property 1: OpenAI→Claude 流转换幂等性** — 任意合法 OpenAI SSE 事件序列，转换后的 Claude SSE 事件数量 ≥ 原始事件数量（不丢失内容）
    - **Validates: Requirements US-5（format=openai 响应转换）**
    - **Property 2: Azure 清理不增加字段** — 经过 `_clean_claude_request_for_azure` 处理后，返回的 dict 中不包含 `context_management`、`betas` 等不支持字段
    - **Validates: Requirements US-5（provider=azure）**
  - [x] 2.4 创建 `KiroGate/kiro_gateway/custom_api/handler.py`
    - 从 `amq2api/src/custom_api/handler.py` 迁移，适配 KiroGate 的 import 路径
    - 主入口：`handle_custom_api_request(account: dict, claude_req, response_format: str) -> AsyncGenerator[str, None]`
    - 移除对 `src.auth.account_manager.set_account_cooldown` 和 `src.processing.usage_tracker` 的依赖（替换为 KiroGate 的 `user_db.increment_custom_api_fail/success`）
    - 保留 429 重试逻辑、超时处理、连接错误处理
    - _Requirements: US-5（请求路由、错误处理）_
  - [ ]* 2.5 为 handler 编写单元测试
    - 测试文件：`KiroGate/tests/test_custom_api_handler.py`
    - 使用 `unittest.mock` mock httpx 请求，测试 format=openai 和 format=claude 两条路径
    - 测试错误响应（4xx/5xx）返回合法的 Claude 错误格式
    - _Requirements: US-5_

- [x] 3. Checkpoint — 确保模块可导入，所有测试通过
  - 确保 `from kiro_gateway.custom_api.converter import convert_claude_to_openai_request` 可正常导入
  - 确保 `from kiro_gateway.custom_api.handler import handle_custom_api_request` 可正常导入
  - 运行 `pytest KiroGate/tests/test_custom_api_database.py KiroGate/tests/test_custom_api_converter.py KiroGate/tests/test_custom_api_handler.py -v`，确保所有测试通过

- [x] 4. 请求路由层：扩展 token_allocator 和 request_handler
  - [x] 4.1 修改 `token_allocator.py`：扩展 `SmartTokenAllocator.get_best_token()` 返回类型
    - 修改返回类型为 `Tuple[str, Any, Optional[KiroAuthManager]]`，其中第一个元素为 `'kiro'` 或 `'custom_api'`
    - 在 `get_best_token()` 中，获取用户的 active custom_api_accounts，与 kiro tokens 合并后随机选择
    - 若选中 custom_api 账号，返回 `('custom_api', account_dict, None)`
    - 若选中 kiro token，返回 `('kiro', token, manager)`（保持现有逻辑）
    - _Requirements: US-5, NFR（两者都参与随机选择）_
  - [ ]* 4.2 为路由逻辑编写属性测试
    - 测试文件：`KiroGate/tests/test_custom_api_routing.py`
    - **Property 3: 路由覆盖性** — 当用户同时有 N 个 kiro token 和 M 个 custom_api 账号时，多次调用 `get_best_token()` 后，两类账号都有机会被选中（概率 > 0）
    - **Validates: Requirements NFR（两者都参与随机选择）**
    - **Property 4: 无账号时抛出异常** — 当用户没有任何 active token 和 custom_api 账号时，`get_best_token()` 必须抛出 `NoTokenAvailable`
    - **Validates: Requirements NFR（无可用账号返回 403）**
  - [x] 4.3 修改 `request_handler.py`：新增 custom_api 分发路径
    - 在 `handle_request()` 中，根据 `get_best_token()` 返回的 account_type 分发
    - `account_type == 'custom_api'`：解密 api_key，调用 `handle_custom_api_request()`，成功/失败后调用 `increment_custom_api_success/fail()`
    - `account_type == 'kiro'`：现有逻辑不变
    - _Requirements: US-5_

- [x] 5. API 路由层：新增用户和 Admin 路由
  - [x] 5.1 在 `routes.py` 中新增用户侧 Custom API 路由
    - `GET /user/api/custom-apis`：获取当前用户的 custom_api 账号列表（分页，api_key 脱敏）
    - `POST /user/api/custom-apis`：添加账号，校验 api_base 为合法 HTTP/HTTPS URL、api_key 非空、format 为 openai/claude
    - `PATCH /user/api/custom-apis/{id}/status`：启用/禁用（校验 account 属于当前用户）
    - `DELETE /user/api/custom-apis/{id}`：删除（校验 account 属于当前用户）
    - _Requirements: US-1, US-2, US-3, US-4, NFR（URL 格式校验）_
  - [x] 5.2 在 `routes.py` 中新增 Admin Custom API 路由
    - `GET /admin/api/custom-apis`：获取所有账号（分页，含 username）
    - `DELETE /admin/api/custom-apis/{id}`：删除任意账号
    - `PATCH /admin/api/custom-apis/{id}/status`：启用/禁用任意账号
    - _Requirements: US-6_
  - [ ]* 5.3 为 API 路由编写单元测试
    - 测试文件：`KiroGate/tests/test_custom_api_routes.py`
    - 使用 FastAPI `TestClient` 测试各路由的正常和异常情况
    - 测试 api_base URL 格式校验（非法 URL 返回 422）
    - 测试用户隔离（用户 A 不能删除用户 B 的账号，返回 404）
    - _Requirements: US-1, US-3, US-4, US-6, NFR_

- [x] 6. 前端 UI：在 pages.py 中新增 Custom API 区块
  - [x] 6.1 在 `pages.py` 中新增 Custom API 账号列表和添加弹窗的 HTML/JS
    - 在现有 Token 列表下方新增独立的「Custom API 账号」区块
    - 列表表格：name/api_base、format、provider、model、状态（active/disabled）、操作（启用/禁用、删除）
    - api_key 脱敏显示（前4位 + `****`）
    - 「添加 Custom API」按钮，点击弹出 modal
    - _Requirements: US-1, US-2, US-3, US-4_
  - [x] 6.2 在 `pages.py` 中实现添加弹窗的表单和 JS 交互逻辑
    - 表单字段：name（可选）、api_base（必填）、api_key（必填）、format（select: openai/claude）、provider（可选）、model（可选）
    - 提交后调用 `POST /user/api/custom-apis`，成功后刷新列表
    - 启用/禁用按钮调用 `PATCH /user/api/custom-apis/{id}/status`
    - 删除按钮调用 `DELETE /user/api/custom-apis/{id}`，带确认提示
    - _Requirements: US-1, US-2, US-3, US-4_

- [x] 7. Final Checkpoint — 确保所有测试通过，功能完整
  - 运行 `pytest KiroGate/tests/ -v -k "custom_api"`，确保所有 custom_api 相关测试通过
  - 确认请求路由逻辑：用户同时有 kiro token 和 custom_api 账号时，两者都参与随机选择
  - 确认 api_key 加密存储，列表接口返回脱敏数据

## Notes

- 标有 `*` 的子任务为可选测试任务，可跳过以加快 MVP 进度
- converter.py 和 handler.py 从 amq2api 迁移时，重点关注 import 路径适配（`src.models` → `kiro_gateway.models` 或实际路径）
- token_allocator 修改需保持向后兼容，现有 kiro token 路径逻辑不变
- 所有测试文件放在 `KiroGate/tests/` 目录，使用 pytest + hypothesis
