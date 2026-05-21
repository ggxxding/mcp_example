# 基于MCP的Agent构建基础代码

## 环境准备

1. 在命令行中通过以下命令安装uv：

- uv是一个基于rust开发的高效Python包管理器，性能比conda要好很多，MCP官方教程也推荐用uv，如果你更习惯conda也可以略过这一步，把后面uv安装命令都用conda代替就行

```zsh
# MacOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. 创建和设置项目：

```
# 克隆本仓库，并进入目录
git@github.com:ggxxding/mcp_example.git
cd mcp_example
```

3. 安装node.js（用于运行MCP Inspector调试工具，非必须）
   访问https://nodejs.org/zh-cn，根据页面提示下载，通过以下命令安装并启动调试工具：

```
npx -y @modelcontextprotocol/inspector
```

## 项目结构

```
.
├── weather.py       # 天气预报MCP服务脚本，包含经纬度天气查询和州代码天气预警查询
├── agent_weather_fastmcp.py # 通过FastMCP构建的天气查询Agent脚本，使用方法见下一节
├── agent_weather_http.py # Http版天气查询Agent脚本，自动查询tool并构建schema，使用方法见下一节
├── agent_weather_http_res.py # 在agent_weather_http.py基础上，添加了资源读取功能，使用方法见下一节
├── README.md        # 说明
└── uv.lock          # uv.lock文件，用于锁定依赖版本
```

## 使用

请先通过ollama或其他工具自行配置好本地LLM。

1. 启动MCP服务（仅用于http）

   在项目根目录执行：`uv run weather.py http`

1. 基础http脚本

   在项目根目录执行：`uv run agent_weather_http.py "你的prompt"`，
   例如：`uv run agent_weather_http.py "查询纽约的天气预警"`

1. http + resource 读取脚本

   在项目根目录执行：`uv run agent_weather_http_res.py "你的prompt"`，
   例如：`uv run agent_weather_http_res.py "帮我查询任意支持的州的天气预警"`

1. FastMCP脚本（第三方框架，代码更简洁）

   在项目根目录执行：`uv run agent_weather_fastmcp.py [stdio|http] "你的prompt"`，
   例如：`uv run agent_weather_fastmcp.py stdio "查询纽约的天气"`
