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
<style>
.mc{{background:var(--bg-card);border:1px solid var(--border);border-radius:.75rem;padding:1.25rem;text-align:center;transition:all .3s ease}}
.mc:hover{{border-color:var(--primary);transform:translateY(-2px);box-shadow:0 8px 25px rgba(99,102,241,0.15)}}
.mi{{font-size:1.75rem;margin-bottom:.75rem}}
.stat-value{{font-size:1.75rem;font-weight:700;line-height:1.2}}
.stat-label{{font-size:.75rem;margin-top:.5rem;opacity:.7}}
.chart-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:.75rem;padding:1.5rem}}
.chart-title{{font-size:1rem;font-weight:600;margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}}
</style>
</head>
<body>
  {COMMON_NAV}
  <main class="max-w-7xl mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-8">
      <h1 class="text-3xl font-bold flex items-center gap-3">
        <span class="text-4xl">📊</span>
        <span>Dashboard</span>
      </h1>
      <button onclick="refreshData()" class="btn-primary flex items-center gap-2">
        <span>🔄</span> 刷新
      </button>
    </div>

    <!-- Primary Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="mc">
        <div class="mi">📈</div>
        <div class="stat-value text-indigo-400" id="totalRequests">-</div>
        <div class="stat-label" style="color:var(--text-muted)">总请求</div>
      </div>
      <div class="mc">
        <div class="mi">✅</div>
        <div class="stat-value text-green-400" id="successRate">-</div>
        <div class="stat-label" style="color:var(--text-muted)">成功率</div>
      </div>
      <div class="mc">
        <div class="mi">⏱️</div>
        <div class="stat-value text-yellow-400" id="avgResponseTime">-</div>
        <div class="stat-label" style="color:var(--text-muted)">平均耗时</div>
      </div>
      <div class="mc">
        <div class="mi">🕐</div>
        <div class="stat-value text-purple-400" id="uptime">-</div>
        <div class="stat-label" style="color:var(--text-muted)">运行时长</div>
      </div>
    </div>

    <!-- Secondary Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="mc">
        <div class="mi">⚡</div>
        <div class="stat-value text-blue-400" style="font-size:1.5rem" id="streamRequests">-</div>
        <div class="stat-label" style="color:var(--text-muted)">流式请求</div>
      </div>
      <div class="mc">
        <div class="mi">💾</div>
        <div class="stat-value text-cyan-400" style="font-size:1.5rem" id="nonStreamRequests">-</div>
        <div class="stat-label" style="color:var(--text-muted)">非流式请求</div>
      </div>
      <div class="mc">
        <div class="mi">❌</div>
        <div class="stat-value text-red-400" style="font-size:1.5rem" id="failedRequests">-</div>
        <div class="stat-label" style="color:var(--text-muted)">失败请求</div>
      </div>
      <div class="mc">
        <div class="mi">🤖</div>
        <div class="stat-value text-emerald-400" style="font-size:1.25rem" id="topModel">-</div>
        <div class="stat-label" style="color:var(--text-muted)">热门模型</div>
      </div>
    </div>

    <!-- API Type Stats -->
    <div class="grid grid-cols-2 gap-4 mb-8">
      <div class="mc">
        <div class="mi">🟢</div>
        <div class="stat-value text-green-400" style="font-size:1.5rem" id="openaiRequests">-</div>
        <div class="stat-label" style="color:var(--text-muted)">OpenAI API</div>
      </div>
      <div class="mc">
        <div class="mi">🟣</div>
        <div class="stat-value text-purple-400" style="font-size:1.5rem" id="anthropicRequests">-</div>
        <div class="stat-label" style="color:var(--text-muted)">Anthropic API</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid lg:grid-cols-2 gap-6 mb-8">
      <div class="chart-card">
        <h2 class="chart-title">📈 24小时请求趋势</h2>
        <div id="latencyChart" style="height:280px"></div>
      </div>
      <div class="chart-card">
        <h2 class="chart-title">📊 状态分布</h2>
        <div style="height:280px;position:relative">
          <canvas id="statusChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Recent Requests -->
    <div class="chart-card">
      <h2 class="chart-title">📋 最近请求</h2>
      <div class="table-responsive">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left" style="color:var(--text-muted);border-bottom:1px solid var(--border)">
              <th class="py-3 px-3">时间</th>
              <th class="py-3 px-3">API</th>
              <th class="py-3 px-3">路径</th>
              <th class="py-3 px-3">状态</th>
              <th class="py-3 px-3">耗时</th>
              <th class="py-3 px-3">模型</th>
            </tr>
          </thead>
          <tbody id="recentRequestsTable">
            <tr><td colspan="6" class="py-6 text-center" style="color:var(--text-muted)">加载中...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>
  {COMMON_FOOTER}
  <script>
let lc,sc;
const START_TIME = new Date('2025-12-25T00:00:00').getTime();
async function refreshData(){{
  try{{
    const r=await fetch('/api/metrics'),d=await r.json();
    document.getElementById('totalRequests').textContent=d.totalRequests||0;
    document.getElementById('successRate').textContent=d.totalRequests>0?((d.successRequests/d.totalRequests)*100).toFixed(1)+'%':'0%';
    document.getElementById('avgResponseTime').textContent=(d.avgResponseTime||0).toFixed(0)+'ms';

    // Calculate uptime from fixed start time
    const now=Date.now();
    const u=Math.floor((now-START_TIME)/1000);
    const days=Math.floor(u/86400);
    const hours=Math.floor((u%86400)/3600);
    const mins=Math.floor((u%3600)/60);
    document.getElementById('uptime').textContent=days>0?days+'d '+hours+'h':hours+'h '+mins+'m';

    document.getElementById('streamRequests').textContent=d.streamRequests||0;
    document.getElementById('nonStreamRequests').textContent=d.nonStreamRequests||0;
    document.getElementById('failedRequests').textContent=d.failedRequests||0;

    const m=Object.entries(d.modelUsage||{{}}).filter(e=>e[0]!=='unknown').sort((a,b)=>b[1]-a[1])[0];
    const formatModel=(name)=>{{
      if(!name)return'-';
      let n=name.replace(/-\\d{{8}}$/,'');
      const parts=n.split('-');
      if(parts.length<=2)return n;
      if(n.includes('claude')){{
        const ver=parts.filter(p=>/^\\d+$/.test(p)).join('.');
        const type=parts.find(p=>['opus','sonnet','haiku'].includes(p))||parts[parts.length-1];
        return ver?type+'-'+ver:type;
      }}
      return parts.slice(-2).join('-');
    }};
    document.getElementById('topModel').textContent=m?formatModel(m[0]):'-';
    document.getElementById('openaiRequests').textContent=(d.apiTypeUsage||{{}}).openai||0;
    document.getElementById('anthropicRequests').textContent=(d.apiTypeUsage||{{}}).anthropic||0;

    // Update 24-hour chart
    const hr=d.hourlyRequests||[];
    lc.setOption({{
      xAxis:{{data:hr.map(h=>new Date(h.hour).getHours()+':00')}},
      series:[{{data:hr.map(h=>h.count)}}]
    }});

    sc.data.datasets[0].data=[d.successRequests||0,d.failedRequests||0];
    sc.update();

    const rq=(d.recentRequests||[]).slice(-10).reverse();
    const tb=document.getElementById('recentRequestsTable');
    tb.innerHTML=rq.length?rq.map(q=>`
      <tr style="border-bottom:1px solid var(--border)">
        <td class="py-3 px-3">${{new Date(q.timestamp).toLocaleTimeString()}}</td>
        <td class="py-3 px-3"><span class="text-xs px-2 py-1 rounded ${{q.apiType==='anthropic'?'bg-purple-600':'bg-green-600'}} text-white">${{q.apiType}}</span></td>
        <td class="py-3 px-3 font-mono text-xs">${{q.path}}</td>
        <td class="py-3 px-3 ${{q.status<400?'text-green-400':'text-red-400'}}">${{q.status}}</td>
        <td class="py-3 px-3">${{q.duration.toFixed(0)}}ms</td>
        <td class="py-3 px-3">${{q.model||'-'}}</td>
      </tr>`).join(''):'<tr><td colspan="6" class="py-6 text-center" style="color:var(--text-muted)">暂无请求</td></tr>';
  }}catch(e){{console.error(e)}}
}}

