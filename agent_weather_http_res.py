# agent_weather_http.py
# 使用本地 Ollama 模型，通过 Streamable HTTP 连接 MCP weather 服务查询天气和预警的示例 Agent

from queue import Full
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import OpenAI

# OpenAI/Ollama 配置
API_KEY = "ollama"
BASE_URL = "http://192.168.200.23:11434/v1"
MODEL_NAME = "qwen3.5:35b"

# Weather MCP 服务 HTTP 端点
# 请确保 weather.py 已经以 HTTP 模式运行，例如：python weather.py
WEATHER_HTTP_ENDPOINT = "http://127.0.0.1:8000/mcp"


class MCPWeatherAgent:
    """
    一个 MCP Agent 类，负责连接 MCP 服务器、动态发现工具、
    并驱动 LLM 使用这些工具进行对话。
    """

    def __init__(self):
        # 初始化 OpenAI 客户端，用于与 LLM 交互
        self.openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        # 用于管理 MCP 会话的 AsyncExitStack，确保资源正确释放
        self.exit_stack = AsyncExitStack()
        # MCP 会话对象
        self.mcp_session: Optional[ClientSession] = None
        # 存储从 MCP 服务器动态发现并转换为 OpenAI 格式的工具 schema
        self.mcp_tools_openai_schema: list[dict] = []

        self.resources = []

    async def connect_to_mcp_server(self, server_url: str):
        """
        连接到 Streamable HTTP MCP 服务器并动态发现工具。

        Args:
            server_url: MCP 服务器的 URL (例如: http://localhost:8000/mcp)
        """
        print(f"尝试连接到 MCP 服务器: {server_url}")
        # 使用 AsyncExitStack 管理 streamablehttp_client 的生命周期
        streamablehttp_transport = await self.exit_stack.enter_async_context(streamablehttp_client(server_url))
        read_stream, write_stream = streamablehttp_transport[0], streamablehttp_transport[1]
        # 使用 AsyncExitStack 管理 ClientSession 的生命周期
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))

        # 初始化 MCP 会话
        await self.mcp_session.initialize()
        print("MCP 会话已初始化。")

        # 从 MCP 服务器列出所有可用工具
        response = await self.mcp_session.list_tools()
        print(f"\n已连接到 MCP 服务器，发现工具: {[tool.name for tool in response.tools]}")

        # 将 MCP 工具转换为 OpenAI function calling schema 格式
        for tool in response.tools:
            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            self.mcp_tools_openai_schema.append(schema)
        print("工具 schema 已成功转换为 OpenAI 格式。")

        # 读取resources
        response = await self.mcp_session.list_resources()
        for resource in response.resources:
            self.resources.append(
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                }
            )
        print("已读取到 resources")

    async def call_mcp_tool(self, name: str, args: dict) -> str:
        """
        调用 MCP 服务器上的指定工具。

        Args:
            name: 工具名称。
            args: 工具参数字典。

        Returns:
            工具执行结果的文本表示。
        """
        if not self.mcp_session:
            raise RuntimeError("MCP 服务器未连接，无法调用工具。")
        # 调用 MCP 工具
        result = await self.mcp_session.call_tool(name=name, arguments=args)
        return self._extract_text_result(result)

    def _extract_text_result(self, result) -> str:
        """
        从 MCP 工具结果中提取文本内容。

        Args:
            result: MCP 工具调用的结果对象。

        Returns:
            提取到的文本内容，如果没有则返回空字符串。
        """
        for item in result.content:
            if getattr(item, "type", None) == "text":
                return item.text
        return ""

    async def run_agent(self, user_query: str) -> None:
        """
        驱动 LLM 与用户对话，自动决定何时调用 MCP 工具并整合结果。

        Args:
            user_query: 用户的初始查询。
        """
        # 初始化全量对话记录（包含思考过程）
        full_history = []
        messages: list[dict] = [
            {
                "role": "system",
                "content": f"""你是一个可以通过weather MCP工具查询天气预报和天气警报的智能助手。
                你可以使用以下资源来帮助回答用户的问题：
                {self.resources}
                
                如果你需要资源，回复:READ_RESOURCE: <uri>
                
                """,
            },
            {"role": "user", "content": user_query},
        ]
        tools_json = json.dumps(self.mcp_tools_openai_schema, ensure_ascii=False, indent=4)
        print(f"\n[工具schema]:\n{tools_json}")
        # 记录初始对话
        for msg in messages:
            full_history.append({"role": msg["role"], "content": msg["content"]})

        step = 1

        while True:
            print(f"\n========================== 第 {step} 轮模型调用 ==========================")
            print("\n[当前对话消息]：\n")

            messages_json = json.dumps(messages, ensure_ascii=False, indent = 4)
            print(messages_json)

            response = self.openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=self.mcp_tools_openai_schema,
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

            if message.content and message.content.startswith("READ_RESOURCE"):
                messages.append({"role": "assistant", "content": message.content})
                resource_uri = message.content.split(":", 1)[1].strip()
                resource = await self.mcp_session.read_resource(resource_uri)
                if resource:
                    full_history.append({"role": "system", "content": f"资源内容: {resource.contents[0].text}"})
                    messages.append({"role": "system", "content": f"资源内容: {resource.contents[0].text}"})
                else:
                    print(f"\n[警告] 未找到 URI 为 {resource_uri} 的资源")
                    full_history.append({"role": "system", "content": f"未找到 URI 为 {resource_uri} 的资源"})
                    messages.append({"role": "system", "content": f"未找到 URI 为 {resource_uri} 的资源"})
                step += 1
                continue

            if message.tool_calls:
                print("[assistant 工具调用计划]:\n")
                tool_messages: list[dict] = []

                for tool_call in message.tool_calls:
                    name = tool_call.function.name
                    raw_args = tool_call.function.arguments or "{}"
                    print(f"- 调用工具: {name}, 原始参数字符串: {raw_args}")
                    args = json.loads(raw_args)
                    result_text = await self.call_mcp_tool(name, args)

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
                continue

            print("\n**********************[最终回答]**********************")
            print(message.content or "")
            break

        # 对话结束，导出为 Markdown
        export_to_markdown(full_history, tools_json)


async def main() -> None:
    """主函数，解析命令行参数并运行 Agent。"""
    if len(sys.argv) < 2:
        print("用法: python agent_weather_http.py \"你的问题\"")
        sys.exit(1)

    user_query = sys.argv[1]

    agent = MCPWeatherAgent()
    # 使用 AsyncExitStack 管理 Agent 内部的异步资源
    async with agent.exit_stack:
        await agent.connect_to_mcp_server(WEATHER_HTTP_ENDPOINT)
        await agent.run_agent(user_query)


def export_to_markdown(history: list[dict], tools_json: str) -> None:
    # 导出对话记录到 history 目录下的 markdown 文件
    history_dir = Path(__file__).parent / "history"
    history_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = history_dir / f"chat_history_{timestamp}.md"
    
    md_content = "# Weather Agent Chat History\n\n"
    md_content += f"**Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    md_content += "## Available Tools\n"
    md_content += "```json\n"
    md_content += f"{tools_json}\n"
    md_content += "```\n\n"
    for entry in history:
        role = entry.get("role")
        content = entry.get("content") or ""
        
        if role == "system":
            md_content += "## System\n"
            md_content += f"{content}\n\n"
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

if __name__ == "__main__":
    asyncio.run(main())
