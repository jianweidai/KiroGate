# 实现计划：Custom API 增强功能

## 概述

按照设计文档，分四个模块依次实现：数据库层新增更新方法、路由层新增 PUT 接口、Token 分配器扩展 Pro+ 逻辑、前端页面新增编辑弹窗。测试文件与实现同步推进。

## 任务

- [x] 1. 数据库层：新增 `update_custom_api_account()` 方法
  - 在 `kiro_gateway/database.py` 的 `UserDatabase` 类中新增 `update_custom_api_account` 方法
  - 动态构建 `SET` 子句，仅更新调用方传入的非 `None` 字段
  - `api_key` 非空时重新加密后存储，为空字符串时跳过该字段
  - `WHERE id = ? AND user_id = ?` 保证用户隔离，返回 `True`/`False`
  - 使用 `self._lock` 保证线程安全
  - _需求：1.1、1.2、1.3_

  - [ ]* 1.1 为 `update_custom_api_account` 编写属性测试
    - **属性 1：update 用户隔离**
    - **验证：需求 1.1、1.3**

  - [ ]* 1.2 为 `update_custom_api_account` 编写属性测试
    - **属性 2：update round-trip**
    - **验证：需求 1.2**

  - [ ]* 1.3 为多模型字符串原样存储编写属性测试
    - **属性 6：多模型字符串原样存储**
    - **验证：需求 2.4**

  - [ ]* 1.4 编写单元测试
    - `test_update_custom_api_account_success`：正常更新流程
    - `test_update_custom_api_account_empty_api_key`：api_key 为空时保留原值
    - _需求：1.2_

- [x] 2. 路由层：新增 `PUT /user/api/custom-apis/{account_id}` 接口
  - 在 `kiro_gateway/routes.py` 中新增 PUT 路由，接受 JSON 请求体
  - 验证 `api_base` 必须匹配 `^https?://`，否则返回 422
  - 验证 `format` 必须为 `openai` 或 `claude`，否则返回 422
  - 调用 `db.update_custom_api_account()`，返回 `False` 时响应 404
  - 成功时返回 `{"success": true}`，HTTP 200
  - _需求：1.4、1.5、1.6、1.7、1.8、2.4_

  - [ ]* 2.1 为非法输入编写属性测试
    - **属性 3：非法输入返回 422**
    - **验证：需求 1.5、1.6**

  - [ ]* 2.2 为非所有者访问编写属性测试
    - **属性 4：非所有者返回 404**
    - **验证：需求 1.8**

  - [ ]* 2.3 编写单元测试
    - `test_put_route_exists`：路由存在性
    - `test_put_route_returns_200_on_success`：路由成功响应
    - _需求：1.4、1.7_

- [x] 3. 检查点 —— 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户反馈。

- [x] 4. Token 分配器：扩展 Pro+ 分支逻辑
  - 在 `kiro_gateway/token_allocator.py` 中新增模块级辅助函数 `_account_matches_model(account, model) -> bool`
  - 将 `model` 字段按逗号拆分、去除首尾空格后精确匹配；字段为空或 NULL 时返回 `False`
  - 修改 `SmartTokenAllocator.get_best_token()` 的 Pro+ 分支：合并 Pro+ Token 和绑定该模型的 Custom API 账号作为候选池
  - Pro+ Token 使用加权随机，Custom API 账号使用等权随机，合并后选择
  - 无 Pro+ 候选时回退到全量池（不抛出异常）
  - 在日志中记录候选来源（Pro+ Token 数量、Custom API 账号数量及所选类型）
  - _需求：3.1、3.2、3.3、3.4、3.5、3.6_

  - [ ]* 4.1 为模型字段解析与匹配编写属性测试
    - **属性 5：模型字段解析与匹配**
    - **验证：需求 2.1、2.2、3.4、3.5**

  - [ ]* 4.2 为 Pro+ 候选池选择编写属性测试
    - **属性 7：Pro+ 候选池选择**
    - **验证：需求 3.1、3.2、3.5**

  - [ ]* 4.3 为 Pro+ 回退逻辑编写属性测试
    - **属性 8：Pro+ 回退逻辑**
    - **验证：需求 3.3**

  - [ ]* 4.4 编写单元测试
    - `test_model_empty_string_matches_nothing`：空 model 字段 edge case
    - `test_model_null_matches_nothing`：NULL model 字段 edge case
    - `test_pro_plus_empty_model_excluded`：空 model 账号不进入 Pro+ 池
    - `test_pro_plus_logging`：日志记录验证
    - _需求：2.2、3.4、3.6_

- [x] 5. 前端页面：编辑弹窗与多模型 placeholder
  - 在 `kiro_gateway/pages.py` 的 `render_user_page` 中，为 Custom API 账号列表每行操作列新增"编辑"按钮
  - 新增编辑弹窗 HTML/JS，预填当前字段值（api_key 字段显示为空，placeholder 提示留空则不修改）
  - 更新添加弹窗和编辑弹窗的 Model 输入框 placeholder 为 `claude-sonnet-4-6, claude-opus-4-6`
  - 提交时调用 `PUT /user/api/custom-apis/{id}`，成功后刷新列表并关闭弹窗
  - _需求：1.9、1.10、2.3_

- [x] 6. 最终检查点 —— 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户反馈。

## 备注

- 标有 `*` 的子任务为可选测试任务，可跳过以加快 MVP 进度
- 每个任务均引用具体需求条款以保证可追溯性
- 属性测试使用 `hypothesis` 库，每个属性对应一个测试函数，位于 `tests/test_custom_api_enhancements.py`
- 数据库 schema 无需变更，`model` 字段语义变更在应用层处理
