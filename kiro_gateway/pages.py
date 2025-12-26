# -*- coding: utf-8 -*-

"""
KiroGate Frontend Pages.

HTML templates for the web interface.
"""

from kiro_gateway.config import APP_VERSION, AVAILABLE_MODELS
import json

# Static assets proxy base
PROXY_BASE = "https://proxy.jhun.edu.kg"

# SEO and common head
COMMON_HEAD = f'''
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KiroGate - OpenAI & Anthropic 兼容的 Kiro API 代理网关</title>

  <!-- SEO Meta Tags -->
  <meta name="description" content="KiroGate 是一个开源的 Kiro IDE API 代理网关，支持 OpenAI 和 Anthropic API 格式，让你可以通过任何兼容的工具使用 Claude 模型。支持流式传输、工具调用、多租户等特性。">
  <meta name="keywords" content="KiroGate, Kiro, Claude, OpenAI, Anthropic, API Gateway, Proxy, AI, LLM, Claude Code, Python, FastAPI, 代理网关">
  <meta name="author" content="KiroGate">
  <meta name="robots" content="index, follow">

  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website">
  <meta property="og:title" content="KiroGate - OpenAI & Anthropic 兼容的 Kiro API 代理网关">
  <meta property="og:description" content="开源的 Kiro IDE API 代理网关，支持 OpenAI 和 Anthropic API 格式，通过任何兼容工具使用 Claude 模型。">
  <meta property="og:site_name" content="KiroGate">

  <!-- Twitter -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="KiroGate - OpenAI & Anthropic 兼容的 Kiro API 代理网关">
  <meta name="twitter:description" content="开源的 Kiro IDE API 代理网关，支持 OpenAI 和 Anthropic API 格式，通过任何兼容工具使用 Claude 模型。">

  <!-- Favicon -->
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🚀</text></svg>">

  <script src="{PROXY_BASE}/proxy/cdn.tailwindcss.com"></script>
  <script src="{PROXY_BASE}/proxy/cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <script src="{PROXY_BASE}/proxy/cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --primary: #6366f1;
      --primary-dark: #4f46e5;
    }}

    /* Light mode (default) */
    [data-theme="light"] {{
      --bg-main: #ffffff;
      --bg-card: #f8fafc;
      --bg-nav: #ffffff;
      --bg-input: #ffffff;
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --border-dark: #cbd5e1;
    }}

    /* Dark mode */
    [data-theme="dark"] {{
      --bg-main: #0f172a;
      --bg-card: #1e293b;
      --bg-nav: #1e293b;
      --bg-input: #334155;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --border: #334155;
      --border-dark: #475569;
    }}

    body {{
      background: var(--bg-main);
      color: var(--text);
      font-family: system-ui, -apple-system, sans-serif;
      transition: background-color 0.3s, color 0.3s;
    }}
    .card {{
      background: var(--bg-card);
      border-radius: 0.75rem;
      padding: 1.5rem;
      border: 1px solid var(--border);
      transition: background-color 0.3s, border-color 0.3s;
    }}
    .btn-primary {{
      background: var(--primary);
      color: white;
      padding: 0.5rem 1rem;
      border-radius: 0.5rem;
      transition: all 0.2s;
    }}
    .btn-primary:hover {{ background: var(--primary-dark); }}
    .nav-link {{
      color: var(--text-muted);
      transition: color 0.2s;
    }}
    .nav-link:hover, .nav-link.active {{ color: var(--primary); }}
    .theme-toggle {{
      cursor: pointer;
      padding: 0.5rem;
      border-radius: 0.5rem;
      transition: background-color 0.2s;
    }}
    .theme-toggle:hover {{
      background: var(--bg-card);
    }}
    /* 代码块优化 */
    pre {{
      max-width: 100%;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }}
    pre::-webkit-scrollbar {{
      height: 6px;
    }}
    pre::-webkit-scrollbar-track {{
      background: var(--bg-input);
      border-radius: 3px;
    }}
    pre::-webkit-scrollbar-thumb {{
      background: var(--border-dark);
      border-radius: 3px;
    }}
    /* 加载动画 */
    .loading-spinner {{
      display: inline-block;
      width: 20px;
      height: 20px;
      border: 2px solid var(--border);
      border-radius: 50%;
      border-top-color: var(--primary);
      animation: spin 0.8s linear infinite;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
    .loading-pulse {{
      animation: pulse 1.5s ease-in-out infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.5; }}
    }}
    /* 表格响应式 */
    .table-responsive {{
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }}
    .table-responsive::-webkit-scrollbar {{
      height: 6px;
    }}
    .table-responsive::-webkit-scrollbar-track {{
      background: var(--bg-input);
    }}
    .table-responsive::-webkit-scrollbar-thumb {{
      background: var(--border-dark);
      border-radius: 3px;
    }}
  </style>
  <script>
    // Theme initialization
    (function() {{
      const theme = localStorage.getItem('theme') || 'light';
      document.documentElement.setAttribute('data-theme', theme);
    }})();
  </script>
'''

