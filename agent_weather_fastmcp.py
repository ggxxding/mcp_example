# 使用本地 Ollama 模型，通过 MCP weather 服务查询天气和预警的示例 Agent
# 在项目根目录执行：uv run agent_weather.py [stdio|http] "你的prompt"
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from openai import OpenAI

API_KEY = "ollama"
BASE_URL = "http://192.168.200.23:11434/v1"
MODEL_NAME = "qwen3.5:35b"

WEATHER_SERVER_PATH = Path(__file__).parent / "weather.py"
WEATHER_HTTP_ENDPOINT = "http://127.0.0.1:8000/mcp"


async def call_weather_tool_stdio(name: str, args: dict) -> str:
    # 通过 STDIO 启动本地 weather MCP 服务器，并调用指定工具
    # WEATHER_SERVER_PATH = /Users/ggxxding/Documents/GitHub/mcp_example/weather.py
    client = Client(str(WEATHER_SERVER_PATH)) 
    async with client:
        result = await client.call_tool(name, args)
    return result.content[0].text if result.content else ""


async def call_weather_tool_http(name: str, args: dict) -> str:
    # 通过 Streamable HTTP 连接远程 weather MCP 服务器，并调用指定工具
    transport = StreamableHttpTransport(url=WEATHER_HTTP_ENDPOINT)
    client = Client(transport)
    async with client:
        result = await client.call_tool(name, args)
    return result.content[0].text if result.content else ""


def convert_mcp_tools_to_openai_schema(tools: list[Any]) -> list[dict]:
    # 将 MCP 工具转换为 OpenAI function calling schema 格式
    tools_schema = []
    for tool in tools:
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        tools_schema.append(schema)
    return tools_schema


async def get_weather_tools_schema_stdio() -> list[dict]:
    # 通过 STDIO 启动本地 weather MCP 服务器，并获取可用工具 schema
    client = Client(str(WEATHER_SERVER_PATH))
    async with client:
        tools = await client.list_tools()
    return convert_mcp_tools_to_openai_schema(tools)


async def get_weather_tools_schema_http() -> list[dict]:
    # 通过 Streamable HTTP 连接远程 weather MCP 服务器，并获取可用工具 schema
    transport = StreamableHttpTransport(url=WEATHER_HTTP_ENDPOINT)
    client = Client(transport)
    async with client:
        tools = await client.list_tools()
    return convert_mcp_tools_to_openai_schema(tools)


async def get_weather_tools_schema(transport: str) -> list[dict]:
    if transport == "stdio":
        return await get_weather_tools_schema_stdio()
    if transport == "http":
        return await get_weather_tools_schema_http()
    raise ValueError(f"未知的transport类型: {transport}")


def build_tools_schema() -> list[dict]:
    # 为 OpenAI 函数调用手动构造工具 schema，与 weather MCP 中的工具保持一致
    return [
        {
            "type": "function",
            "function": {
                "name": "get_forecast",
                "description": "根据经纬度获取未来一段时间的天气预报信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "地点的纬度，例如 37.7749",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "地点的经度，例如 -122.4194",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_alerts",
                "description": "根据美国州代码获取当前的天气预警信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "两位的美国州代码，例如 CA、NY",
                        }
                    },
                    "required": ["state"],
                },
            },
        },
    ]


