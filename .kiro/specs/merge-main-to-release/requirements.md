# 需求文档：合并 main 分支到 release 分支

## 简介

KiroGate 项目的 `main` 分支和 `release` 分支从 commit `21af4ba` 分叉后各自独立发展。两个分支在 Thinking Mode 和 WebSearch 两个核心功能上有不同的实现方式。本次合并的目标是将 main 分支的所有功能融合到 release 分支，对 Thinking Mode 和 WebSearch 采用精心设计的融合策略，同时引入 main 分支独有的新功能。

## 术语表

- **KiroGate**: 本项目，一个将 Claude API 请求转换为 Amazon Q / Gemini / 自定义 API 请求的代理服务
- **Thinking_Mode**: 一种扩展思考功能，将 Kiro API 返回的 `<thinking>` 标签解析为 Anthropic Extended Thinking 格式
- **KiroThinkingTagParser**: main 分支中独立的 `<thinking>` 标签增量解析器类，位于 `thinking_parser.py`
- **ThinkingStreamHandler**: release 分支中嵌入在 `streaming.py` 中的思考模式处理器
- **WebSearch**: 网页搜索功能，通过 MCP API 执行搜索并将结果注入对话上下文
- **Buffered_Streaming**: release 分支中用于 `/cc/v1` 端点的缓冲流处理模块
- **SSE**: Server-Sent Events，服务器推送事件流协议
- **Fusion_Strategy**: 本次合并采用的融合策略，从两个分支中选取各自最优实现进行组合

## 需求

### 需求 1：Thinking Mode 解析器融合

**用户故事：** 作为开发者，我希望将两个分支的 Thinking Mode 实现融合为一个统一的高质量实现，以便获得更好的代码组织和更强的功能。

#### 验收标准

1. THE KiroGate SHALL 使用 main 分支的 `thinking_parser.py` 中的 `KiroThinkingTagParser` 作为基础解析器
2. WHEN 解析 `<thinking>` 标签时，THE KiroThinkingTagParser SHALL 检测并跳过被引号包裹的假标签
3. WHEN 响应以 `<thinking>` 标签开头时，THE KiroThinkingTagParser SHALL 将内容解析为 thinking 片段；否则进入直通模式
4. WHEN 流结束且 thinking 块未正常关闭时，THE KiroThinkingTagParser SHALL 将缓冲区剩余内容作为 thinking 内容输出

### 需求 2：Thinking Mode 注入策略融合

**用户故事：** 作为开发者，我希望 Thinking Mode 的提示注入采用 main 分支的 XML 标签方式，以便保持简洁且不干扰模型行为。

#### 验收标准

1. THE Converters 模块 SHALL 仅注入 XML 控制标签到 system prompt 中，不注入自然语言指令
2. WHEN 请求中包含 thinking 配置时，THE Converters 模块 SHALL 从请求中读取 thinking budget 值
3. WHEN 请求中未指定 thinking budget 时，THE Converters 模块 SHALL 使用默认值 200000
4. THE KiroGate SHALL 默认启用 Thinking Mode（保留 release 分支的默认行为）

### 需求 3：Thinking Mode 流式处理重构

**用户故事：** 作为开发者，我希望 streaming.py 中的 Thinking Mode 处理逻辑使用 `KiroThinkingTagParser`，以便消除重复代码并统一解析行为。

#### 验收标准

1. WHEN 处理流式响应时，THE Streaming 模块 SHALL 使用 `KiroThinkingTagParser` 进行 `<thinking>` 标签解析
2. THE Streaming 模块 SHALL 移除原有的内嵌 `ThinkingStreamHandler` 实现
3. WHEN 生成 Anthropic 格式的流式响应时，THE Streaming 模块 SHALL 将 thinking 片段转换为 `thinking` content_block 事件
4. WHEN 生成 OpenAI 格式的流式响应时，THE Streaming 模块 SHALL 将 thinking 片段转换为带 `reasoning_content` 字段的 delta 事件

### 需求 4：非流式 Thinking 支持

**用户故事：** 作为开发者，我希望非流式响应也支持 Thinking Mode，以便所有 API 调用方式都能获得思考内容。

#### 验收标准