COMMON_NAV = f'''
  <nav style="background: var(--bg-nav); border-bottom: 1px solid var(--border);" class="sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex items-center space-x-8">
          <a href="/" class="text-2xl font-bold text-indigo-500">⚡ KiroGate</a>
          <div class="hidden md:flex space-x-6">
            <a href="/" class="nav-link">首页</a>
            <a href="/docs" class="nav-link">文档</a>
            <a href="/swagger" class="nav-link">Swagger</a>
            <a href="/playground" class="nav-link">Playground</a>
            <a href="/deploy" class="nav-link">部署</a>
            <a href="/dashboard" class="nav-link">Dashboard</a>
          </div>
        </div>
        <div class="flex items-center space-x-4">
          <button onclick="toggleTheme()" class="theme-toggle" title="切换主题">
            <svg id="theme-icon-sun" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display: none;">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
            </svg>
            <svg id="theme-icon-moon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display: none;">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
            </svg>
          </button>
          <span class="hidden sm:inline text-sm" style="color: var(--text-muted);">v{APP_VERSION}</span>
          <!-- 移动端汉堡菜单按钮 -->
          <button onclick="toggleMobileMenu()" class="md:hidden theme-toggle" title="菜单">
            <svg id="menu-icon-open" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
            <svg id="menu-icon-close" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display: none;">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
    <!-- 移动端导航菜单 -->
    <div id="mobile-menu" class="md:hidden hidden" style="background: var(--bg-nav); border-top: 1px solid var(--border);">
      <div class="px-4 py-3 space-y-2">
        <a href="/" class="block nav-link py-2 px-3 rounded hover:bg-indigo-500/10">首页</a>
        <a href="/docs" class="block nav-link py-2 px-3 rounded hover:bg-indigo-500/10">文档</a>
        <a href="/swagger" class="block nav-link py-2 px-3 rounded hover:bg-indigo-500/10">Swagger</a>
        <a href="/playground" class="block nav-link py-2 px-3 rounded hover:bg-indigo-500/10">Playground</a>
        <a href="/deploy" class="block nav-link py-2 px-3 rounded hover:bg-indigo-500/10">部署</a>
        <a href="/dashboard" class="block nav-link py-2 px-3 rounded hover:bg-indigo-500/10">Dashboard</a>
      </div>
    </div>
  </nav>
  <script>
    function toggleTheme() {{
      const html = document.documentElement;
      const currentTheme = html.getAttribute('data-theme');
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
      updateThemeIcon();
    }}

    function updateThemeIcon() {{
      const theme = document.documentElement.getAttribute('data-theme');
      const sunIcon = document.getElementById('theme-icon-sun');
      const moonIcon = document.getElementById('theme-icon-moon');
      if (theme === 'dark') {{
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
      }} else {{
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
      }}
    }}

    function toggleMobileMenu() {{
      const menu = document.getElementById('mobile-menu');
      const openIcon = document.getElementById('menu-icon-open');
      const closeIcon = document.getElementById('menu-icon-close');
      const isHidden = menu.classList.contains('hidden');

      if (isHidden) {{
        menu.classList.remove('hidden');
        openIcon.style.display = 'none';
        closeIcon.style.display = 'block';
      }} else {{
        menu.classList.add('hidden');
        openIcon.style.display = 'block';
        closeIcon.style.display = 'none';
      }}
    }}

    // Initialize icon on page load
    document.addEventListener('DOMContentLoaded', updateThemeIcon);
  </script>
'''

COMMON_FOOTER = '''
  <footer style="background: var(--bg-nav); border-top: 1px solid var(--border);" class="py-6 sm:py-8 mt-12 sm:mt-16">
    <div class="max-w-7xl mx-auto px-4 text-center" style="color: var(--text-muted);">
      <p class="text-sm sm:text-base">KiroGate - OpenAI & Anthropic 兼容的 Kiro API 网关</p>
      <div class="mt-3 sm:mt-4 flex flex-wrap justify-center gap-x-4 gap-y-2 text-xs sm:text-sm">
        <span class="flex items-center gap-1">
          <span style="color: var(--text);">Deno</span>
          <a href="https://kirogate.deno.dev" class="text-indigo-400 hover:underline" target="_blank">Demo</a>
          <span>·</span>
          <a href="https://github.com/dext7r/KiroGate" class="text-indigo-400 hover:underline" target="_blank">GitHub</a>
        </span>
        <span class="hidden sm:inline" style="color: var(--border-dark);">|</span>
        <span class="flex items-center gap-1">
          <span style="color: var(--text);">Python</span>
          <a href="https://kirogate.fly.dev" class="text-indigo-400 hover:underline" target="_blank">Demo</a>
          <span>·</span>
          <a href="https://github.com/aliom-v/KiroGate" class="text-indigo-400 hover:underline" target="_blank">GitHub</a>
        </span>
      </div>
      <p class="mt-3 text-xs sm:text-sm opacity-75">欲买桂花同载酒 终不似少年游</p>
    </div>
  </footer>
'''

# 移除旧的 THEME_SCRIPT，已经集成到 COMMON_NAV 中


