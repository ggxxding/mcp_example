from types import SimpleNamespace
import asyncio
import unittest

from unittest.mock import AsyncMock, patch

from agent_weather_fastmcp import (
    convert_mcp_tools_to_openai_schema,
    get_weather_tools_schema,
)


class ToolSchemaTests(unittest.TestCase):
    def test_convert_mcp_tools_to_openai_schema(self):
        input_schema = {
            "type": "object",
            "properties": {"state": {"type": "string"}},
            "required": ["state"],
        }
        tools = [
            SimpleNamespace(
                name="get_alerts",
                description="根据美国州代码获取当前的天气预警信息",
                inputSchema=input_schema,
            )
        ]

        self.assertEqual(
            convert_mcp_tools_to_openai_schema(tools),
            [
                {
                    "type": "function",
                    "function": {
                        "name": "get_alerts",
                        "description": "根据美国州代码获取当前的天气预警信息",
                        "parameters": input_schema,
                    },
                }
            ],
        )

    def test_get_weather_tools_schema_uses_http_transport(self):
        expected_schema = [{"type": "function", "function": {"name": "get_alerts"}}]

        with (
            patch(
                "agent_weather_fastmcp.get_weather_tools_schema_http",
                new=AsyncMock(return_value=expected_schema),
            ) as http_schema,
            patch(
                "agent_weather_fastmcp.get_weather_tools_schema_stdio",
                new=AsyncMock(return_value=[]),
            ) as stdio_schema,
        ):
            self.assertEqual(
                asyncio.run(get_weather_tools_schema("http")),
                expected_schema,
            )

        http_schema.assert_awaited_once_with()
        stdio_schema.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