lc=echarts.init(document.getElementById('latencyChart'));
lc.setOption({{
  tooltip:{{trigger:'axis',backgroundColor:'rgba(30,41,59,0.95)',borderColor:'#334155',textStyle:{{color:'#e2e8f0'}}}},
  grid:{{left:'3%',right:'4%',bottom:'3%',containLabel:true}},
  xAxis:{{type:'category',data:[],axisLabel:{{color:'#94a3b8',fontSize:11}},axisLine:{{lineStyle:{{color:'#334155'}}}}}},
  yAxis:{{type:'value',name:'请求数',nameTextStyle:{{color:'#94a3b8'}},axisLabel:{{color:'#94a3b8'}},axisLine:{{lineStyle:{{color:'#334155'}}}},splitLine:{{lineStyle:{{color:'#1e293b'}}}}}},
  series:[{{
    type:'bar',
    data:[],
    itemStyle:{{
      color:new echarts.graphic.LinearGradient(0,0,0,1,[
        {{offset:0,color:'#818cf8'}},
        {{offset:1,color:'#6366f1'}}
      ]),
      borderRadius:[4,4,0,0]
    }},
    emphasis:{{itemStyle:{{color:'#a5b4fc'}}}}
  }}]
}});

sc=new Chart(document.getElementById('statusChart'),{{
  type:'doughnut',
  data:{{
    labels:['成功','失败'],
    datasets:[{{data:[0,0],backgroundColor:['#22c55e','#ef4444'],borderWidth:0,hoverOffset:8}}]
  }},
  options:{{
    responsive:true,
    maintainAspectRatio:false,
    cutout:'65%',
    plugins:{{
      legend:{{position:'bottom',labels:{{color:'#94a3b8',padding:20,font:{{size:13}}}}}}
    }}
  }}
}});

refreshData();
setInterval(refreshData,5000);
window.addEventListener('resize',()=>lc.resize());
  </script>
</body>
</html>'''


def render_swagger_page() -> str:
    """Render the Swagger UI page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
  {COMMON_HEAD}
  <link rel="stylesheet" href="{PROXY_BASE}/proxy/cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <style>
    .swagger-ui .topbar {{ display: none; }}
    .swagger-ui .info .title {{ font-size: 2rem; }}
    .swagger-ui .opblock-tag {{ font-size: 1.2rem; }}
    .swagger-ui .opblock.opblock-post {{ border-color: #49cc90; background: rgba(73, 204, 144, 0.1); }}
    .swagger-ui .opblock.opblock-get {{ border-color: #61affe; background: rgba(97, 175, 254, 0.1); }}
    .swagger-ui {{ background: var(--bg); }}
    .swagger-ui .info .title, .swagger-ui .info .base-url {{ color: var(--text); }}
    .swagger-ui .opblock-tag {{ color: var(--text); }}
    .swagger-ui .opblock-summary-description {{ color: var(--text-muted); }}
  </style>
</head>
<body>
  {COMMON_NAV}
  <main class="max-w-7xl mx-auto px-4 py-6">
    <div id="swagger-ui"></div>
  </main>
  {COMMON_FOOTER}
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


def render_admin_login_page(error: str = "") -> str:
    """Render the admin login page."""
    error_html = f'<div class="bg-red-500/20 border border-red-500 text-red-400 px-4 py-3 rounded-lg mb-4">{error}</div>' if error else ''

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Login - KiroGate</title>
  <meta name="robots" content="noindex, nofollow">
  <script src="{PROXY_BASE}/proxy/cdn.tailwindcss.com"></script>
  <style>
    :root {{ --bg-main: #0f172a; --bg-card: #1e293b; --text: #e2e8f0; --border: #334155; --primary: #6366f1; }}
    body {{ background: var(--bg-main); color: var(--text); font-family: system-ui, sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
  </style>
</head>
<body>
  <div class="w-full max-w-md px-6">
    <div style="background: var(--bg-card); border: 1px solid var(--border);" class="rounded-xl p-8 shadow-2xl">
      <div class="text-center mb-8">
        <span class="text-4xl">🔐</span>
        <h1 class="text-2xl font-bold mt-4">Admin Login</h1>
        <p class="text-sm mt-2" style="color: #94a3b8;">KiroGate 管理后台</p>
      </div>

      {error_html}

      <form action="/admin/login" method="POST" class="space-y-6">
        <div>
          <label class="block text-sm mb-2" style="color: #94a3b8;">管理员密码</label>
          <input type="password" name="password" required autofocus
            class="w-full px-4 py-3 rounded-lg border focus:outline-none focus:ring-2 focus:ring-indigo-500"
            style="background: var(--bg-main); border-color: var(--border); color: var(--text);"
            placeholder="请输入管理员密码">
        </div>
        <button type="submit" class="w-full py-3 rounded-lg font-semibold text-white transition-all hover:opacity-90"
          style="background: var(--primary);">
          登 录
        </button>
      </form>

      <div class="mt-6 text-center">
        <a href="/" class="text-sm hover:underline" style="color: #6366f1;">← 返回首页</a>
      </div>
    </div>
  </div>
</body>
</html>'''