def render_home_page() -> str:
    """Render the home page."""
    models_json = json.dumps(AVAILABLE_MODELS)

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}

  <main class="max-w-7xl mx-auto px-4 py-8 sm:py-12">
    <!-- Hero Section -->
    <section class="text-center py-8 sm:py-16">
      <h1 class="text-3xl sm:text-4xl md:text-5xl font-bold mb-4 sm:mb-6 bg-gradient-to-r from-indigo-400 to-purple-500 bg-clip-text text-transparent">
        KiroGate API 网关
      </h1>
      <p class="text-base sm:text-xl mb-6 sm:mb-8 max-w-2xl mx-auto px-4" style="color: var(--text-muted);">
        将 OpenAI 和 Anthropic API 请求无缝代理到 Kiro (AWS CodeWhisperer)，
        支持完整的流式传输、工具调用和多模型切换。
      </p>
      <div class="flex flex-col sm:flex-row justify-center gap-3 sm:gap-4 px-4">
        <a href="/docs" class="btn-primary text-base sm:text-lg px-6 py-3">📖 查看文档</a>
        <a href="/playground" class="btn-primary text-base sm:text-lg px-6 py-3" style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text);">🎮 在线试用</a>
      </div>
    </section>

    <!-- Features Grid -->
    <section class="grid md:grid-cols-3 gap-6 py-12">
      <div class="card">
        <div class="text-3xl mb-4">🔄</div>
        <h3 class="text-xl font-semibold mb-2">双 API 兼容</h3>
        <p style="color: var(--text-muted);">同时支持 OpenAI 和 Anthropic API 格式，无需修改现有代码。</p>
      </div>
      <div class="card">
        <div class="text-3xl mb-4">⚡</div>
        <h3 class="text-xl font-semibold mb-2">流式传输</h3>
        <p style="color: var(--text-muted);">完整的 SSE 流式支持，实时获取模型响应。</p>
      </div>
      <div class="card">
        <div class="text-3xl mb-4">🔧</div>
        <h3 class="text-xl font-semibold mb-2">工具调用</h3>
        <p style="color: var(--text-muted);">支持 Function Calling，构建强大的 AI Agent。</p>
      </div>
      <div class="card">
        <div class="text-3xl mb-4">🔁</div>
        <h3 class="text-xl font-semibold mb-2">自动重试</h3>
        <p style="color: var(--text-muted);">智能处理 403/429/5xx 错误，自动刷新 Token。</p>
      </div>
      <div class="card">
        <div class="text-3xl mb-4">📊</div>
        <h3 class="text-xl font-semibold mb-2">监控面板</h3>
        <p style="color: var(--text-muted);">实时查看请求统计、响应时间和模型使用情况。</p>
      </div>
      <div class="card">
        <div class="text-3xl mb-4">👥</div>
        <h3 class="text-xl font-semibold mb-2">多租户支持</h3>
        <p style="color: var(--text-muted);">组合模式认证，多用户共享网关实例。</p>
      </div>
    </section>

    <!-- Models Chart -->
    <section class="py-12">
      <h2 class="text-2xl font-bold mb-6 text-center">📈 支持的模型</h2>
      <div class="card">
        <div id="modelsChart" style="height: 300px;"></div>
      </div>
    </section>
  </main>

  {COMMON_FOOTER}

  <script>
    // ECharts 模型展示图
    const modelsChart = echarts.init(document.getElementById('modelsChart'));
    modelsChart.setOption({{
      tooltip: {{ trigger: 'axis' }},
      xAxis: {{
        type: 'category',
        data: {models_json},
        axisLabel: {{ rotate: 45, color: '#94a3b8' }},
        axisLine: {{ lineStyle: {{ color: '#334155' }} }}
      }},
      yAxis: {{
        type: 'value',
        name: '性能指数',
        axisLabel: {{ color: '#94a3b8' }},
        axisLine: {{ lineStyle: {{ color: '#334155' }} }},
        splitLine: {{ lineStyle: {{ color: '#1e293b' }} }}
      }},
      series: [{{
        name: '模型能力',
        type: 'bar',
        data: [100, 100, 70, 90, 90, 85, 85, 80],
        itemStyle: {{
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {{ offset: 0, color: '#6366f1' }},
            {{ offset: 1, color: '#4f46e5' }}
          ])
        }}
      }}]
    }});
    window.addEventListener('resize', () => modelsChart.resize());
  </script>
