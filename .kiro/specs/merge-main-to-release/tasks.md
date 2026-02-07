# 实现计划：合并 main 分支到 release 分支

## 概述

将 main 分支功能融合到 release 分支。当前 release 分支已包含大部分融合成果（thinking_parser.py、Anthropic 流式/非流式 thinking 支持、models 更新）。主要剩余工作是 OpenAI 格式的 thinking 支持、WebSearch 确认、main 独有功能合并，以及测试验证。

## Tasks

- [x] 1. OpenAI 流式 Thinking 支持
  - [x] 1.1 在 `stream_kiro_to_openai_internal` 中添加 `thinking_enabled` 参数和 `KiroThinkingTagParser` 集成
    - 添加 `thinking_enabled: bool = False` 参数
    - 当启用时创建 `KiroThinkingTagParser` 实例
    - THINKING 片段输出为 `delta.reasoning_content`
    - TEXT 片段输出为 `delta.content`
    - 流结束时调用 `flush()` 处理缓冲区
    - _Requirements: 3.1, 3.3, 3.4_

  - [x] 1.2 在 `stream_kiro_to_openai` 中传递 `thinking_enabled` 参数
    - 确保包装函数将 `thinking_enabled` 传递给 `stream_kiro_to_openai_internal`
    - _Requirements: 3.1_

  - [x] 1.3 在 `stream_with_first_token_retry` 中传递 `thinking_enabled` 参数
    - 确保重试逻辑也传递 thinking 参数
    - _Requirements: 3.1_

- [x] 2. OpenAI 非流式 Thinking 支持
  - [x] 2.1 在 `collect_stream_response` 中添加 `thinking_enabled` 参数和 thinking 解析
    - 添加 `thinking_enabled: bool = False` 参数
    - 当启用时使用 `KiroThinkingTagParser` 解析完整内容
    - 在 message 中添加 `reasoning_content` 字段
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 3. Request Handler 集成
  - [x] 3.1 更新 `request_handler.py` 中的 OpenAI 路径调用，传递 `thinking_enabled`
    - 在 `create_stream_response` 中传递 `thinking_enabled` 给 OpenAI 流式函数
    - 在 `create_non_stream_response` 中传递 `thinking_enabled` 给 `collect_stream_response`
    - _Requirements: 3.1, 4.1_

- [x] 4. Checkpoint - 确保 Thinking Mode 集成完整
  - 确保所有测试通过，ask the user if questions arise.

- [x] 5. WebSearch 功能确认与补全
  - [x] 5.1 确认当前 `websearch.py` 是否已支持 OpenAI 格式，如未支持则添加
    - 检查 `has_web_search_tool` 是否接受 `ChatCompletionRequest`
    - 检查查询提取是否从最后一条用户消息提取
    - 如有差异，按 release 分支策略调整
    - _Requirements: 6.1, 6.3_

- [x] 6. Main 分支独有功能合并
  - [x] 6.1 对比 main 和 release 分支的差异，列出尚未合并的功能
    - 使用 `git diff main..HEAD` 检查各文件差异
    - 确认用户系统增强、代理支持、安全加固等功能的合并状态
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10_

  - [x] 6.2 合并尚未包含的 main 分支功能代码
    - 逐文件合并差异代码
    - 解决导入冲突和配置冲突
    - _Requirements: 8.1-8.10_

  - [x] 6.3 更新版本号为 2.3.0
    - _Requirements: 8.10_

- [x] 7. Checkpoint - 确保 main 功能合并完整
  - 确保所有测试通过，ask the user if questions arise.

- [ ] 8. 属性测试
  - [ ]* 8.1 编写 Thinking 解析器属性测试
    - **Property 1: Thinking 解析器模式激活**
    - **Validates: Requirements 1.3**
    - 使用 hypothesis 生成随机字符串，验证以 `<thinking>` 开头时产生 THINKING 片段

  - [ ]* 8.2 编写假标签检测属性测试
    - **Property 2: 假标签检测**
    - **Validates: Requirements 1.2**
    - 生成包含引号包裹的 `</thinking>` 的字符串，验证不被误识别为关闭标签

  - [ ]* 8.3 编写 XML 注入纯净性属性测试
    - **Property 3: XML 标签注入纯净性**
    - **Validates: Requirements 2.1**
    - 生成随机 thinking 配置和 system prompt，验证输出仅含 XML 标签

  - [ ]* 8.4 编写 Thinking Budget 解析属性测试
    - **Property 4: Thinking Budget 解析**
    - **Validates: Requirements 2.2, 2.3**
    - 生成随机 thinking 配置，验证 budget 返回值正确

  - [ ]* 8.5 编写 WebSearch 查询提取属性测试
    - **Property 5: WebSearch 查询提取位置**
    - **Validates: Requirements 6.3**
    - 生成多消息请求，验证从正确位置提取查询

  - [ ]* 8.6 编写 AnthropicTool 可选 schema 属性测试
    - **Property 6: AnthropicTool 可选 input_schema**
    - **Validates: Requirements 7.1, 7.3**
    - 生成随机工具名称，验证无 input_schema 时不报错

- [x] 9. 合并后审查与验证
  - [x] 9.1 运行完整测试套件，确保所有测试通过
    - _Requirements: 9.1_

  - [x] 9.2 生成合并审查报告，列出所有已合并功能和冲突解决方案
    - 列出每个冲突文件的解决策略
    - 确认所有 main 分支功能已集成
    - 标记需要用户手动验证的功能点
    - _Requirements: 9.2, 9.3, 9.4, 9.5_

- [x] 10. Final checkpoint - 合并完成确认
  - 确保所有测试通过，ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 当前 release 分支已包含大部分 Thinking Mode 融合成果，主要缺失 OpenAI 格式支持
- 属性测试使用 `hypothesis` 库，每个测试至少 100 次迭代
- 合并 main 独有功能时需要逐文件对比，避免覆盖 release 分支的改进