1. WHEN 收到非流式请求且 Thinking Mode 启用时，THE KiroGate SHALL 收集完整响应后解析 `<thinking>` 标签
2. WHEN 非流式响应包含 thinking 内容时，THE KiroGate SHALL 在 Anthropic 格式响应中包含 `thinking` 类型的 content block
3. WHEN 非流式响应包含 thinking 内容时，THE KiroGate SHALL 在 OpenAI 格式响应中包含 `reasoning_content` 字段

### 需求 5：Buffered Streaming 重构

**用户故事：** 作为开发者，我希望保留 release 分支的 `buffered_streaming.py` 但重构其内部实现使用 `KiroThinkingTagParser`，以便 `/cc/v1` 端点也使用统一的解析器。

#### 验收标准

1. THE Buffered_Streaming 模块 SHALL 使用 `KiroThinkingTagParser` 进行 thinking 标签解析
2. WHEN `/cc/v1` 端点接收流式请求时，THE Buffered_Streaming 模块 SHALL 正确缓冲并转换 thinking 内容
3. IF Buffered_Streaming 模块在当前分支已被移除，THEN THE KiroGate SHALL 跳过此需求的实现

### 需求 6：WebSearch 功能融合

**用户故事：** 作为开发者，我希望使用 release 分支的 WebSearch 实现作为基础，以便保留双格式支持和结构化数据模型。

#### 验收标准

1. THE WebSearch 模块 SHALL 同时支持 OpenAI 和 Anthropic 两种请求格式
2. THE WebSearch 模块 SHALL 使用结构化的 dataclass 模型定义搜索结果
3. WHEN 从请求中提取搜索查询时，THE WebSearch 模块 SHALL 从最后一条用户消息中提取
4. THE WebSearch 模块 SHALL 保留 release 分支的测试文件

### 需求 7：Models 数据模型更新

**用户故事：** 作为开发者，我希望合并 main 分支对 `models.py` 的改进，以便数据模型更加灵活。

#### 验收标准

1. THE AnthropicTool 模型 SHALL 将 `input_schema` 字段设为 Optional 类型
2. THE AnthropicTool 模型 SHALL 包含 `type` 字段
3. WHEN `input_schema` 未提供时，THE AnthropicTool 模型 SHALL 接受请求而不报验证错误

### 需求 8：Main 分支独有功能合并

**用户故事：** 作为开发者，我希望将 main 分支的所有独有功能合并到 release 分支，以便 release 分支包含所有最新功能。

#### 验收标准

1. THE KiroGate SHALL 包含用户系统增强功能（邮箱注册/登录、审批流程、会话版本控制、PBKDF2 密码哈希）
2. THE KiroGate SHALL 支持 HTTP/SOCKS5 代理配置
3. THE KiroGate SHALL 包含 Docker CI 工作流（GitHub Actions）
4. THE KiroGate SHALL 实施安全加固措施（拒绝生产环境默认密钥、移除 file_path）
5. THE KiroGate SHALL 提供 `/v1/messages/count_tokens` 端点
6. THE KiroGate SHALL 支持 IDC snake_case 格式的凭证导入
7. THE KiroGate SHALL 实现 Token 账户信息缓存
8. THE KiroGate SHALL 在转换器中支持图片内容
9. THE KiroGate SHALL 集成 Kiro Portal API（CBOR 格式）
10. THE KiroGate SHALL 将版本号更新为 2.3.0

### 需求 9：合并后验证与审查

**用户故事：** 作为开发者，我希望合并完成后有一个系统化的验证和审查机制，以便确保所有功能正确融合且无回归问题。

#### 验收标准

1. WHEN 合并完成后，THE KiroGate SHALL 通过所有现有测试用例
2. WHEN 合并完成后，THE 开发者 SHALL 对 Thinking Mode 的流式和非流式输出进行验证
3. WHEN 合并完成后，THE 开发者 SHALL 对 WebSearch 的双格式支持进行验证
4. WHEN 合并完成后，THE 开发者 SHALL 检查所有 main 分支独有功能的集成状态
5. IF 合并过程中发现冲突文件，THEN THE 开发者 SHALL 逐文件审查冲突解决方案