</body>
</html>'''


def render_docs_page() -> str:
    """Render the API documentation page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}

  <main class="max-w-7xl mx-auto px-4 py-12">
    <h1 class="text-4xl font-bold mb-8">📖 API 文档</h1>

    <div class="space-y-8">
      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">🔑 认证</h2>
        <p style="color: var(--text-muted);" class="mb-4">所有 API 请求需要在 Header 中携带 API Key。支持两种认证模式：</p>

        <h3 class="text-lg font-medium mb-2 text-indigo-400">模式 1: 简单模式（使用服务器配置的 REFRESH_TOKEN）</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm mb-4">
# OpenAI 格式
Authorization: Bearer YOUR_PROXY_API_KEY

# Anthropic 格式
x-api-key: YOUR_PROXY_API_KEY</pre>

        <h3 class="text-lg font-medium mb-2 text-indigo-400">模式 2: 组合模式（用户自带 REFRESH_TOKEN，无需服务器配置）✨ 推荐</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm">
# OpenAI 格式
Authorization: Bearer YOUR_PROXY_API_KEY:YOUR_REFRESH_TOKEN

# Anthropic 格式
x-api-key: YOUR_PROXY_API_KEY:YOUR_REFRESH_TOKEN</pre>

        <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg mt-4">
          <p class="text-sm" style="color: var(--text-muted);">
            <strong>💡 优先级说明：</strong>
          </p>
          <ul class="text-sm mt-2 space-y-1" style="color: var(--text-muted);">
            <li>• <strong>优先使用组合模式</strong>：如果 API Key 包含冒号 <code>:</code>，自动识别为 <code>PROXY_API_KEY:REFRESH_TOKEN</code> 格式</li>
            <li>• <strong>回退到简单模式</strong>：如果不包含冒号，使用服务器配置的全局 REFRESH_TOKEN</li>
            <li>• <strong>多租户支持</strong>：组合模式允许多个用户使用各自的 REFRESH_TOKEN，无需修改服务器配置</li>
            <li>• <strong>缓存优化</strong>：每个用户的认证信息会被缓存（最多100个用户），提升性能</li>
          </ul>
        </div>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">📡 端点列表</h2>
        <div class="space-y-4">
          <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg">
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2 py-1 text-xs font-bold rounded bg-green-500 text-white">GET</span>
              <code>/</code>
            </div>
            <p class="text-sm" style="color: var(--text-muted);">健康检查端点</p>
          </div>
          <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg">
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2 py-1 text-xs font-bold rounded bg-green-500 text-white">GET</span>
              <code>/health</code>
            </div>
            <p class="text-sm" style="color: var(--text-muted);">详细健康检查，返回 token 状态和缓存信息</p>
          </div>
          <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg">
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2 py-1 text-xs font-bold rounded bg-green-500 text-white">GET</span>
              <code>/v1/models</code>
            </div>
            <p class="text-sm" style="color: var(--text-muted);">获取可用模型列表 (需要认证)</p>
          </div>
          <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg">
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2 py-1 text-xs font-bold rounded bg-blue-500 text-white">POST</span>
              <code>/v1/chat/completions</code>
            </div>
            <p class="text-sm" style="color: var(--text-muted);">OpenAI 兼容的聊天补全 API (需要认证)</p>
          </div>
          <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg">
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2 py-1 text-xs font-bold rounded bg-blue-500 text-white">POST</span>
              <code>/v1/messages</code>
            </div>
            <p class="text-sm" style="color: var(--text-muted);">Anthropic 兼容的消息 API (需要认证)</p>
          </div>
        </div>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">💡 使用示例</h2>
        <h3 class="text-lg font-medium mb-2 text-indigo-400">OpenAI SDK (Python)</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm mb-4">
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_PROXY_API_KEY"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-5",
    messages=[{{"role": "user", "content": "Hello!"}}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")</pre>

        <h3 class="text-lg font-medium mb-2 text-indigo-400">Anthropic SDK (Python)</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm mb-4">
import anthropic

client = anthropic.Anthropic(
    base_url="http://localhost:8000",
    api_key="YOUR_PROXY_API_KEY"
)

message = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{{"role": "user", "content": "Hello!"}}]
)

print(message.content[0].text)</pre>

        <h3 class="text-lg font-medium mb-2 text-indigo-400">cURL</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm">
curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer YOUR_PROXY_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "claude-sonnet-4-5",
    "messages": [{{"role": "user", "content": "Hello!"}}]
  }}'</pre>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">🤖 可用模型</h2>
        <ul class="grid md:grid-cols-2 gap-2">
          {"".join([f'<li style="background: var(--bg-input); border: 1px solid var(--border);" class="px-4 py-2 rounded text-sm"><code>{m}</code></li>' for m in AVAILABLE_MODELS])}
        </ul>
      </section>
    </div>
  </main>

  {COMMON_FOOTER}
</body>
</html>'''


