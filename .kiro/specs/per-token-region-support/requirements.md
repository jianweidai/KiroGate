# 需求文档

## 简介

本功能为 KiroGate 添加 Token 级别的 AWS 区域支持。目前系统使用全局配置的 AWS 区域（默认 us-east-1），但用户可能拥有不同区域的 Kiro 账号（如 ap-southeast-1）。本功能允许为每个 Token 单独配置区域，在请求时自动使用该 Token 对应的区域进行 API 调用。

## 术语表

- **Token**: 用户捐赠的 Kiro refresh token，用于获取 access token 进行 API 调用
- **Region**: AWS 区域标识符，如 us-east-1、ap-southeast-1、eu-west-1
- **KiroAuthManager**: 负责 Token 刷新和 API 认证的管理器类
- **TokenAllocator**: 智能 Token 分配器，负责选择最优 Token 处理请求
- **UserDatabase**: 用户系统数据库管理器，管理用户、Token、API Key 等数据

## 需求

### 需求 1：数据库支持 Token 区域字段

**用户故事：** 作为系统管理员，我希望数据库能存储每个 Token 的区域信息，以便系统能够持久化保存 Token 的区域配置。

#### 验收标准

1. THE UserDatabase SHALL 在 tokens 表中包含 region 字段，默认值为 'us-east-1'
2. WHEN 数据库初始化时，THE UserDatabase SHALL 自动为现有 tokens 表添加 region 字段（如果不存在）
3. THE DonatedToken 数据模型 SHALL 包含 region 属性

### 需求 2：Token 添加时支持区域选择

**用户故事：** 作为用户，我希望在添加 Token 时能够选择区域，以便我可以添加不同区域的 Kiro 账号。

#### 验收标准

1. WHEN 用户通过 API 添加 Token 时，THE 系统 SHALL 接受可选的 region 参数
2. IF region 参数未提供，THEN THE 系统 SHALL 使用默认值 'us-east-1'
3. WHEN 验证 Token 时，THE 系统 SHALL 使用指定的 region 创建 KiroAuthManager
4. THE donate_token 方法 SHALL 将 region 值存储到数据库

### 需求 3：Token 分配时使用正确区域

**用户故事：** 作为系统，我希望在分配 Token 时使用该 Token 配置的区域，以便 API 请求能够正确路由到对应的 AWS 区域。

#### 验收标准

1. WHEN TokenAllocator 创建 KiroAuthManager 时，THE 系统 SHALL 使用 Token 存储的 region 值
2. THE get_token_credentials 方法 SHALL 返回 Token 的 region 信息
3. WHEN Token 的 region 与全局配置不同时，THE 系统 SHALL 使用 Token 的 region 进行 API 调用

### 需求 4：前端支持区域选择

**用户故事：** 作为用户，我希望在前端界面添加 Token 时能够选择区域，以便我可以方便地配置不同区域的 Token。

#### 验收标准

1. WHEN 用户在前端添加 Token 时，THE 界面 SHALL 显示区域选择器
2. THE 区域选择器 SHALL 包含支持的 AWS 区域列表（us-east-1、ap-southeast-1、eu-west-1 等）
3. THE 区域选择器 SHALL 默认选中 'us-east-1'
4. WHEN 用户提交 Token 时，THE 前端 SHALL 将选择的区域发送到后端 API

### 需求 5：管理界面显示 Token 区域

**用户故事：** 作为管理员，我希望在管理界面能够查看每个 Token 的区域信息，以便我可以了解系统中 Token 的区域分布。

#### 验收标准

1. WHEN 管理员查看 Token 列表时，THE 界面 SHALL 显示每个 Token 的区域信息
2. WHEN 用户查看自己的 Token 列表时，THE 界面 SHALL 显示每个 Token 的区域信息
