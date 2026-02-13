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
```