def render_playground_page() -> str:
    """Render the API playground page."""
    models_options = "".join([f'<option value="{m}">{m}</option>' for m in AVAILABLE_MODELS])

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}

  <main class="max-w-7xl mx-auto px-4 py-12">
    <h1 class="text-4xl font-bold mb-8">🎮 API Playground</h1>

    <div class="grid md:grid-cols-2 gap-6">
      <!-- Request Panel -->
      <div class="card">
        <h2 class="text-xl font-semibold mb-4">请求配置</h2>

        <div class="space-y-4">
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted);">API Key</label>
            <input type="password" id="apiKey" style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="w-full rounded px-3 py-2" placeholder="PROXY_API_KEY 或 PROXY_API_KEY:REFRESH_TOKEN" oninput="updateAuthMode()">
            <div id="authModeDisplay" class="mt-2 text-sm flex items-center gap-2">
              <span id="authModeIcon">🔒</span>
              <span id="authModeText" style="color: var(--text-muted);">输入 API Key 后显示认证模式</span>
            </div>
          </div>

          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted);">模型</label>
            <select id="model" style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="w-full rounded px-3 py-2">
              {models_options}
            </select>
          </div>

          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted);">消息内容</label>
            <textarea id="message" rows="4" style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="w-full rounded px-3 py-2" placeholder="输入你的消息...">Hello! Please introduce yourself briefly.</textarea>
          </div>

          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2">
              <input type="checkbox" id="stream" checked class="rounded">
              <span class="text-sm">流式响应</span>
            </label>
            <label class="flex items-center gap-2">
              <input type="radio" name="apiFormat" value="openai" checked>
              <span class="text-sm">OpenAI 格式</span>
            </label>
            <label class="flex items-center gap-2">
              <input type="radio" name="apiFormat" value="anthropic">
              <span class="text-sm">Anthropic 格式</span>
            </label>
          </div>

          <button id="sendBtn" onclick="sendRequest()" class="btn-primary w-full py-3 text-base sm:text-lg">
            <span id="sendBtnText">🚀 发送请求</span>
            <span id="sendBtnLoading" class="hidden"><span class="loading-spinner mr-2"></span>请求中...</span>
          </button>
        </div>
      </div>

      <!-- Response Panel -->
      <div class="card">
        <h2 class="text-lg sm:text-xl font-semibold mb-4">响应结果</h2>
        <div id="response" style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="rounded p-3 sm:p-4 min-h-[250px] sm:min-h-[300px] whitespace-pre-wrap text-xs sm:text-sm font-mono overflow-auto">
          <span style="color: var(--text-muted);">响应将显示在这里...</span>
        </div>
        <div id="stats" class="mt-3 sm:mt-4 text-xs sm:text-sm" style="color: var(--text-muted);"></div>
      </div>
    </div>
  </main>

  {COMMON_FOOTER}

  <script>
    function updateAuthMode() {{
      const apiKey = document.getElementById('apiKey').value;
      const iconEl = document.getElementById('authModeIcon');
      const textEl = document.getElementById('authModeText');

      if (!apiKey) {{
        iconEl.textContent = '🔒';
        textEl.textContent = '输入 API Key 后显示认证模式';
        textEl.style.color = 'var(--text-muted)';
        return;
      }}

      if (apiKey.includes(':')) {{
        iconEl.textContent = '👥';
        textEl.innerHTML = '<span style="color: #22c55e; font-weight: 600;">组合模式</span> <span style="color: var(--text-muted);">- PROXY_API_KEY:REFRESH_TOKEN（多租户）</span>';
      }} else {{
        iconEl.textContent = '🔑';
        textEl.innerHTML = '<span style="color: #3b82f6; font-weight: 600;">简单模式</span> <span style="color: var(--text-muted);">- 使用服务器配置的 REFRESH_TOKEN</span>';
      }}
    }}

    async function sendRequest() {{
      const apiKey = document.getElementById('apiKey').value;
      const model = document.getElementById('model').value;
      const message = document.getElementById('message').value;
      const stream = document.getElementById('stream').checked;
      const format = document.querySelector('input[name="apiFormat"]:checked').value;

      const responseEl = document.getElementById('response');
      const statsEl = document.getElementById('stats');
      const sendBtn = document.getElementById('sendBtn');
      const sendBtnText = document.getElementById('sendBtnText');
      const sendBtnLoading = document.getElementById('sendBtnLoading');

      // 显示加载状态
      sendBtn.disabled = true;
      sendBtnText.classList.add('hidden');
      sendBtnLoading.classList.remove('hidden');
      responseEl.innerHTML = '<span class="loading-pulse" style="color: var(--text-muted);">请求中...</span>';
      statsEl.textContent = '';

      const startTime = Date.now();

      try {{
        const endpoint = format === 'openai' ? '/v1/chat/completions' : '/v1/messages';
        const headers = {{
          'Content-Type': 'application/json',
        }};

        if (format === 'openai') {{
          headers['Authorization'] = 'Bearer ' + apiKey;
        }} else {{
          headers['x-api-key'] = apiKey;
        }}

        const body = format === 'openai' ? {{
          model,
          messages: [{{ role: 'user', content: message }}],
          stream
        }} : {{
          model,
          max_tokens: 1024,
          messages: [{{ role: 'user', content: message }}],
          stream
        }};

        const response = await fetch(endpoint, {{
          method: 'POST',
          headers,
          body: JSON.stringify(body)
        }});

        if (!response.ok) {{
          const error = await response.text();
          throw new Error(error);
        }}

        if (stream) {{
          responseEl.textContent = '';
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let fullContent = '';
          let buffer = '';

          while (true) {{
            const {{ done, value }} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {{ stream: true }});
            const lines = buffer.split('\\n');
            buffer = lines.pop() || '';

            for (let i = 0; i < lines.length; i++) {{
              const line = lines[i].trim();

              if (format === 'openai') {{
                if (line.startsWith('data: ') && !line.includes('[DONE]')) {{
                  try {{
                    const data = JSON.parse(line.slice(6));
                    const content = data.choices?.[0]?.delta?.content || '';
                    fullContent += content;
                  }} catch {{}}
                }}
              }} else if (format === 'anthropic') {{
                if (line.startsWith('event: content_block_delta')) {{
                  const nextLine = lines[i + 1];
                  if (nextLine && nextLine.trim().startsWith('data: ')) {{
                    try {{
                      const data = JSON.parse(nextLine.trim().slice(6));
                      if (data.delta?.text) {{
                        fullContent += data.delta.text;
                      }}
                    }} catch {{}}
                  }}
                }}
              }}
            }}
            responseEl.textContent = fullContent;
          }}
        }} else {{
          const data = await response.json();
          if (format === 'openai') {{
            responseEl.textContent = data.choices?.[0]?.message?.content || JSON.stringify(data, null, 2);
          }} else {{
            const text = data.content?.find(c => c.type === 'text')?.text || JSON.stringify(data, null, 2);
            responseEl.textContent = text;
          }}
        }}

        const duration = ((Date.now() - startTime) / 1000).toFixed(2);
        statsEl.textContent = '耗时: ' + duration + 's';

      }} catch (e) {{
        responseEl.textContent = '错误: ' + e.message;
      }} finally {{
        // 恢复按钮状态
        sendBtn.disabled = false;
        sendBtnText.classList.remove('hidden');
        sendBtnLoading.classList.add('hidden');
      }}
    }}
  </script>