def render_admin_page() -> str:
    """Render the admin dashboard page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Dashboard - KiroGate</title>
  <meta name="robots" content="noindex, nofollow">
  <script src="{PROXY_BASE}/proxy/cdn.tailwindcss.com"></script>
  <style>
    :root {{ --bg-main: #0f172a; --bg-card: #1e293b; --bg-input: #334155; --text: #e2e8f0; --text-muted: #94a3b8; --border: #334155; --primary: #6366f1; }}
    body {{ background: var(--bg-main); color: var(--text); font-family: system-ui, sans-serif; }}
    .card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: .75rem; padding: 1.5rem; }}
    .btn {{ padding: .5rem 1rem; border-radius: .5rem; font-weight: 500; transition: all .2s; cursor: pointer; }}
    .btn-primary {{ background: var(--primary); color: white; }}
    .btn-primary:hover {{ opacity: .9; }}
    .btn-danger {{ background: #ef4444; color: white; }}
    .btn-danger:hover {{ opacity: .9; }}
    .btn-success {{ background: #22c55e; color: white; }}
    .btn-success:hover {{ opacity: .9; }}
    .tab {{ padding: .75rem 1.25rem; cursor: pointer; border-bottom: 2px solid transparent; transition: all .2s; }}
    .tab:hover {{ color: var(--primary); }}
    .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
    .table-row {{ border-bottom: 1px solid var(--border); }}
    .table-row:hover {{ background: rgba(99,102,241,0.05); }}
    .switch {{ position: relative; width: 50px; height: 26px; }}
    .switch input {{ opacity: 0; width: 0; height: 0; }}
    .slider {{ position: absolute; cursor: pointer; inset: 0; background: #475569; border-radius: 26px; transition: .3s; }}
    .slider:before {{ content: ""; position: absolute; height: 20px; width: 20px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .3s; }}
    input:checked + .slider {{ background: #22c55e; }}
    input:checked + .slider:before {{ transform: translateX(24px); }}
    .status-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
    .status-ok {{ background: #22c55e; }}
    .status-error {{ background: #ef4444; }}
  </style>
</head>
<body>
  <!-- Header -->
  <header style="background: var(--bg-card); border-bottom: 1px solid var(--border);" class="sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
      <div class="flex items-center gap-4">
        <span class="text-2xl">🛡️</span>
        <h1 class="text-xl font-bold">Admin Dashboard</h1>
      </div>
      <a href="/admin/logout" class="btn btn-danger text-sm">退出登录</a>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6">
    <!-- Status Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="card text-center">
        <div class="text-2xl mb-2" id="siteIcon">🟢</div>
        <div class="flex items-center justify-center gap-2">
          <label class="switch" style="transform: scale(0.8);">
            <input type="checkbox" id="siteToggleQuick" checked onchange="toggleSite(this.checked)">
            <span class="slider"></span>
          </label>
        </div>
        <div class="text-sm mt-2" style="color: var(--text-muted);">站点开关</div>
      </div>
      <div class="card text-center">
        <div class="text-2xl mb-2">🔑</div>
        <div class="text-2xl font-bold" id="tokenStatus">-</div>
        <div class="text-sm" style="color: var(--text-muted);">Token 状态</div>
      </div>
      <div class="card text-center">
        <div class="text-2xl mb-2">📊</div>
        <div class="text-2xl font-bold" id="totalRequests">-</div>
        <div class="text-sm" style="color: var(--text-muted);">总请求数</div>
      </div>
      <div class="card text-center">
        <div class="text-2xl mb-2">👥</div>
        <div class="text-2xl font-bold" id="cachedTokens">-</div>
        <div class="text-sm" style="color: var(--text-muted);">缓存用户</div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex flex-wrap border-b mb-6" style="border-color: var(--border);">
      <div class="tab active" onclick="showTab('overview')">📈 概览</div>
      <div class="tab" onclick="showTab('users')">👥 用户</div>
      <div class="tab" onclick="showTab('donated-tokens')">🎁 Token 池</div>
      <div class="tab" onclick="showTab('ip-stats')">🌐 IP 统计</div>
      <div class="tab" onclick="showTab('blacklist')">🚫 黑名单</div>
      <div class="tab" onclick="showTab('tokens')">🔑 缓存</div>
      <div class="tab" onclick="showTab('system')">⚙️ 系统</div>
    </div>

    <!-- Tab Content: Overview -->
    <div id="tab-overview" class="tab-content">
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">📊 实时统计</h2>
        <div class="grid md:grid-cols-3 gap-4">
          <div style="background: var(--bg-input);" class="p-4 rounded-lg">
            <div class="text-sm" style="color: var(--text-muted);">成功率</div>
            <div class="text-2xl font-bold text-green-400" id="successRate">-</div>
          </div>
          <div style="background: var(--bg-input);" class="p-4 rounded-lg">
            <div class="text-sm" style="color: var(--text-muted);">平均响应时间</div>
            <div class="text-2xl font-bold text-yellow-400" id="avgLatency">-</div>
          </div>
          <div style="background: var(--bg-input);" class="p-4 rounded-lg">
            <div class="text-sm" style="color: var(--text-muted);">活跃连接</div>
            <div class="text-2xl font-bold text-blue-400" id="activeConns">-</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Content: Users -->
    <div id="tab-users" class="tab-content hidden">
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">👥 注册用户管理</h2>
          <button onclick="refreshUsers()" class="btn btn-primary text-sm">刷新</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">ID</th>
                <th class="text-left py-3 px-3">用户名</th>
                <th class="text-left py-3 px-3">信任等级</th>
                <th class="text-left py-3 px-3">Token 数</th>
                <th class="text-left py-3 px-3">API Key</th>
                <th class="text-left py-3 px-3">状态</th>
                <th class="text-left py-3 px-3">注册时间</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="usersTable">
              <tr><td colspan="8" class="py-6 text-center" style="color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab Content: Donated Tokens -->
    <div id="tab-donated-tokens" class="tab-content hidden">
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">🎁 捐献 Token 池</h2>
          <button onclick="refreshDonatedTokens()" class="btn btn-primary text-sm">刷新</button>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div style="background: var(--bg-input);" class="p-3 rounded-lg text-center">
            <div class="text-xl font-bold text-green-400" id="poolTotalTokens">-</div>
            <div class="text-xs" style="color: var(--text-muted);">总 Token</div>
          </div>
          <div style="background: var(--bg-input);" class="p-3 rounded-lg text-center">
            <div class="text-xl font-bold text-blue-400" id="poolActiveTokens">-</div>
            <div class="text-xs" style="color: var(--text-muted);">有效</div>
          </div>
          <div style="background: var(--bg-input);" class="p-3 rounded-lg text-center">
            <div class="text-xl font-bold text-purple-400" id="poolPublicTokens">-</div>
            <div class="text-xs" style="color: var(--text-muted);">公开</div>
          </div>
          <div style="background: var(--bg-input);" class="p-3 rounded-lg text-center">
            <div class="text-xl font-bold text-yellow-400" id="poolAvgSuccessRate">-</div>
            <div class="text-xs" style="color: var(--text-muted);">平均成功率</div>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">ID</th>
                <th class="text-left py-3 px-3">所有者</th>
                <th class="text-left py-3 px-3">可见性</th>
                <th class="text-left py-3 px-3">状态</th>
                <th class="text-left py-3 px-3">成功率</th>
                <th class="text-left py-3 px-3">使用次数</th>
                <th class="text-left py-3 px-3">最后使用</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="donatedTokensTable">
              <tr><td colspan="8" class="py-6 text-center" style="color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab Content: IP Stats -->
    <div id="tab-ip-stats" class="tab-content hidden">
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">🌐 IP 请求统计</h2>
          <button onclick="refreshIpStats()" class="btn btn-primary text-sm">刷新</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">IP 地址</th>
                <th class="text-left py-3 px-3">请求次数</th>
                <th class="text-left py-3 px-3">最后访问</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="ipStatsTable">
              <tr><td colspan="4" class="py-6 text-center" style="color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab Content: Blacklist -->
    <div id="tab-blacklist" class="tab-content hidden">
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">🚫 IP 黑名单</h2>
          <div class="flex gap-2">
            <input type="text" id="banIpInput" placeholder="输入 IP 地址"
              class="px-3 py-2 rounded-lg text-sm" style="background: var(--bg-input); border: 1px solid var(--border); color: var(--text);">
            <button onclick="banIp()" class="btn btn-danger text-sm">封禁</button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">IP 地址</th>
                <th class="text-left py-3 px-3">封禁时间</th>
                <th class="text-left py-3 px-3">原因</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="blacklistTable">
              <tr><td colspan="4" class="py-6 text-center" style="color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab Content: Token Management -->
    <div id="tab-tokens" class="tab-content hidden">
      <div class="card mb-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">🔑 缓存的用户 Token</h2>
          <div class="flex gap-2">
            <button onclick="refreshTokenList()" class="btn btn-primary text-sm">刷新</button>
            <button onclick="clearAllTokens()" class="btn btn-danger text-sm">清空全部</button>
          </div>
        </div>
        <p class="text-sm mb-4" style="color: var(--text-muted);">
          多租户模式下，每个用户的 REFRESH_TOKEN 会被缓存以提升性能。最多缓存 100 个用户。
        </p>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="color: var(--text-muted); border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">#</th>
                <th class="text-left py-3 px-3">Token (已脱敏)</th>
                <th class="text-left py-3 px-3">状态</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="tokenListTable">
              <tr><td colspan="4" class="py-6 text-center" style="color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2 class="text-lg font-semibold mb-4">📊 Token 使用统计</h2>
        <div class="grid md:grid-cols-2 gap-4">
          <div style="background: var(--bg-input);" class="p-4 rounded-lg">
            <div class="text-sm" style="color: var(--text-muted);">全局 Token 状态</div>
            <div class="text-xl font-bold mt-1" id="globalTokenStatus">-</div>
          </div>
          <div style="background: var(--bg-input);" class="p-4 rounded-lg">
            <div class="text-sm" style="color: var(--text-muted);">缓存用户数</div>
            <div class="text-xl font-bold mt-1" id="cachedUsersCount">-</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Content: System -->
    <div id="tab-system" class="tab-content hidden">
      <div class="grid md:grid-cols-2 gap-6">
        <div class="card">
          <h2 class="text-lg font-semibold mb-4">⚙️ 站点控制</h2>
          <div class="flex items-center justify-between p-4 rounded-lg" style="background: var(--bg-input);">
            <div>
              <div class="font-medium">站点开关</div>
              <div class="text-sm" style="color: var(--text-muted);">关闭后所有 API 请求返回 503</div>
            </div>
            <label class="switch">
              <input type="checkbox" id="siteToggle" onchange="toggleSite(this.checked)">
              <span class="slider"></span>
            </label>
          </div>
        </div>

        <div class="card">
          <h2 class="text-lg font-semibold mb-4">🔧 系统操作</h2>
          <div class="space-y-3">
            <button onclick="refreshToken()" class="w-full btn btn-primary flex items-center justify-center gap-2">
              <span>🔄</span> 刷新 Kiro Token
            </button>
            <button onclick="clearCache()" class="w-full btn flex items-center justify-center gap-2"
              style="background: var(--bg-input); border: 1px solid var(--border);">
              <span>🗑️</span> 清除模型缓存
            </button>
          </div>
        </div>
      </div>

      <div class="card mt-6">
        <h2 class="text-lg font-semibold mb-4">📋 系统信息</h2>
        <div class="grid md:grid-cols-2 gap-4 text-sm">
          <div class="flex justify-between p-3 rounded" style="background: var(--bg-input);">
            <span style="color: var(--text-muted);">版本</span>
            <span class="font-mono">{APP_VERSION}</span>
          </div>
          <div class="flex justify-between p-3 rounded" style="background: var(--bg-input);">
            <span style="color: var(--text-muted);">缓存大小</span>
            <span class="font-mono" id="cacheSize">-</span>
          </div>
        </div>
      </div>
    </div>
  </main>

  <script>
    let currentTab = 'overview';
    const allTabs = ['overview','users','donated-tokens','ip-stats','blacklist','tokens','system'];

    function showTab(tab) {{
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
      document.querySelector(`.tab:nth-child(${{allTabs.indexOf(tab)+1}})`).classList.add('active');
      document.getElementById('tab-' + tab).classList.remove('hidden');
      currentTab = tab;
      if (tab === 'users') refreshUsers();
      if (tab === 'donated-tokens') refreshDonatedTokens();
      if (tab === 'ip-stats') refreshIpStats();
      if (tab === 'blacklist') refreshBlacklist();
      if (tab === 'tokens') refreshTokenList();
    }}

    async function refreshStats() {{
      try {{
        const r = await fetch('/admin/api/stats');
        const d = await r.json();
        // Site toggle and icon
        const siteEnabled = d.site_enabled;
        document.getElementById('siteIcon').textContent = siteEnabled ? '🟢' : '🔴';
        document.getElementById('siteToggleQuick').checked = siteEnabled;
        document.getElementById('siteToggle').checked = siteEnabled;
        // Token status
        document.getElementById('tokenStatus').innerHTML = d.token_valid ? '<span class="text-green-400">有效</span>' : '<span class="text-yellow-400">未知</span>';
        document.getElementById('totalRequests').textContent = d.total_requests || 0;
        document.getElementById('cachedTokens').textContent = d.cached_tokens || 0;
        document.getElementById('successRate').textContent = d.total_requests > 0 ? ((d.success_requests / d.total_requests) * 100).toFixed(1) + '%' : '0%';
        document.getElementById('avgLatency').textContent = (d.avg_latency || 0).toFixed(0) + 'ms';
        document.getElementById('activeConns').textContent = d.active_connections || 0;
        document.getElementById('cacheSize').textContent = d.cache_size || 0;
        // Token tab stats
        document.getElementById('globalTokenStatus').innerHTML = d.token_valid ? '<span class="text-green-400">有效</span>' : '<span class="text-yellow-400">未配置/未知</span>';
        document.getElementById('cachedUsersCount').textContent = (d.cached_tokens || 0) + ' / 100';
      }} catch (e) {{ console.error(e); }}
    }}

    async function refreshIpStats() {{
      try {{
        const r = await fetch('/admin/api/ip-stats');
        const d = await r.json();
        const tb = document.getElementById('ipStatsTable');
        if (!d.length) {{
          tb.innerHTML = '<tr><td colspan="4" class="py-6 text-center" style="color: var(--text-muted);">暂无数据</td></tr>';
          return;
        }}
        tb.innerHTML = d.slice(0, 50).map(ip => `
          <tr class="table-row">
            <td class="py-3 px-3 font-mono">${{ip.ip}}</td>
            <td class="py-3 px-3">${{ip.count}}</td>
            <td class="py-3 px-3">${{ip.last_seen ? new Date(ip.last_seen * 1000).toLocaleString() : '-'}}</td>
            <td class="py-3 px-3">
              <button onclick="banIpDirect('${{ip.ip}}')" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">封禁</button>
            </td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}

    async function refreshBlacklist() {{
      try {{
        const r = await fetch('/admin/api/blacklist');
        const d = await r.json();
        const tb = document.getElementById('blacklistTable');
        if (!d.length) {{
          tb.innerHTML = '<tr><td colspan="4" class="py-6 text-center" style="color: var(--text-muted);">黑名单为空</td></tr>';
          return;
        }}
        tb.innerHTML = d.map(ip => `
          <tr class="table-row">
            <td class="py-3 px-3 font-mono">${{ip.ip}}</td>
            <td class="py-3 px-3">${{ip.banned_at ? new Date(ip.banned_at * 1000).toLocaleString() : '-'}}</td>
            <td class="py-3 px-3">${{ip.reason || '-'}}</td>
            <td class="py-3 px-3">
              <button onclick="unbanIp('${{ip.ip}}')" class="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30">解封</button>
            </td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}

    async function banIpDirect(ip) {{
      if (!confirm('确定要封禁 ' + ip + ' 吗？')) return;
      const fd = new FormData();
      fd.append('ip', ip);
      fd.append('reason', 'Manual ban from admin');
      await fetch('/admin/api/ban-ip', {{ method: 'POST', body: fd }});
      refreshIpStats();
      refreshBlacklist();
      refreshStats();
    }}

    async function banIp() {{
      const ip = document.getElementById('banIpInput').value.trim();
      if (!ip) return alert('请输入 IP 地址');
      const fd = new FormData();
      fd.append('ip', ip);
      fd.append('reason', 'Manual ban from admin');
      await fetch('/admin/api/ban-ip', {{ method: 'POST', body: fd }});
      document.getElementById('banIpInput').value = '';
      refreshBlacklist();
      refreshStats();
    }}

    async function unbanIp(ip) {{
      if (!confirm('确定要解封 ' + ip + ' 吗？')) return;
      const fd = new FormData();
      fd.append('ip', ip);
      await fetch('/admin/api/unban-ip', {{ method: 'POST', body: fd }});
      refreshBlacklist();
      refreshStats();
    }}

    async function toggleSite(enabled) {{
      const fd = new FormData();
      fd.append('enabled', enabled);
      await fetch('/admin/api/toggle-site', {{ method: 'POST', body: fd }});
      refreshStats();
    }}

    async function refreshToken() {{
      const r = await fetch('/admin/api/refresh-token', {{ method: 'POST' }});
      const d = await r.json();
      alert(d.message || (d.success ? '刷新成功' : '刷新失败'));
      refreshStats();
    }}

    async function clearCache() {{
      const r = await fetch('/admin/api/clear-cache', {{ method: 'POST' }});
      const d = await r.json();
      alert(d.message || (d.success ? '清除成功' : '清除失败'));
    }}

    async function refreshTokenList() {{
      try {{
        const r = await fetch('/admin/api/tokens');
        const d = await r.json();
        const tb = document.getElementById('tokenListTable');
        if (!d.tokens || !d.tokens.length) {{
          tb.innerHTML = '<tr><td colspan="4" class="py-6 text-center" style="color: var(--text-muted);">暂无缓存的用户 Token</td></tr>';
          return;
        }}
        tb.innerHTML = d.tokens.map((t, i) => `
          <tr class="table-row">
            <td class="py-3 px-3">${{i + 1}}</td>
            <td class="py-3 px-3 font-mono">${{t.masked_token}}</td>
            <td class="py-3 px-3">${{t.has_access_token ? '<span class="text-green-400">已认证</span>' : '<span class="text-yellow-400">待认证</span>'}}</td>
            <td class="py-3 px-3">
              <button onclick="removeToken('${{t.token_id}}')" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">移除</button>
            </td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}

    async function removeToken(tokenId) {{
      if (!confirm('确定要移除此 Token 吗？用户需要重新认证。')) return;
      const fd = new FormData();
      fd.append('token_id', tokenId);
      await fetch('/admin/api/remove-token', {{ method: 'POST', body: fd }});
      refreshTokenList();
      refreshStats();
    }}

    async function clearAllTokens() {{
      if (!confirm('确定要清空所有缓存的 Token 吗？所有用户需要重新认证。')) return;
      await fetch('/admin/api/clear-tokens', {{ method: 'POST' }});
      refreshTokenList();
      refreshStats();
      alert('已清空所有缓存的 Token');
    }}

    async function refreshUsers() {{
      try {{
        const r = await fetch('/admin/api/users');
        const d = await r.json();
        const tb = document.getElementById('usersTable');
        if (!d.users || !d.users.length) {{
          tb.innerHTML = '<tr><td colspan="8" class="py-6 text-center" style="color: var(--text-muted);">暂无用户</td></tr>';
          return;
        }}
        tb.innerHTML = d.users.map(u => `
          <tr class="table-row">
            <td class="py-3 px-3">${{u.id}}</td>
            <td class="py-3 px-3 font-medium">${{u.username}}</td>
            <td class="py-3 px-3">Lv.${{u.trust_level}}</td>
            <td class="py-3 px-3">${{u.token_count}}</td>
            <td class="py-3 px-3">${{u.api_key_count}}</td>
            <td class="py-3 px-3">${{u.is_banned ? '<span class="text-red-400">已封禁</span>' : '<span class="text-green-400">正常</span>'}}</td>
            <td class="py-3 px-3">${{u.created_at ? new Date(u.created_at).toLocaleString() : '-'}}</td>
            <td class="py-3 px-3">
              ${{u.is_banned
                ? `<button onclick="unbanUser(${{u.id}})" class="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30">解封</button>`
                : `<button onclick="banUser(${{u.id}})" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">封禁</button>`
              }}
            </td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}

    async function banUser(userId) {{
      if (!confirm('确定要封禁此用户吗？')) return;
      const fd = new FormData();
      fd.append('user_id', userId);
      await fetch('/admin/api/users/ban', {{ method: 'POST', body: fd }});
      refreshUsers();
    }}

    async function unbanUser(userId) {{
      if (!confirm('确定要解封此用户吗？')) return;
      const fd = new FormData();
      fd.append('user_id', userId);
      await fetch('/admin/api/users/unban', {{ method: 'POST', body: fd }});
      refreshUsers();
    }}

    async function refreshDonatedTokens() {{
      try {{
        const r = await fetch('/admin/api/donated-tokens');
        const d = await r.json();
        document.getElementById('poolTotalTokens').textContent = d.total || 0;
        document.getElementById('poolActiveTokens').textContent = d.active || 0;
        document.getElementById('poolPublicTokens').textContent = d.public || 0;
        document.getElementById('poolAvgSuccessRate').textContent = d.avg_success_rate ? d.avg_success_rate.toFixed(1) + '%' : '-';
        const tb = document.getElementById('donatedTokensTable');
        if (!d.tokens || !d.tokens.length) {{
          tb.innerHTML = '<tr><td colspan="8" class="py-6 text-center" style="color: var(--text-muted);">暂无捐献 Token</td></tr>';
          return;
        }}
        tb.innerHTML = d.tokens.map(t => `
          <tr class="table-row">
            <td class="py-3 px-3">#${{t.id}}</td>
            <td class="py-3 px-3">${{t.username || 'Unknown'}}</td>
            <td class="py-3 px-3">${{t.visibility === 'public' ? '<span class="text-green-400">公开</span>' : '<span class="text-blue-400">私有</span>'}}</td>
            <td class="py-3 px-3">${{t.status === 'active' ? '<span class="text-green-400">有效</span>' : '<span class="text-red-400">' + t.status + '</span>'}}</td>
            <td class="py-3 px-3">${{(t.success_rate * 100).toFixed(1)}}%</td>
            <td class="py-3 px-3">${{t.success_count + t.fail_count}}</td>
            <td class="py-3 px-3">${{t.last_used ? new Date(t.last_used).toLocaleString() : '-'}}</td>
            <td class="py-3 px-3">
              <button onclick="toggleTokenVisibility(${{t.id}}, '${{t.visibility === 'public' ? 'private' : 'public'}}')" class="text-xs px-2 py-1 rounded bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 mr-1">切换</button>
              <button onclick="deleteDonatedToken(${{t.id}})" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">删除</button>
            </td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}

    async function toggleTokenVisibility(tokenId, newVisibility) {{
      const fd = new FormData();
      fd.append('token_id', tokenId);
      fd.append('visibility', newVisibility);
      await fetch('/admin/api/donated-tokens/visibility', {{ method: 'POST', body: fd }});
      refreshDonatedTokens();
    }}

    async function deleteDonatedToken(tokenId) {{
      if (!confirm('确定要删除此 Token 吗？')) return;
      const fd = new FormData();
      fd.append('token_id', tokenId);
      await fetch('/admin/api/donated-tokens/delete', {{ method: 'POST', body: fd }});
      refreshDonatedTokens();
    }}

    refreshStats();
    setInterval(refreshStats, 10000);
  </script>
</body>
</html>'''


def render_user_page(user) -> str:
    """Render the user dashboard page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}
  <main class="max-w-6xl mx-auto px-4 py-8">
    <div class="card mb-6">
      <div class="flex items-center gap-4">
        <div class="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center text-2xl">
          {user.username[0].upper() if user.username else '👤'}
        </div>
        <div>
          <h1 class="text-2xl font-bold">{user.username}</h1>
          <p style="color: var(--text-muted);">信任等级: Lv.{user.trust_level}</p>
        </div>
        <div class="ml-auto">
          <a href="/oauth2/logout" class="btn-primary">退出登录</a>
        </div>
      </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="card text-center">
        <div class="text-3xl font-bold text-indigo-400" id="tokenCount">-</div>
        <div class="text-sm" style="color: var(--text-muted);">我的 Token</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-green-400" id="publicTokenCount">-</div>
        <div class="text-sm" style="color: var(--text-muted);">公开 Token</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-amber-400" id="apiKeyCount">-</div>
        <div class="text-sm" style="color: var(--text-muted);">API Keys</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-purple-400" id="requestCount">-</div>
        <div class="text-sm" style="color: var(--text-muted);">总请求</div>
      </div>
    </div>
    <div class="flex gap-2 mb-4 border-b" style="border-color: var(--border);">
      <button class="tab px-4 py-2 font-medium" onclick="showTab('tokens')" id="tab-tokens">🔑 Token 管理</button>
      <button class="tab px-4 py-2 font-medium" onclick="showTab('keys')" id="tab-keys">🗝️ API Keys</button>
    </div>
    <div id="panel-tokens" class="tab-panel">
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold">我的 Token</h2>
          <button onclick="showDonateModal()" class="btn-primary">+ 捐献 Token</button>
        </div>
        <div class="table-responsive">
          <table class="w-full">
            <thead>
              <tr style="border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">ID</th>
                <th class="text-left py-3 px-3">可见性</th>
                <th class="text-left py-3 px-3">状态</th>
                <th class="text-left py-3 px-3">成功率</th>
                <th class="text-left py-3 px-3">最后使用</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="tokenTable"></tbody>
          </table>
        </div>
      </div>
    </div>
    <div id="panel-keys" class="tab-panel" style="display: none;">
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold">我的 API Keys</h2>
          <button onclick="generateKey()" class="btn-primary">+ 生成新 Key</button>
        </div>
        <div class="table-responsive">
          <table class="w-full">
            <thead>
              <tr style="border-bottom: 1px solid var(--border);">
                <th class="text-left py-3 px-3">Key</th>
                <th class="text-left py-3 px-3">名称</th>
                <th class="text-left py-3 px-3">请求数</th>
                <th class="text-left py-3 px-3">最后使用</th>
                <th class="text-left py-3 px-3">操作</th>
              </tr>
            </thead>
            <tbody id="keyTable"></tbody>
          </table>
        </div>
        <p class="mt-4 text-sm" style="color: var(--text-muted);">
          💡 API Key 仅在创建时显示一次，请妥善保存。使用方式: <code class="bg-black/20 px-1 rounded">Authorization: Bearer sk-xxx</code>
        </p>
      </div>
    </div>
  </main>
  <div id="donateModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" style="display: none;">
    <div class="card w-full max-w-md mx-4">
      <h3 class="text-lg font-bold mb-4">捐献 Refresh Token</h3>
      <textarea id="donateToken" class="w-full h-32 p-3 rounded-lg" style="background: var(--bg-input); border: 1px solid var(--border);" placeholder="粘贴你的 Refresh Token..."></textarea>
      <div class="flex items-center gap-4 mt-4">
        <label class="flex items-center gap-2"><input type="radio" name="visibility" value="private" checked> 私有</label>
        <label class="flex items-center gap-2"><input type="radio" name="visibility" value="public"> 公开</label>
      </div>
      <p class="text-sm mt-2" style="color: var(--text-muted);">公开的 Token 会加入公共池供所有用户使用</p>
      <div class="flex justify-end gap-2 mt-4">
        <button onclick="hideDonateModal()" class="px-4 py-2 rounded-lg" style="background: var(--bg-input);">取消</button>
        <button onclick="donateToken()" class="btn-primary">提交</button>
      </div>
    </div>
  </div>
  {COMMON_FOOTER}
  <style>
    .tab {{ color: var(--text-muted); border-bottom: 2px solid transparent; }}
    .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
    .table-row:hover {{ background: var(--bg-input); }}
  </style>
  <script>
    let currentTab = 'tokens';
    function showTab(tab) {{
      currentTab = tab;
      document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.getElementById('panel-' + tab).style.display = 'block';
      document.getElementById('tab-' + tab).classList.add('active');
    }}
    async function loadProfile() {{
      try {{
        const r = await fetch('/user/api/profile');
        const d = await r.json();
        document.getElementById('tokenCount').textContent = d.token_count || 0;
        document.getElementById('publicTokenCount').textContent = d.public_token_count || 0;
        document.getElementById('apiKeyCount').textContent = d.api_key_count || 0;
        document.getElementById('requestCount').textContent = '-';
      }} catch (e) {{ console.error(e); }}
    }}
    async function loadTokens() {{
      try {{
        const r = await fetch('/user/api/tokens');
        const d = await r.json();
        const tb = document.getElementById('tokenTable');
        if (!d.tokens || !d.tokens.length) {{
          tb.innerHTML = '<tr><td colspan="6" class="py-6 text-center" style="color: var(--text-muted);">暂无 Token，点击上方按钮捐献</td></tr>';
          return;
        }}
        tb.innerHTML = d.tokens.map(t => `
          <tr class="table-row">
            <td class="py-3 px-3">#${{t.id}}</td>
            <td class="py-3 px-3"><span class="${{t.visibility === 'public' ? 'text-green-400' : 'text-blue-400'}}">${{t.visibility === 'public' ? '公开' : '私有'}}</span></td>
            <td class="py-3 px-3"><span class="${{t.status === 'active' ? 'text-green-400' : 'text-red-400'}}">${{t.status === 'active' ? '有效' : t.status}}</span></td>
            <td class="py-3 px-3">${{t.success_rate}}%</td>
            <td class="py-3 px-3">${{t.last_used ? new Date(t.last_used).toLocaleString() : '-'}}</td>
            <td class="py-3 px-3">
              <button onclick="toggleVisibility(${{t.id}}, '${{t.visibility === 'public' ? 'private' : 'public'}}')" class="text-xs px-2 py-1 rounded bg-indigo-500/20 text-indigo-400 mr-1">切换</button>
              <button onclick="deleteToken(${{t.id}})" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400">删除</button>
            </td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}
    async function loadKeys() {{
      try {{
        const r = await fetch('/user/api/keys');
        const d = await r.json();
        const tb = document.getElementById('keyTable');
        if (!d.keys || !d.keys.length) {{
          tb.innerHTML = '<tr><td colspan="5" class="py-6 text-center" style="color: var(--text-muted);">暂无 API Key，点击上方按钮生成</td></tr>';
          return;
        }}
        tb.innerHTML = d.keys.map(k => `
          <tr class="table-row">
            <td class="py-3 px-3 font-mono">${{k.key_prefix}}</td>
            <td class="py-3 px-3">${{k.name || '-'}}</td>
            <td class="py-3 px-3">${{k.request_count}}</td>
            <td class="py-3 px-3">${{k.last_used ? new Date(k.last_used).toLocaleString() : '-'}}</td>
            <td class="py-3 px-3"><button onclick="deleteKey(${{k.id}})" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400">删除</button></td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}
    function showDonateModal() {{ document.getElementById('donateModal').style.display = 'flex'; }}
    function hideDonateModal() {{ document.getElementById('donateModal').style.display = 'none'; }}
    async function donateToken() {{
      const token = document.getElementById('donateToken').value.trim();
      if (!token) return alert('请输入 Token');
      const visibility = document.querySelector('input[name="visibility"]:checked').value;
      const fd = new FormData();
      fd.append('refresh_token', token);
      fd.append('visibility', visibility);
      try {{
        const r = await fetch('/user/api/tokens', {{ method: 'POST', body: fd }});
        const d = await r.json();
        if (d.success) {{
          alert('Token 捐献成功！');
          hideDonateModal();
          document.getElementById('donateToken').value = '';
          loadTokens();
          loadProfile();
        }} else {{ alert(d.message || '捐献失败'); }}
      }} catch (e) {{ alert('请求失败'); }}
    }}
    async function toggleVisibility(tokenId, newVisibility) {{
      const fd = new FormData();
      fd.append('visibility', newVisibility);
      await fetch('/user/api/tokens/' + tokenId, {{ method: 'PUT', body: fd }});
      loadTokens();
      loadProfile();
    }}
    async function deleteToken(tokenId) {{
      if (!confirm('确定要删除此 Token 吗？')) return;
      await fetch('/user/api/tokens/' + tokenId, {{ method: 'DELETE' }});
      loadTokens();
      loadProfile();
    }}
    async function generateKey() {{
      const name = prompt('Key 名称（可选）');
      const fd = new FormData();
      fd.append('name', name || '');
      try {{
        const r = await fetch('/user/api/keys', {{ method: 'POST', body: fd }});
        const d = await r.json();
        if (d.success) {{
          alert('API Key 已生成！\\n\\n请立即复制保存，此 Key 仅显示一次：\\n\\n' + d.key);
          loadKeys();
          loadProfile();
        }} else {{ alert(d.message || '生成失败'); }}
      }} catch (e) {{ alert('请求失败'); }}
    }}
    async function deleteKey(keyId) {{
      if (!confirm('确定要删除此 API Key 吗？')) return;
      await fetch('/user/api/keys/' + keyId, {{ method: 'DELETE' }});
      loadKeys();
      loadProfile();
    }}
    showTab('tokens');
    loadProfile();
    loadTokens();
    loadKeys();
  </script>
</body>
</html>'''


def render_tokens_page(user=None) -> str:
    """Render the public token pool page."""
    login_section = '<a href="/user" class="btn-primary">用户中心</a>' if user else '<a href="/login" class="btn-primary">登录捐献</a>'
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}
  <main class="max-w-4xl mx-auto px-4 py-8">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-2">🌐 公开 Token 池</h1>
      <p style="color: var(--text-muted);">社区捐献的 Refresh Token，供所有用户共享使用</p>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-8">
      <div class="card text-center">
        <div class="text-4xl font-bold text-green-400" id="poolCount">-</div>
        <div style="color: var(--text-muted);">可用 Token</div>
      </div>
      <div class="card text-center">
        <div class="text-4xl font-bold text-indigo-400" id="avgRate">-</div>
        <div style="color: var(--text-muted);">平均成功率</div>
      </div>
    </div>
    <div class="card mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold">Token 列表</h2>
        {login_section}
      </div>
      <div class="table-responsive">
        <table class="w-full">
          <thead>
            <tr style="border-bottom: 1px solid var(--border);">
              <th class="text-left py-3 px-3">#</th>
              <th class="text-left py-3 px-3">成功率</th>
              <th class="text-left py-3 px-3">最后使用</th>
            </tr>
          </thead>
          <tbody id="poolTable"></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <h3 class="font-bold mb-3">💡 如何使用</h3>
      <ol class="list-decimal list-inside space-y-2" style="color: var(--text-muted);">
        <li>通过 LinuxDo 或 GitHub 登录本站</li>
        <li>在用户中心捐献你的 Refresh Token</li>
        <li>选择"公开"以加入公共池</li>
        <li>生成 API Key (sk-xxx 格式)</li>
        <li>使用 API Key 调用本站接口</li>
      </ol>
    </div>
  </main>
  {COMMON_FOOTER}
  <script>
    async function loadPool() {{
      try {{
        const r = await fetch('/api/public-tokens');
        const d = await r.json();
        document.getElementById('poolCount').textContent = d.count || 0;
        const tokens = d.tokens || [];
        if (tokens.length > 0) {{
          const avgRate = tokens.reduce((sum, t) => sum + t.success_rate, 0) / tokens.length;
          document.getElementById('avgRate').textContent = avgRate.toFixed(1) + '%';
        }} else {{ document.getElementById('avgRate').textContent = '-'; }}
        const tb = document.getElementById('poolTable');
        if (!tokens.length) {{
          tb.innerHTML = '<tr><td colspan="3" class="py-6 text-center" style="color: var(--text-muted);">暂无公开 Token</td></tr>';
          return;
        }}
        tb.innerHTML = tokens.map((t, i) => `
          <tr style="border-bottom: 1px solid var(--border);">
            <td class="py-3 px-3">${{i + 1}}</td>
            <td class="py-3 px-3"><span class="${{t.success_rate >= 80 ? 'text-green-400' : t.success_rate >= 50 ? 'text-yellow-400' : 'text-red-400'}}">${{t.success_rate}}%</span></td>
            <td class="py-3 px-3" style="color: var(--text-muted);">${{t.last_used ? new Date(t.last_used).toLocaleString() : '-'}}</td>
          </tr>
        `).join('');
      }} catch (e) {{ console.error(e); }}
    }}
    loadPool();
    setInterval(loadPool, 30000);
  </script>
</body>
</html>'''


def render_login_page() -> str:
    """Render the login selection page with multiple OAuth2 providers."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}
  <main class="max-w-md mx-auto px-4 py-16">
    <div class="card text-center">
      <div class="mb-6">
        <h1 class="text-2xl font-bold mb-2">🔐 用户登录</h1>
        <p style="color: var(--text-muted);">选择一种登录方式开始使用</p>
      </div>
      <div class="space-y-4">
        <a href="/oauth2/login" class="btn-primary w-full flex items-center justify-center gap-3" style="display: flex; padding: 12px 24px;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
          LinuxDo 登录
        </a>
        <a href="/oauth2/github/login" class="w-full flex items-center justify-center gap-3" style="display: flex; padding: 12px 24px; background: #24292e; color: white; border-radius: 8px; font-weight: 500; transition: all 0.2s;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
          GitHub 登录
        </a>
      </div>
      <div class="mt-6 pt-6" style="border-top: 1px solid var(--border);">
        <p style="color: var(--text-muted); font-size: 0.875rem;">
          登录后可捐献 Token 并生成 API Key
        </p>
      </div>
    </div>
  </main>
  {COMMON_FOOTER}
</body>
</html>'''


def render_404_page() -> str:
    """Render the 404 Not Found page."""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>{COMMON_HEAD}</head>
<body>
  {COMMON_NAV}
  <main class="max-w-2xl mx-auto px-4 py-16 text-center">
    <div class="mb-8">
      <div class="text-9xl font-bold" style="background: linear-gradient(135deg, var(--primary) 0%, #ec4899 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">404</div>
    </div>
    <h1 class="text-3xl font-bold mb-4">页面未找到</h1>
    <p class="text-lg mb-8" style="color: var(--text-muted);">
      抱歉，您访问的页面不存在或已被移动。
    </p>
    <div class="flex flex-col sm:flex-row gap-4 justify-center">
      <a href="/" class="btn-primary inline-flex items-center gap-2">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
        </svg>
        返回首页
      </a>
      <a href="/docs" class="inline-flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all" style="background: var(--bg-card); border: 1px solid var(--border);">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
        </svg>
        查看文档
      </a>
    </div>
    <div class="mt-12 p-6 rounded-lg" style="background: var(--bg-card); border: 1px solid var(--border);">
      <h3 class="font-bold mb-3">💡 可能有帮助的链接</h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <a href="/playground" class="p-3 rounded-lg hover:bg-opacity-80 transition-all" style="background: var(--bg);">🎮 Playground</a>
        <a href="/status" class="p-3 rounded-lg hover:bg-opacity-80 transition-all" style="background: var(--bg);">📊 系统状态</a>
        <a href="/swagger" class="p-3 rounded-lg hover:bg-opacity-80 transition-all" style="background: var(--bg);">📚 API 文档</a>
        <a href="/tokens" class="p-3 rounded-lg hover:bg-opacity-80 transition-all" style="background: var(--bg);">🌐 Token 池</a>
      </div>
    </div>
  </main>
  {COMMON_FOOTER}
</body>
</html>'''
