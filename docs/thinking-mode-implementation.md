# Thinking 模式完整实现文档

## 概述

本文档详细说明了项目中 thinking 模式的完整实现，包括三种渠道（Amazon Q、Gemini、Custom API）的不同实现方式和相互兼容性。

**最后更新**: 2024-12-23

---

## 目录

1. [架构概览](#架构概览)
2. [三种渠道的实现](#三种渠道的实现)
3. [Thinking 块格式](#thinking-块格式)
4. [关键实现细节](#关键实现细节)
5. [跨格式兼容性](#跨格式兼容性)
6. [测试和验证](#测试和验证)

---

## 架构概览

### Thinking 模式支持矩阵

| 渠道 | 支持状态 | 实现方式 | Signature 要求 |
|------|---------|---------|---------------|
| **Amazon Q** | ✅ 支持 | 提示词注入 + `<thinking>` 标签解析 | 无 |
| **Gemini** | ✅ 原生支持 | `thinkingConfig` | 使用 `thoughtSignature` |
| **Custom API (OpenAI)** | ✅ 提示词注入 | `<thinking>` 标签解析 | 无 |
| **Custom API (Claude - Anthropic)** | ✅ 透传 | 直接透传 | 无 |
| **Custom API (Claude - Azure)** | ✅ 有限支持 | 透传 + 过滤 | **必须有 `signature`** |

### 数据流向

```
客户端请求 (thinking: true)
    ↓
main.py (智能路由)
    ↓
    ├─→ Amazon Q: 注入提示词 → 解析 <thinking> 标签
    ├─→ Gemini: 转换为 thinkingConfig
    └─→ Custom API:
        ├─→ OpenAI 格式: 注入提示词 → 解析 <thinking> 标签
        └─→ Claude 格式:
            ├─→ Anthropic 官方: 直接透传
            └─→ Azure: 过滤无 signature 的 thinking 块
```

---

## 三种渠道的实现

### 1. Amazon Q 渠道

**状态**: ✅ 支持（通过提示词注入）

#### 实现位置

- **提示词注入**: `src/amazonq/converter.py` - `convert_claude_to_codewhisperer_request()`
- **标签解析**: `src/amazonq/stream_handler.py` - `AmazonQStreamHandler.handle_stream()`

#### 核心逻辑

##### 1.1 提示词注入

Amazon Q 使用与 Custom API (OpenAI) 相同的策略：在用户消息末尾注入 thinking 提示词。

```python
# src/amazonq/converter.py

THINKING_HINT = "<thinking_mode>interleaved</thinking_mode><max_thinking_length>16000</max_thinking_length><thinking_mode>interleaved</thinking_mode><max_thinking_length>16000</max_thinking_length>"

def convert_claude_to_codewhisperer_request(claude_req: ClaudeRequest, ...):
    """
    将 Claude 请求转换为 CodeWhisperer 请求
    """
    # 检测是否启用 thinking 模式（默认启用）
    thinking_enabled = True  # 默认启用
    thinking_param = getattr(claude_req, 'thinking', None)
    if thinking_param is not None:
        if isinstance(thinking_param, bool):
            thinking_enabled = thinking_param
        elif isinstance(thinking_param, dict):
            thinking_type = thinking_param.get('type', 'enabled')
            thinking_enabled = thinking_type == 'enabled' or thinking_param.get('enabled', True)
    
    # 如果启用 thinking，在 prompt_content 末尾添加 THINKING_HINT
    if thinking_enabled and prompt_content:
        prompt_content = f"{prompt_content}\n{THINKING_HINT}"
    
    # 格式化内容（添加上下文信息）
    formatted_content = (
        "--- CONTEXT ENTRY BEGIN ---\n"
        f"Current time: {get_current_timestamp()}\n"
        "...\n"
        "--- CONTEXT ENTRY END ---\n\n"
        "--- USER MESSAGE BEGIN ---\n"
        f"{prompt_content}\n"  # 包含 THINKING_HINT
        "--- USER MESSAGE END ---"
    )
```

**关键点**:
- **默认启用**: 与 Gemini 和 Custom API (OpenAI) 一致
- **双重提示**: `THINKING_HINT` 重复两次，增强效果
- **位置**: 在用户消息末尾，但在格式化模板之前

##### 1.2 历史消息转换

```python
# src/amazonq/converter.py - 处理历史消息中的 thinking 块

for block in content:
    if block.get("type") == "thinking":
        # 转换为 <thinking> 标签格式
        text_parts.append(f"{THINKING_START_TAG}{block.get('thinking', '')}{THINKING_END_TAG}")
```

##### 1.3 响应流解析

`src/amazonq/stream_handler.py` 中的 `AmazonQStreamHandler` 实时解析 Amazon Q 返回的文本流，检测 `<thinking>` 标签：

```python
class AmazonQStreamHandler:
    def __init__(self):
        # Thinking 标签状态
        self.in_think_block: bool = False
        self.think_buffer: str = ""
        self.pending_start_tag_chars: int = 0
    
    async def handle_stream(self, upstream_bytes):
        """处理 Amazon Q Event Stream"""
        
        # 收到文本内容
        content = event.delta.text
        self.think_buffer += content
        
        while self.think_buffer:
            if not self.in_think_block:
                # 查找 <thinking> 开始标签
                think_start = self.think_buffer.find(THINKING_START_TAG)
                
                if think_start == -1:
                    # 检查是否有部分标签在末尾（跨字节流边界）
                    pending = _pending_tag_suffix(self.think_buffer, THINKING_START_TAG)
                    
                    if pending == len(self.think_buffer) and pending > 0:
                        # 整个 buffer 都是标签前缀
                        # 关闭当前文本块，开启 thinking 块
                        if self.content_block_start_sent:
                            yield build_claude_content_block_stop_event(self.content_block_index)
                        
                        self.content_block_index += 1
                        yield build_claude_content_block_start_event(self.content_block_index, "thinking")
                        self.in_think_block = True
                        self.pending_start_tag_chars = len(THINKING_START_TAG) - pending
                        self.think_buffer = ""
                        break
                    
                    # 发送非标签部分作为普通文本
                    emit_len = len(self.think_buffer) - pending
                    if emit_len > 0:
                        text_chunk = self.think_buffer[:emit_len]
                        if not self.content_block_start_sent:
                            self.content_block_index += 1
                            yield build_claude_content_block_start_event(self.content_block_index, "text")
                        yield build_claude_content_block_delta_event(self.content_block_index, text_chunk)
                    self.think_buffer = self.think_buffer[emit_len:]
                else:
                    # 找到完整的 <thinking> 标签
                    before_text = self.think_buffer[:think_start]
                    if before_text:
                        # 发送标签前的文本
                        if not self.content_block_start_sent:
                            self.content_block_index += 1
                            yield build_claude_content_block_start_event(self.content_block_index, "text")
                        yield build_claude_content_block_delta_event(self.content_block_index, before_text)
                    
                    # 跳过标签，进入 thinking 模式
                    self.think_buffer = self.think_buffer[think_start + len(THINKING_START_TAG):]
                    
                    # 关闭文本块，开启 thinking 块
                    if self.content_block_start_sent:
                        yield build_claude_content_block_stop_event(self.content_block_index)
                    
                    self.content_block_index += 1
                    yield build_claude_content_block_start_event(self.content_block_index, "thinking")
                    self.in_think_block = True
            
            else:
                # 在 thinking 块中，查找 </thinking> 结束标签
                think_end = self.think_buffer.find(THINKING_END_TAG)
                
                if think_end == -1:
                    # 检查是否有部分结束标签
                    pending = _pending_tag_suffix(self.think_buffer, THINKING_END_TAG)
                    emit_len = len(self.think_buffer) - pending
                    
                    if emit_len > 0:
                        thinking_chunk = self.think_buffer[:emit_len]
                        # 发送 thinking_delta 事件
                        yield build_claude_content_block_delta_event(
                            self.content_block_index,
                            thinking_chunk,
                            delta_type="thinking_delta",
                            field_name="thinking"
                        )
                    self.think_buffer = self.think_buffer[emit_len:]
                else:
                    # 找到完整的 </thinking> 标签
                    thinking_chunk = self.think_buffer[:think_end]
                    if thinking_chunk:
                        yield build_claude_content_block_delta_event(
                            self.content_block_index,
                            thinking_chunk,
                            delta_type="thinking_delta",
                            field_name="thinking"
                        )
                    
                    # 跳过结束标签
                    self.think_buffer = self.think_buffer[think_end + len(THINKING_END_TAG):]
                    
                    # 关闭 thinking 块
                    yield build_claude_content_block_stop_event(self.content_block_index)
                    self.in_think_block = False
```

**关键特性**:

1. **跨字节流边界检测**: `_pending_tag_suffix()` 函数检测 buffer 末尾是否是标签的部分前缀
   ```python
   def _pending_tag_suffix(buffer: str, tag: str) -> int:
       """检测 buffer 末尾是否是 tag 的部分前缀"""
       max_len = min(len(buffer), len(tag) - 1)
       for length in range(max_len, 0, -1):
           if buffer[-length:] == tag[:length]:
               return length
       return 0
   ```

2. **状态机管理**: 
   - `in_think_block`: 是否在 thinking 块中
   - `think_buffer`: 累积待处理的文本
   - `pending_start_tag_chars`: 待处理的开始标签字符数

3. **实时流式处理**: 不等待完整标签，边接收边解析

##### 1.4 默认启用策略

```python
# 默认启用 thinking（与 Gemini 和 Custom API 一致）
thinking_enabled = True

# 可以通过参数禁用
thinking_param = getattr(claude_req, 'thinking', None)
if thinking_param is not None:
    if isinstance(thinking_param, bool):
        thinking_enabled = thinking_param
    elif isinstance(thinking_param, dict):
        thinking_type = thinking_param.get('type', 'enabled')
        thinking_enabled = thinking_type == 'enabled' or thinking_param.get('enabled', True)
```

---

### 2. Gemini 渠道

**状态**: ✅ 原生支持

#### 实现位置

- **配置生成**: `src/gemini/converter.py` - `get_thinking_config()`
- **请求转换**: `src/gemini/converter.py` - `convert_claude_to_gemini()`
- **响应处理**: `src/gemini/handler.py` - `handle_gemini_stream()`

#### 核心逻辑

##### 2.1 配置生成 (`get_thinking_config`)

```python
def get_thinking_config(thinking: Optional[Union[bool, Dict[str, Any]]]) -> Dict[str, Any]:
    """
    将 Claude thinking 参数转换为 Gemini thinkingConfig
    
    默认启用 thinking，budget 为 1024 tokens
    """
    if thinking is None:
        return {
            "includeThoughts": True,
            "thinkingBudget": DEFAULT_THINKING_BUDGET  # 1024
        }
    
    if isinstance(thinking, bool):
        return {
            "includeThoughts": thinking,
            "thinkingBudget": DEFAULT_THINKING_BUDGET if thinking else 0
        }
    
    if isinstance(thinking, dict):
        thinking_type = thinking.get("type", "enabled")
        is_enabled = thinking_type == "enabled"
        budget = thinking.get("budget_tokens", DEFAULT_THINKING_BUDGET)
        
        return {
            "includeThoughts": is_enabled,
            "thinkingBudget": budget if is_enabled else 0
        }
```

##### 2.2 Signature 处理

Gemini 使用 `thoughtSignature` 字段来标记 thinking 块的结束：

**请求转换** (`convert_claude_to_gemini`):
```python
# Claude thinking 块格式:
{
    "type": "thinking",
    "thinking": "思考内容",
    "signature": "abc123"  # 可选
}

# 转换为 Gemini 格式:
{
    "thought": "思考内容",
    "thoughtSignature": "abc123"  # 如果有 signature
}
```

**响应处理** (`handle_gemini_stream`):
```python
# Gemini 返回:
{
    "thought": "思考内容",
    "thoughtSignature": "abc123"
}

# 转换为 Claude 格式:
# 1. thinking_delta 事件（思考内容）
# 2. signature_delta 事件（signature）
# 3. content_block_stop 事件
```

##### 2.3 消息重组

`reorganize_tool_messages()` 函数处理历史消息中的 thinking 块：

```python
def reorganize_tool_messages(contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    重新组织消息：
    1. thinking 和下一个 part（带 thoughtSignature）组合在一起
    2. functionCall 和对应的 functionResponse 组合在一起
    """
    # 处理空 text part（只有 thoughtSignature）
    if (part.get("text") == "" and "thoughtSignature" in part):
        pending_signature = part["thoughtSignature"]
        continue
    
    # 将 signature 附加到下一个 part
    if pending_signature:
        part["thoughtSignature"] = pending_signature
        pending_signature = None
```

---

### 3. Custom API 渠道

#### 3.1 OpenAI 格式

**状态**: ✅ 支持（通过提示词注入）

##### 实现位置

- **请求转换**: `src/custom_api/converter.py` - `convert_claude_to_openai_request()`
- **响应解析**: `src/custom_api/converter.py` - `_process_thinking_content()`
- **流处理**: `src/custom_api/converter.py` - `OpenAIStreamState`

##### 三阶段转换

**阶段 1: 请求转换（注入提示词）**

```python
THINKING_HINT = "<thinking_mode>interleaved</thinking_mode><max_thinking_length>16000</max_thinking_length>"

def convert_claude_to_openai_request(claude_req: ClaudeRequest, model: str):
    thinking_enabled = _is_thinking_enabled(claude_req)
    
    # 如果启用 thinking，在 system prompt 末尾添加提示
    if thinking_enabled:
        if system_content:
            system_content = f"{system_content}\n{THINKING_HINT}"
        else:
            system_content = THINKING_HINT
    
    return openai_request, thinking_enabled
```

**阶段 2: 历史消息转换**

```python
def _convert_assistant_message(content, thinking_enabled):
    """将历史消息中的 thinking 块转换为 <thinking> 标签"""
    for block in content:
        if block.get("type") == "thinking":
            if thinking_enabled:
                thinking_text = block.get("thinking", "")
                text_parts.append(f"<thinking>{thinking_text}</thinking>")
```

**阶段 3: 响应流解析**

```python
class OpenAIStreamState:
    def __init__(self, thinking_enabled: bool = False):
        self.thinking_enabled = thinking_enabled
        self.in_thinking_block = False
        self.thinking_buffer = ""
        self.current_block_type: Optional[str] = None  # "text" or "thinking"

def _process_thinking_content(content: str, state: OpenAIStreamState):
    """
    实时解析 <thinking>...</thinking> 标签
    
    流程:
    1. 检测 <thinking> 开始标签 → 创建 thinking content block
    2. 收集思考内容到 buffer → 发送 thinking_delta 事件
    3. 检测 </thinking> 结束标签 → 关闭 thinking block
    4. 后续内容作为普通 text block
    """
    state.thinking_buffer += content
    
    while True:
        if state.in_thinking_block:
            # 查找结束标签
            end_idx = state.thinking_buffer.find(THINKING_END_TAG)
            if end_idx != -1:
                thinking_content = state.thinking_buffer[:end_idx]
                events.append(_build_thinking_delta(index, thinking_content))
                events.append(_build_content_block_stop(index))
                state.in_thinking_block = False
        else:
            # 查找开始标签
            start_idx = state.thinking_buffer.find(THINKING_START_TAG)
            if start_idx != -1:
                # 发送开始标签前的普通文本
                text_before = state.thinking_buffer[:start_idx]
                if text_before:
                    events.append(_build_text_delta(index, text_before))
                
                # 开始新的 thinking 块
                events.append(_build_thinking_start(index))
                state.in_thinking_block = True
```

##### 默认启用逻辑

```python
def _is_thinking_enabled(claude_req: ClaudeRequest) -> bool:
    """
    检测请求是否启用了 thinking 模式（默认启用）
    
    与 Gemini 行为一致：如果没有明确禁用，则启用
    """
    thinking_param = getattr(claude_req, 'thinking', None)
    if thinking_param is not None:
        if isinstance(thinking_param, bool):
            return thinking_param
        elif isinstance(thinking_param, dict):
            thinking_type = thinking_param.get('type', 'enabled')
            return thinking_type == 'enabled' or thinking_param.get('enabled', True)
    return True  # 默认启用
```

---

#### 3.2 Claude 格式（Anthropic 官方）

**状态**: ✅ 完全支持

##### 实现位置

- **透传处理**: `src/custom_api/handler.py` - `handle_claude_format_stream()`

##### 核心逻辑

```python
async def handle_claude_format_stream(
    api_base: str,
    api_key: str,
    request_data: Dict[str, Any],
    provider: str = "",
    ...
):
    """
    Anthropic 官方 API：直接透传，不做任何清理
    """
    # 官方 Anthropic API 或其他：直接透传，不清理
    if provider != "azure":
        # 直接发送 request_data，包含 thinking 参数
        pass
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    
    # 直接透传请求和响应
    async with client.stream("POST", api_url, json=request_data, headers=headers):
        # 透传响应流
        yield event_text + '\n\n'
```

**特点**:
- 不修改 `request_data`
- `thinking` 参数原样发送给 Anthropic API
- 响应流原样返回给客户端
- 无需格式转换

---

#### 3.3 Claude 格式（Azure）

**状态**: ✅ 有限支持（需要 signature）

##### 实现位置

- **清理逻辑**: `src/custom_api/handler.py` - `_clean_claude_request_for_azure()`

##### 核心逻辑

这是**最关键的部分**，实现了跨格式兼容性：

```python
def _clean_claude_request_for_azure(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    为 Azure Anthropic API 清理 Claude 请求数据
    
    Azure 的特殊要求：
    1. 不支持某些扩展字段（context_management, betas 等）
    2. 工具格式需要转换为标准格式
    3. Thinking 块必须有 signature 字段
    """
    import copy
    cleaned = copy.deepcopy(request_data)
    
    # 移除不支持的顶层字段
    unsupported_fields = ["context_management", "betas", "anthropic_beta"]
    for field in unsupported_fields:
        if field in cleaned:
            del cleaned[field]
    
    # 跟踪是否有缺少 signature 的 thinking 块被移除
    has_invalid_thinking = False
    
    # 清理 messages 字段
    if "messages" in cleaned:
        cleaned_messages = []
        for idx, msg in enumerate(cleaned["messages"]):
            content = msg.get("content")
            
            # 如果 content 是列表，清理其中的 thinking 块
            if isinstance(content, list):
                cleaned_content = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        
                        # 关键逻辑：检查 thinking 块是否有 signature
                        if block_type == "thinking":
                            if block.get("signature"):
                                # 有 signature，保留（Azure 支持）
                                cleaned_content.append(block)
                            else:
                                # 没有 signature，移除（Azure 不支持）
                                logger.debug(f"移除消息 {idx} 中缺少 signature 的 thinking 块")
                                has_invalid_thinking = True
                            continue
                        
                        # redacted_thinking 块也需要检查
                        if block_type == "redacted_thinking":
                            if block.get("data"):
                                cleaned_content.append(block)
                            else:
                                has_invalid_thinking = True
                            continue
                        
                        cleaned_content.append(block)
                
                content = cleaned_content
                msg = {**msg, "content": content}
            
            # 检查 content 是否为空
            is_empty = (
                content is None or
                (isinstance(content, str) and not content.strip()) or
                (isinstance(content, list) and len(content) == 0)
            )
            
            if not is_empty:
                cleaned_messages.append(msg)
        
        cleaned["messages"] = cleaned_messages
    
    # 如果有无效的 thinking 块被移除，禁用 thinking 功能
    # 因为 Azure API 要求：启用 thinking 时，assistant 消息必须以 thinking 块开头
    if has_invalid_thinking and "thinking" in cleaned:
        logger.info("检测到缺少 signature 的 thinking 块，禁用 thinking 功能以避免格式错误")
        del cleaned["thinking"]
    
    # 清理 tools 字段（省略，见代码）
    
    return cleaned
```

##### Azure 的特殊要求

1. **Thinking 块格式**:
   ```python
   # ✅ Azure 支持（有 signature）
   {
       "type": "thinking",
       "thinking": "思考内容",
       "signature": "abc123"  # 必须有
   }
   
   # ❌ Azure 不支持（无 signature）
   {
       "type": "thinking",
       "thinking": "思考内容"
   }
   ```

2. **条件性禁用**:
   - 如果历史消息中有**无 signature** 的 thinking 块 → 移除这些块
   - 如果移除了 thinking 块 → 删除请求中的 `thinking` 参数
   - 这样可以避免 Azure API 报错

3. **工具清理**:
   - 移除 `custom` 类型包装
   - 转换 `function` 格式为标准 Claude 格式
   - 只保留 `name`, `description`, `input_schema` 字段

---

## Thinking 块格式

### Claude API 标准格式

```json
{
  "type": "thinking",
  "thinking": "让我分析一下这个问题...",
  "signature": "abc123"  // 可选，Azure 需要
}
```

### Gemini 格式

```json
{
  "thought": "让我分析一下这个问题...",
  "thoughtSignature": "abc123"  // 可选
}
```

### OpenAI 格式（文本标签）

```
<thinking>
让我分析一下这个问题...
</thinking>
```

### SSE 事件格式

```
event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"让我分析"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"一下这个问题..."}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta","signature":"abc123"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}
```

---

## 关键实现细节

### 1. Signature 的作用

**Signature** 是 thinking 块的唯一标识符，用于：

1. **验证完整性**: 确保 thinking 块完整传输
2. **Azure 兼容性**: Azure API 要求 thinking 块必须有 signature
3. **消息重组**: Gemini 使用 signature 来组合 thinking 和后续内容

### 2. 默认启用策略

**Gemini 和 Custom API (OpenAI) 默认启用 thinking**:

```python
# 如果请求中没有 thinking 参数，默认启用
if thinking_param is None:
    return True
```

**原因**:
- 提供更好的用户体验
- 与 Claude 官方行为一致
- 用户可以明确禁用：`thinking: false` 或 `thinking: {"type": "disabled"}`

### 3. 跨格式消息处理

当 OpenAI 格式和 Claude 格式混用时：

```
请求 1 (OpenAI 格式) → 生成 thinking 块（无 signature）
    ↓
历史消息传递给 Azure
    ↓
_clean_claude_request_for_azure() 检测到无 signature 的 thinking 块
    ↓
移除这些块，禁用 thinking 参数
    ↓
Azure API 正常处理
```

### 4. 缓存支持

Thinking 块可以被缓存：

```python
# 在 src/main.py 中
if _cache_manager is not None:
    cacheable_content, token_count = _cache_manager.extract_cacheable_content(request_data)
    # thinking 块会被包含在 cacheable_content 中
```

从日志可以看到：
```
缓存创建: 3599, 缓存读取: 0
```

---

## 跨格式兼容性

### 场景 1: Amazon Q → Amazon Q

```
客户端 (Amazon Q)
    ↓
convert_claude_to_codewhisperer_request() - 注入 THINKING_HINT
    ↓
Amazon Q API 返回 <thinking>...</thinking>
    ↓
AmazonQStreamHandler.handle_stream() - 解析为 thinking 块（无 signature）
    ↓
历史消息存储
    ↓
下一次请求 (Amazon Q)
    ↓
convert_claude_to_codewhisperer_request() - 转换为 <thinking> 标签
    ↓
Amazon Q API 正常处理
```

### 场景 2: Amazon Q → Azure

```
客户端 (Amazon Q)
    ↓
convert_claude_to_codewhisperer_request() - 注入 THINKING_HINT
    ↓
Amazon Q API 返回 <thinking>...</thinking>
    ↓
AmazonQStreamHandler.handle_stream() - 解析为 thinking 块（无 signature）
    ↓
历史消息存储
    ↓
下一次请求 (Azure)
    ↓
_clean_claude_request_for_azure() - 移除无 signature 的块
    ↓
Azure API 正常处理
```

### 场景 3: OpenAI → Azure

```
客户端 (OpenAI 格式)
    ↓
convert_claude_to_openai_request() - 注入提示词
    ↓
OpenAI API 返回 <thinking>...</thinking>
    ↓
_process_thinking_content() - 解析为 thinking 块（无 signature）
    ↓
历史消息存储
    ↓
下一次请求 (Azure)
    ↓
_clean_claude_request_for_azure() - 移除无 signature 的块
    ↓
Azure API 正常处理
```

### 场景 4: Gemini → Azure

```
客户端 (Gemini)
    ↓
convert_claude_to_gemini() - 转换为 thinkingConfig
    ↓
Gemini API 返回 thought + thoughtSignature
    ↓
handle_gemini_stream() - 转换为 thinking 块（有 signature）
    ↓
历史消息存储
    ↓
下一次请求 (Azure)
    ↓
_clean_claude_request_for_azure() - 保留有 signature 的块
    ↓
Azure API 正常处理
```

### 场景 5: Azure → Azure

```
客户端 (Azure)
    ↓
_clean_claude_request_for_azure() - 清理请求
    ↓
Azure API 返回 thinking 块（有 signature）
    ↓
历史消息存储
    ↓
下一次请求 (Azure)
    ↓
_clean_claude_request_for_azure() - 保留有 signature 的块
    ↓
Azure API 正常处理
```

---

## 测试和验证

### 测试 Amazon Q Thinking

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "解释量子纠缠"}],
    "max_tokens": 4096,
    "thinking": true
  }'
```

**预期结果**:
- 请求中注入 `THINKING_HINT`
- Amazon Q 返回包含 `<thinking>` 标签的文本
- 转换为 `thinking` content block
- 无 signature

### 测试 Gemini Thinking

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -d '{
    "model": "claude-sonnet-4-5-thinking",
    "messages": [{"role": "user", "content": "解释量子纠缠"}],
    "max_tokens": 4096,
    "thinking": {"type": "enabled", "budget_tokens": 2048}
  }'
```

**预期结果**:
- 响应包含 `thinking` content block
- 包含 `signature_delta` 事件

### 测试 Custom API (OpenAI 格式)

```bash
curl -X POST http://localhost:8080/v1/custom_api/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -H "X-Account-ID: your-openai-account-id" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "解释量子纠缠"}],
    "max_tokens": 4096,
    "thinking": true
  }'
```

**预期结果**:
- System prompt 包含 THINKING_HINT
- 响应包含 `<thinking>` 标签
- 转换为 `thinking` content block

### 测试 Custom API (Azure)

```bash
curl -X POST http://localhost:8080/v1/custom_api/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -H "X-Account-ID: your-azure-account-id" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "解释量子纠缠"}],
    "max_tokens": 4096,
    "thinking": true
  }'
```

**预期结果**:
- 请求被 `_clean_claude_request_for_azure()` 清理
- 如果历史消息有无 signature 的 thinking 块，会被移除
- 日志显示: "工具清理完成: X 个工具"

### 验证日志

成功的 Azure 请求日志示例：

```
2025-12-23 20:03:19,159 - custom_api.handler - INFO - Custom API 请求: format=claude, provider=azure, api_base=https://xxx.azure.com/anthropic, model=claude-haiku-4-5
2025-12-23 20:03:19,159 - custom_api.handler - INFO - 第一个工具结构: {"name": "Task", ...}
2025-12-23 20:03:19,159 - custom_api.handler - INFO - 工具清理完成: 43 个工具
2025-12-23 20:03:19,159 - custom_api.handler - INFO - 透传 Claude 格式请求到: https://xxx.azure.com/anthropic/v1/messages
2025-12-23 20:03:21,948 - httpx - INFO - HTTP Request: POST https://xxx.azure.com/anthropic/v1/messages "HTTP/1.1 200 OK"
2025-12-23 20:03:22,175 - custom_api.handler - INFO - Custom API (Claude) Token 统计 - 输入: 147, 输出: 27, 缓存创建: 0, 缓存读取: 0
2025-12-23 20:03:25,281 - httpx - INFO - HTTP Request: POST https://xxx.azure.com/anthropic/v1/messages "HTTP/1.1 200 OK"
2025-12-23 20:03:45,588 - custom_api.handler - INFO - Custom API (Claude) Token 统计 - 输入: 9, 输出: 2842, 缓存创建: 3599, 缓存读取: 0
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `src/models.py` | 定义 `ClaudeRequest.thinking` 参数 |
| `src/gemini/converter.py` | Gemini thinking 配置生成和 signature 处理 |
| `src/gemini/handler.py` | Gemini 响应流处理，signature_delta 事件 |
| `src/custom_api/converter.py` | OpenAI 格式 thinking 转换（提示词注入 + 流解析） |
| `src/custom_api/handler.py` | Claude 格式透传和 Azure 清理逻辑 |
| `src/auth/account_manager.py` | Gemini thinking 模型路由 |
| `src/main.py` | API 端点和智能路由逻辑 |
| `src/processing/cache_manager.py` | Thinking 块缓存支持 |

---

## 注意事项

1. **Amazon Q 特点**:
   - 使用提示词注入方式实现 thinking
   - 默认启用（与 Gemini 和 Custom API 一致）
   - 不生成 signature（Azure 会过滤）
   - 支持跨字节流边界的标签检测

2. **Azure 限制**: 
   - 如果需要完整的 thinking 功能，建议使用 Anthropic 官方 API
   - Azure 只支持带 signature 的 thinking 块
   - 混用不同格式时，Azure 会自动过滤不兼容的块

3. **默认行为**:
   - Gemini 和 Custom API (OpenAI) 默认启用 thinking
   - 可以通过 `thinking: false` 明确禁用

4. **Signature 生成**:
   - Amazon Q 不生成 signature（Azure 会过滤）
   - Gemini 自动生成 thoughtSignature
   - OpenAI 格式不生成 signature（Azure 会过滤）
   - Anthropic 官方 API 可能生成或不生成 signature

5. **缓存兼容性**:
   - Thinking 块可以被缓存
   - 缓存键包含 thinking 内容
   - 跨格式缓存可能导致 signature 不一致

6. **性能考虑**:
   - Thinking 模式会消耗额外的 token
   - 建议设置合理的 `budget_tokens`
   - 监控 token 使用量

---

## 更新历史

- **2024-12-23**: 初始版本，记录完整的 thinking 模式实现
- **2024-12-23**: 更新 Amazon Q 渠道，确认其支持 thinking 模式（通过提示词注入）
- **2026-01-13**: 实现 Extended Thinking 支持
  - 在 `converters.py` 中添加 `THINKING_HINT` 常量和 `_is_thinking_enabled()` 函数
  - 修改 `build_kiro_payload()` 函数支持 thinking 提示词注入
  - 在 `streaming.py` 中添加 `ThinkingStreamHandler` 类用于解析 `<thinking>` 标签
  - 修改 `stream_kiro_to_anthropic()` 函数实现实时 thinking 块解析
  - 更新 `request_handler.py` 正确传递 thinking_enabled 参数
  - **Prompt 增强**: 引入 `THINKING_SYSTEM_PROMPT` 和自然语言指令，解决模型“思考不积极”的问题