</body>
</html>'''


def render_deploy_page() -> str:
    """Render the deployment guide page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}

  <main class="max-w-7xl mx-auto px-4 py-12">
    <h1 class="text-4xl font-bold mb-8">🚀 部署指南</h1>

    <div class="space-y-8">
      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">📋 环境要求</h2>
        <ul class="list-disc list-inside space-y-2" style="color: var(--text-muted);">
          <li>Python 3.10+</li>
          <li>pip 或 poetry</li>
          <li>网络连接（需访问 AWS CodeWhisperer API）</li>
        </ul>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">⚙️ 环境变量配置</h2>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm">
# 必填项
PROXY_API_KEY="your-secret-api-key"      # 代理服务器密码

# 可选项（仅简单模式需要）
# 如果使用组合模式（PROXY_API_KEY:REFRESH_TOKEN），可以不配置此项
REFRESH_TOKEN="your-kiro-refresh-token"  # Kiro Refresh Token

# 其他可选配置
KIRO_REGION="us-east-1"                  # AWS 区域
PROFILE_ARN="arn:aws:..."                # Profile ARN
LOG_LEVEL="INFO"                          # 日志级别

# 或使用凭证文件
KIRO_CREDS_FILE="~/.kiro/credentials.json"</pre>

        <div style="background: var(--bg-input); border: 1px solid var(--border);" class="p-4 rounded-lg mt-4">
          <p class="text-sm font-semibold mb-2" style="color: var(--text);">配置说明：</p>
          <ul class="text-sm space-y-1" style="color: var(--text-muted);">
            <li>• <strong>简单模式</strong>：必须配置 <code>REFRESH_TOKEN</code> 环境变量</li>
            <li>• <strong>组合模式（推荐）</strong>：无需配置 <code>REFRESH_TOKEN</code>，用户在请求中直接传递</li>
            <li>• <strong>多租户部署</strong>：使用组合模式可以让多个用户共享同一网关实例</li>
          </ul>
        </div>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">🐍 本地运行</h2>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm">
# 克隆仓库
git clone https://github.com/dext7r/KiroGate.git
cd KiroGate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写配置

# 启动服务
python main.py</pre>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4 flex items-center gap-2">
          <span>🐳</span>
          <span>Docker 部署</span>
        </h2>
        <h3 class="text-lg font-medium mb-2 text-indigo-400">简单模式</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm">
docker build -t kirogate .
docker run -d \\
  -p 8000:8000 \\
  -e PROXY_API_KEY="your-key" \\
  -e REFRESH_TOKEN="your-token" \\
  kirogate</pre>

        <h3 class="text-lg font-medium mb-2 mt-6 text-indigo-400">组合模式（推荐 - 无需配置 REFRESH_TOKEN）</h3>
        <pre style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);" class="p-4 rounded-lg overflow-x-auto text-sm">
docker build -t kirogate .
docker run -d \\
  -p 8000:8000 \\
  -e PROXY_API_KEY="your-key" \\
  kirogate

# 用户在请求中传递 PROXY_API_KEY:REFRESH_TOKEN</pre>
      </section>

      <section class="card">
        <h2 class="text-2xl font-semibold mb-4">🔐 获取 Refresh Token</h2>
        <div style="background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.1)); border: 1px solid var(--primary);" class="p-4 rounded-lg mb-4">
          <p class="text-sm font-semibold mb-2" style="color: var(--text);">✨ 推荐工具：Kiro Account Manager</p>
          <p class="text-sm mb-2" style="color: var(--text-muted);">
            使用 <a href="https://github.com/chaogei/Kiro-account-manager" class="text-indigo-400 hover:underline font-medium" target="_blank">Kiro Account Manager</a>
            可以轻松管理和获取 Refresh Token，无需手动抓包。
          </p>
          <a href="https://github.com/chaogei/Kiro-account-manager" target="_blank" class="inline-flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300">
            <span>前往 GitHub 查看 →</span>
          </a>
        </div>

        <p class="text-sm mb-3" style="color: var(--text-muted);">或者手动获取：</p>
        <ol class="list-decimal list-inside space-y-2" style="color: var(--text-muted);">
          <li>安装并打开 <a href="https://kiro.dev/" class="text-indigo-400 hover:underline">Kiro IDE</a></li>
          <li>登录你的账号</li>
          <li>使用开发者工具或代理拦截流量</li>
          <li>查找发往 <code style="background: var(--bg-input); border: 1px solid var(--border);" class="px-2 py-1 rounded">prod.us-east-1.auth.desktop.kiro.dev/refreshToken</code> 的请求</li>
          <li>复制请求体中的 refreshToken 值</li>
        </ol>
      </section>
    </div>
  </main>

  {COMMON_FOOTER}
</body>
</html>'''


def render_status_page(status_data: dict) -> str:
    """Render the status page."""
    status_color = "#22c55e" if status_data.get("status") == "healthy" else "#ef4444"
    token_color = "#22c55e" if status_data.get("token_valid") else "#ef4444"

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}
  <meta http-equiv="refresh" content="30">
