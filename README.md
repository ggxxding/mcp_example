# 基于MCP的Agent构建教程

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
# 创建项目目录
uv init mcp_example
cd mcp_example

# 创建虚拟环境并激活
uv venv
source .venv/bin/activate

# 安装依赖
uv add "mcp[cli]" httpx
uv add fastmcp
uv add openai
```

3. 安装node.js（用于运行MCP Inspector调试工具，非必须）
   访问https://nodejs.org/zh-cn，根据页面提示下载

```
npx -y @modelcontextprotocol/inspector
```

## 项目结构

```
.
├── weather.py       # 天气预报MCP服务脚本，包含经纬度天气查询和州代码天气预警查询
├── agent_weather.py # 天气查询Agent脚本，使用方法见下一节
├── agent_weather_http.py # Http版天气查询Agent脚本，自动查询tool并构建schema，使用方法见下一节
├── README.md        # 说明
└── uv.lock          # uv.lock文件，用于锁定依赖版本
```

## 使用

自行配置好本地LLM。

1. 启动MCP服务
   在项目根目录执行：`uv run weather.py [stdio|http]`
1. 基础脚本
   不要关闭上一步的服务，开启一个新终端，确保transport与上一步一致，
   在项目根目录执行：`uv run agent_weather.py [stdio|http] "你的prompt"`，
   例如：`uv run agent_weather.py stdio "查询纽约的天气"`
1. http脚本
   在项目根目录执行：`uv run agent_weather_http.py "你的prompt"`