def run_agent(transport: str, user_query: str) -> None:
    # 驱动 LLM 与用户对话，自动决定何时调用 MCP 工具并整合结果
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    tools = asyncio.run(get_weather_tools_schema(transport))
    # tools = build_tools_schema()

    tools_json = json.dumps(tools, ensure_ascii=False, indent = 4)
    print(f"\n[可供调用的工具]:\n{tools_json}")
    
    # 初始化全量对话记录（包含思考过程）
    full_history = []
    
    messages: list[dict] = [
        {
            "role": "system",
            "content": "你是一个可以通过weather MCP工具查询天气预报和天气警报的智能助手。",
        },
        {"role": "user", "content": user_query},
    ]
    
    # 记录初始对话
    for msg in messages:
        full_history.append({"role": msg["role"], "content": msg["content"]})

    step = 1

    while True:
        print(f"\n========================== 第 {step} 轮模型调用 ==========================")
        print("\n[当前对话消息]：\n")

        messages_json = json.dumps(messages, ensure_ascii=False, indent = 4)
        print(messages_json)


        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        message = response.choices[0].message
        reasoning = getattr(response.choices[0].message, "reasoning", None)
        
        # 记录模型思考过程
        if reasoning:
            print("\n[模型思考过程]:\n", reasoning)
            full_history.append({"role": "thought", "content": reasoning})

        print("\n[模型本轮回复内容]:\n", message.content)
        
        # 记录模型回复
        full_history.append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})

        if not message.tool_calls:
            print("\n**********************[最终回答]**********************")
            print(message.content or "")
            break

        print("[assistant 工具调用计划]:\n")
        tool_messages: list[dict] = []

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            print(f"- 调用工具: {name}, 原始参数字符串: {raw_args}")
            args = json.loads(raw_args)

            if transport == "stdio":
                result_text = asyncio.run(call_weather_tool_stdio(name, args))
            elif transport == "http":
                result_text = asyncio.run(call_weather_tool_http(name, args))
            else:
                raise ValueError(f"未知的transport类型: {transport}")

            tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result_text,
                }
            tool_messages.append(tool_msg)
            # 记录工具执行结果
            full_history.append(tool_msg)

        print("\n[实际工具调用结果已写入 tool 消息，继续下一轮对话]")

        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            }
        )
        messages.extend(tool_messages)

        step += 1

    # 对话结束，导出为 Markdown
    export_to_markdown(full_history, tools_json)


def export_to_markdown(history: list[dict], tools_json: str) -> None:
    # 导出对话记录到 history 目录下的 markdown 文件
    history_dir = Path(__file__).parent / "history"
    history_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = history_dir / f"chat_history_{timestamp}.md"
    
    md_content = "# Weather Agent Chat History\n\n"
    md_content += f"**Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for entry in history:
        role = entry.get("role")
        content = entry.get("content") or ""
        
        if role == "system":
            md_content += "## System\n"
            md_content += f"{content}\n\n"
            md_content += "## Available Tools\n"
            md_content += "```json\n"
            md_content += f"{tools_json}\n"
            md_content += "```\n\n"
        elif role == "user":
            md_content += "## User\n"
            md_content += f"{content}\n\n"
        elif role == "thought":
            md_content += "## Reasoning\n"
            md_content += f"> {content.replace('\n', '\n> ')}\n\n"
        elif role == "assistant":
            md_content += "## Assistant\n"
            if content:
                md_content += f"{content}\n\n"
            
            tool_calls = entry.get("tool_calls")
            if tool_calls:
                md_content += "**Tool Calls:**\n"
                for tc in tool_calls:
                    # tool_calls can be ChoiceDeltaToolCall or similar from openai
                    name = getattr(tc.function, "name", "unknown")
                    args = getattr(tc.function, "arguments", "{}")
                    md_content += f"- `{name}({args})`\n"
                md_content += "\n"
        elif role == "tool":
            name = entry.get("name", "unknown")
            md_content += f"### Tool Result: {name}\n"
            md_content += "```json\n"
            md_content += f"{content}\n"
            md_content += "```\n\n"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print(f"\n[对话记录已保存到]: {filename}")


def main() -> None:
    # 从命令行读取 transport 和用户问题，运行示例 Agent
    if len(sys.argv) < 3:
        print("用法: uv run agent_weather.py [stdio|http] \"你的问题\"")
        sys.exit(1)

    transport = sys.argv[1]
    user_query = sys.argv[2]
    run_agent(transport, user_query)


if __name__ == "__main__":
    main()