</head>
<body>
  {COMMON_NAV}

  <main class="max-w-4xl mx-auto px-4 py-12">
    <h1 class="text-4xl font-bold mb-8">📊 系统状态</h1>

    <div class="grid md:grid-cols-2 gap-6 mb-8">
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">服务状态</h2>
        <div class="flex items-center gap-3">
          <div class="w-4 h-4 rounded-full" style="background: {status_color};"></div>
          <span class="text-2xl font-bold">{status_data.get("status", "unknown").upper()}</span>
        </div>
      </div>
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">Token 状态</h2>
        <div class="flex items-center gap-3">
          <div class="w-4 h-4 rounded-full" style="background: {token_color};"></div>
          <span class="text-2xl font-bold">{"有效" if status_data.get("token_valid") else "无效/未配置"}</span>
        </div>
      </div>
    </div>

    <div class="card mb-8">
      <h2 class="text-xl font-semibold mb-4">详细信息</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-sm" style="color: var(--text-muted);">版本</p>
          <p class="font-mono">{status_data.get("version", "unknown")}</p>
        </div>
        <div>
          <p class="text-sm" style="color: var(--text-muted);">缓存大小</p>
          <p class="font-mono">{status_data.get("cache_size", 0)}</p>
        </div>
        <div>
          <p class="text-sm" style="color: var(--text-muted);">最后更新</p>
          <p class="font-mono text-sm">{status_data.get("cache_last_update", "N/A")}</p>
        </div>
        <div>
          <p class="text-sm" style="color: var(--text-muted);">时间戳</p>
          <p class="font-mono text-sm">{status_data.get("timestamp", "N/A")}</p>
        </div>
      </div>
    </div>

    <p class="text-sm text-center" style="color: var(--text-muted);">页面每 30 秒自动刷新</p>
  </main>

  {COMMON_FOOTER}
</body>
</html>'''


def render_dashboard_page() -> str:
    """Render the dashboard page with metrics."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}
<style>.mc{{background:var(--bg-card);border:1px solid var(--border);border-radius:.75rem;padding:1rem;text-align:center}}.mc:hover{{border-color:var(--primary)}}.mi{{font-size:1.5rem;margin-bottom:.5rem}}</style>
</head>
<body>
  {COMMON_NAV}
  <main class="max-w-7xl mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">📊 Dashboard</h1>
      <button onclick="refreshData()" class="btn-primary">🔄 刷新</button>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <div class="mc"><div class="mi">📈</div><div class="text-2xl font-bold text-indigo-400" id="totalRequests">-</div><div class="text-xs" style="color:var(--text-muted)">总请求</div></div>
      <div class="mc"><div class="mi">✅</div><div class="text-2xl font-bold text-green-400" id="successRate">-</div><div class="text-xs" style="color:var(--text-muted)">成功率</div></div>
      <div class="mc"><div class="mi">⏱️</div><div class="text-2xl font-bold text-yellow-400" id="avgResponseTime">-</div><div class="text-xs" style="color:var(--text-muted)">平均耗时</div></div>
      <div class="mc"><div class="mi">🕐</div><div class="text-2xl font-bold text-purple-400" id="uptime">-</div><div class="text-xs" style="color:var(--text-muted)">运行时长</div></div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <div class="mc"><div class="mi">⚡</div><div class="text-xl font-bold text-blue-400" id="streamRequests">-</div><div class="text-xs" style="color:var(--text-muted)">流式请求</div></div>
      <div class="mc"><div class="mi">💾</div><div class="text-xl font-bold text-cyan-400" id="nonStreamRequests">-</div><div class="text-xs" style="color:var(--text-muted)">非流式</div></div>
      <div class="mc"><div class="mi">❌</div><div class="text-xl font-bold text-red-400" id="failedRequests">-</div><div class="text-xs" style="color:var(--text-muted)">失败</div></div>
      <div class="mc"><div class="mi">🤖</div><div class="text-xl font-bold text-emerald-400" id="topModel">-</div><div class="text-xs" style="color:var(--text-muted)">热门模型</div></div>
    </div>
    <div class="grid grid-cols-2 gap-3 mb-6">
      <div class="mc"><div class="mi">🟢</div><div class="text-xl font-bold text-green-400" id="openaiRequests">-</div><div class="text-xs" style="color:var(--text-muted)">OpenAI API</div></div>
      <div class="mc"><div class="mi">🟣</div><div class="text-xl font-bold text-purple-400" id="anthropicRequests">-</div><div class="text-xs" style="color:var(--text-muted)">Anthropic API</div></div>
    </div>
    <div class="grid lg:grid-cols-2 gap-4 mb-6">
      <div class="card"><h2 class="text-lg font-semibold mb-3">📈 耗时趋势</h2><div id="latencyChart" style="height:250px"></div></div>
      <div class="card"><h2 class="text-lg font-semibold mb-3">📊 状态分布</h2><div style="height:250px;position:relative"><canvas id="statusChart"></canvas></div></div>
    </div>
    <div class="card">
      <h2 class="text-lg font-semibold mb-3">📋 最近请求</h2>
      <div class="table-responsive"><table class="w-full text-xs"><thead><tr class="text-left" style="color:var(--text-muted);border-bottom:1px solid var(--border)"><th class="py-2 px-2">时间</th><th class="py-2 px-2">API</th><th class="py-2 px-2">路径</th><th class="py-2 px-2">状态</th><th class="py-2 px-2">耗时</th><th class="py-2 px-2">模型</th></tr></thead><tbody id="recentRequestsTable"><tr><td colspan="6" class="py-4 text-center" style="color:var(--text-muted)">加载中...</td></tr></tbody></table></div>
    </div>
  </main>
  {COMMON_FOOTER}
  <script>
let lc,sc;
async function refreshData(){{try{{const r=await fetch('/api/metrics'),d=await r.json();document.getElementById('totalRequests').textContent=d.totalRequests||0;document.getElementById('successRate').textContent=d.totalRequests>0?((d.successRequests/d.totalRequests)*100).toFixed(1)+'%':'0%';document.getElementById('avgResponseTime').textContent=(d.avgResponseTime||0).toFixed(0)+'ms';const u=Math.floor((Date.now()-d.startTime)/1000);document.getElementById('uptime').textContent=Math.floor(u/3600)+'h '+Math.floor((u%3600)/60)+'m';document.getElementById('streamRequests').textContent=d.streamRequests||0;document.getElementById('nonStreamRequests').textContent=d.nonStreamRequests||0;document.getElementById('failedRequests').textContent=d.failedRequests||0;const m=Object.entries(d.modelUsage||{{}}).sort((a,b)=>b[1]-a[1])[0];document.getElementById('topModel').textContent=m?m[0].split('-').slice(-2).join('-'):'-';document.getElementById('openaiRequests').textContent=(d.apiTypeUsage||{{}}).openai||0;document.getElementById('anthropicRequests').textContent=(d.apiTypeUsage||{{}}).anthropic||0;const rt=d.responseTimes||[];lc.setOption({{xAxis:{{data:rt.map((_,i)=>i+1)}},series:[{{data:rt}}]}});sc.data.datasets[0].data=[d.successRequests||0,d.failedRequests||0];sc.update();const rq=(d.recentRequests||[]).slice(-10).reverse(),tb=document.getElementById('recentRequestsTable');tb.innerHTML=rq.length?rq.map(q=>'<tr style="border-bottom:1px solid var(--border)"><td class="py-2 px-2">'+new Date(q.timestamp).toLocaleTimeString()+'</td><td class="py-2 px-2"><span class="text-xs px-1 rounded '+(q.apiType==='anthropic'?'bg-purple-600':'bg-green-600')+' text-white">'+q.apiType+'</span></td><td class="py-2 px-2 font-mono">'+q.path+'</td><td class="py-2 px-2 '+(q.status<400?'text-green-400':'text-red-400')+'">'+q.status+'</td><td class="py-2 px-2">'+q.duration.toFixed(0)+'ms</td><td class="py-2 px-2">'+(q.model||'-')+'</td></tr>').join(''):'<tr><td colspan="6" class="py-4 text-center" style="color:var(--text-muted)">暂无</td></tr>'}}catch(e){{console.error(e)}}}}
lc=echarts.init(document.getElementById('latencyChart'));lc.setOption({{tooltip:{{trigger:'axis'}},xAxis:{{type:'category',data:[],axisLabel:{{color:'#94a3b8'}}}},yAxis:{{type:'value',name:'ms',axisLabel:{{color:'#94a3b8'}}}},series:[{{type:'line',smooth:true,data:[],areaStyle:{{color:'rgba(99,102,241,0.2)'}},lineStyle:{{color:'#6366f1'}}}}]}});
sc=new Chart(document.getElementById('statusChart'),{{type:'doughnut',data:{{labels:['成功','失败'],datasets:[{{data:[0,0],backgroundColor:['#22c55e','#ef4444'],borderWidth:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#94a3b8'}}}}}}}}}});
refreshData();setInterval(refreshData,5000);window.addEventListener('resize',()=>lc.resize());
  </script>
</body>
</html>'''


