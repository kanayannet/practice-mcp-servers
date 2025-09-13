#!/usr/bin/env python3
"""
簡単なMCPサーバーの例
数学計算とテキスト処理の機能を提供
"""

import asyncio
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource, 
    Tool, 
    TextContent, 
    ImageContent, 
    EmbeddedResource
)
from pydantic import AnyUrl
import mcp.types as types


# サーバーインスタンスを作成
server = Server("simple-mcp-server")


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """利用可能なリソースのリストを返す"""
    return [
        Resource(
            uri=AnyUrl("sample://greeting"),
            name="Sample Greeting",
            description="A sample greeting resource",
            mimeType="text/plain",
        )
    ]


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """リソースの内容を読み取る"""
    if str(uri) == "sample://greeting":
        return "Hello from MCP Server! This is a sample resource."
    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """利用可能なツールのリストを返す"""
    return [
        Tool(
            name="calculator",
            description="Perform basic mathematical calculations",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                    }
                },
                "required": ["expression"]
            }
        ),
        Tool(
            name="text_analyzer",
            description="Analyze text and return statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to analyze"
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="reverse_text",
            description="Reverse the order of characters in text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to reverse"
                    }
                },
                "required": ["text"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """ツールを実行する"""
    
    if name == "calculator":
        try:
            expression = arguments.get("expression", "")
            # 安全性のため、基本的な数学関数のみ許可
            allowed_names = {
                "abs": abs, "round": round, "min": min, "max": max,
                "pow": pow, "sum": sum, "len": len
            }
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return [
                types.TextContent(
                    type="text",
                    text=f"計算結果: {expression} = {result}"
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"計算エラー: {str(e)}"
                )
            ]
    
    elif name == "text_analyzer":
        text = arguments.get("text", "")
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.split('\n'))
        
        analysis = f"""テキスト分析結果:
文字数: {char_count}
単語数: {word_count}
行数: {line_count}
空白を除く文字数: {len(text.replace(' ', '').replace('\n', '').replace('\t', ''))}
"""
        return [
            types.TextContent(
                type="text",
                text=analysis
            )
        ]
    
    elif name == "reverse_text":
        text = arguments.get("text", "")
        reversed_text = text[::-1]
        return [
            types.TextContent(
                type="text",
                text=f"元のテキスト: {text}\n逆順テキスト: {reversed_text}"
            )
        ]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    # Stdio transport を使用
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="simple-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
