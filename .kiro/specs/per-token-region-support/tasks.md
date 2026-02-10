# 实现计划: Per-Token Region Support

## 概述

本实现计划将 Token 级别的 AWS 区域支持功能分解为可执行的编码任务。每个任务都是增量的，构建在前一个任务的基础上。

## 任务

- [x] 1. 数据库层修改
  - [x] 1.1 修改 DonatedToken 数据模型，添加 region 属性
    - 在 `kiro_gateway/database.py` 中的 `DonatedToken` dataclass 添加 `region: str` 字段
    - 默认值为 'us-east-1'
    - _Requirements: 1.3_
  
  - [x] 1.2 修改数据库 schema，添加 region 字段
    - 在 `_init_db` 方法中添加 tokens 表的 region 字段迁移逻辑
    - 使用 `ALTER TABLE tokens ADD COLUMN region TEXT DEFAULT 'us-east-1'`
    - _Requirements: 1.1, 1.2_
  
  - [x] 1.3 修改 donate_token 方法，支持 region 参数
    - 添加 `region: str = "us-east-1"` 参数
    - 在 INSERT 语句中包含 region 字段
    - _Requirements: 2.4_
  
  - [x] 1.4 修改 get_token_credentials 方法，返回 region 信息
    - 在 SELECT 语句中包含 region 字段
    - 在返回的字典中添加 region 键
    - _Requirements: 3.2_
  
  - [x] 1.5 修改 _row_to_token 方法，处理 region 字段
    - 从数据库行中读取 region 字段
    - 兼容旧数据（region 可能不存在）
    - _Requirements: 1.3_

- [x] 2. Checkpoint - 数据库层验证
  - 确保所有数据库相关修改正确
  - 运行现有测试确保没有破坏性变更
  - 如有问题请询问用户

- [x] 3. Token 分配器修改
  - [x] 3.1 修改 _get_manager 方法，使用 Token 的 region
    - 从 credentials 中获取 region 值
    - 传递 region 给 KiroAuthManager 构造函数
    - 如果 region 不存在，使用默认值 'us-east-1'
    - _Requirements: 3.1, 3.3_
  
  - [ ]* 3.2 编写属性测试：Token 分配使用正确区域
    - **Property 2: Token 分配使用正确区域**
    - **Validates: Requirements 3.1, 3.3**

- [x] 4. API 端点修改
  - [x] 4.1 修改 user_donate_token 端点，支持 region 参数
    - 添加 `region: str = Form("us-east-1")` 参数
    - 验证 region 是否在支持列表中
    - 使用指定 region 创建 KiroAuthManager 进行验证
    - 将 region 传递给 user_db.donate_token
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 4.2 添加支持的区域常量列表
    - 在 routes.py 或 config.py 中定义 SUPPORTED_REGIONS
    - 包含 us-east-1, ap-southeast-1, eu-west-1
    - _Requirements: 2.1_
  
  - [ ]* 4.3 编写属性测试：Region 字段存储一致性
    - **Property 1: Region 字段存储一致性**
    - **Validates: Requirements 2.4, 3.2**
  
  - [ ]* 4.4 编写属性测试：默认区域行为
    - **Property 3: 默认区域行为**
    - **Validates: Requirements 2.2**

- [x] 5. Checkpoint - 后端功能验证
  - 确保 API 端点正确处理 region 参数
  - 运行测试验证功能
  - 如有问题请询问用户

- [x] 6. 前端界面修改
  - [x] 6.1 修改添加 Token 模态框，添加区域选择器
    - 在 `render_user_page` 函数的 donateModal 中添加区域选择下拉框
    - 包含支持的区域选项
    - 默认选中 us-east-1
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 6.2 修改 submitTokens JavaScript 函数，发送 region 参数
    - 获取选择的区域值
    - 在 FormData 中添加 region 字段
    - _Requirements: 4.4_
  
  - [x] 6.3 修改 Token 列表显示，添加区域列
    - 在用户 Token 表格中添加区域列
    - 显示每个 Token 的区域信息
    - _Requirements: 5.2_

- [x] 7. 管理界面修改
  - [x] 7.1 修改管理员 Token 列表 API，返回 region 信息
    - 在 get_all_tokens_with_users 方法中包含 region 字段
    - 在返回的字典中添加 region 键
    - _Requirements: 5.1_
  
  - [x] 7.2 修改管理员 Token 列表页面，显示区域列
    - 在 render_admin_page 的 Token 表格中添加区域列
    - _Requirements: 5.1_

- [x] 8. Final Checkpoint - 完整功能验证
  - 确保所有测试通过
  - 验证前端和后端集成正常
  - 如有问题请询问用户

## 注意事项

- 标记为 `*` 的任务是可选的测试任务，可以跳过以加快 MVP 开发
- 每个任务都引用了具体的需求以便追溯
- Checkpoint 任务用于验证阶段性成果
- 属性测试验证通用正确性属性