def render_swagger_page() -> str:
    """Render the Swagger UI page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KiroGate API - Swagger UI</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🚀</text></svg>">
  <link rel="stylesheet" href="{PROXY_BASE}/proxy/cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <style>
    body {{ margin: 0; background: #fafafa; }}
    .swagger-ui .topbar {{ display: none; }}
    .custom-header {{
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: white;
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .custom-header h1 {{ margin: 0; font-size: 1.5rem; font-weight: bold; }}
    .custom-header a {{ color: white; text-decoration: none; opacity: 0.8; }}
    .custom-header a:hover {{ opacity: 1; }}
    .header-links {{ display: flex; gap: 1.5rem; align-items: center; }}
    .header-links a {{ font-size: 0.9rem; }}
    .version-badge {{
      background: rgba(255,255,255,0.2);
      padding: 0.25rem 0.5rem;
      border-radius: 0.25rem;
      font-size: 0.8rem;
    }}
    /* Swagger UI 主题调整 */
    .swagger-ui .info .title {{ font-size: 2rem; }}
    .swagger-ui .opblock-tag {{ font-size: 1.2rem; }}
    .swagger-ui .opblock.opblock-post {{ border-color: #49cc90; background: rgba(73, 204, 144, 0.1); }}
    .swagger-ui .opblock.opblock-get {{ border-color: #61affe; background: rgba(97, 175, 254, 0.1); }}
  </style>
</head>
<body>
  <div class="custom-header">
    <div style="display: flex; align-items: center; gap: 1rem;">
      <h1>⚡ KiroGate API</h1>
      <span class="version-badge">v{APP_VERSION}</span>
    </div>
    <div class="header-links">
      <a href="/">首页</a>
      <a href="/docs">文档</a>
      <a href="/playground">Playground</a>
      <a href="/dashboard">Dashboard</a>
      <a href="https://github.com/dext7r/KiroGate" target="_blank">GitHub</a>
    </div>
  </div>
  <div id="swagger-ui"></div>
  <script src="{PROXY_BASE}/proxy/cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {{
      SwaggerUIBundle({{
        url: "/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 1,
        docExpansion: "list",
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        syntaxHighlight: {{
          activate: true,
          theme: "monokai"
        }}
      }});
    }}
  </script>
</body>
</html>'''
