#!/usr/bin/env python3
"""
高度なMCPサーバーの例
ローカルファイルシステム、データベース、外部API連携の機能を提供
"""

import asyncio
import os
import sqlite3
import json
import requests
from datetime import datetime
from pathlib import Path
import subprocess

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
server = Server("advanced-mcp-server")

# 作業ディレクトリの設定
WORK_DIR = Path(__file__).parent / "mcp_workspace"
WORK_DIR.mkdir(exist_ok=True)

# SQLiteデータベースの初期化
DB_PATH = WORK_DIR / "notes.db"

def init_database():
    """ノート管理用のデータベースを初期化"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            due_date TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_database()


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """利用可能なリソースのリストを返す"""
    resources = [
        Resource(
            uri=AnyUrl("mcp://workspace-files"),
            name="Workspace Files",
            description="Files in the MCP workspace directory",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("mcp://notes"),
            name="Stored Notes",
            description="Notes stored in local database",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("mcp://tasks"),
            name="Task List",
            description="Task management system",
            mimeType="application/json",
        )
    ]
    return resources


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """リソースの内容を読み取る"""
    uri_str = str(uri)
    
    if uri_str == "mcp://workspace-files":
        files = []
        for file_path in WORK_DIR.rglob("*"):
            if file_path.is_file() and file_path.name != "notes.db":
                files.append({
                    "name": file_path.name,
                    "path": str(file_path.relative_to(WORK_DIR)),
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
        return json.dumps(files, indent=2, ensure_ascii=False)
    
    elif uri_str == "mcp://notes":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC")
        notes = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        conn.close()
        return json.dumps(notes, indent=2, ensure_ascii=False)
    
    elif uri_str == "mcp://tasks":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        tasks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        conn.close()
        return json.dumps(tasks, indent=2, ensure_ascii=False)
    
    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """利用可能なツールのリストを返す"""
    return [
        Tool(
            name="file_operations",
            description="Read, write, and manage files in the workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "list", "delete"],
                        "description": "File operation to perform"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Name of the file (required for read, write, delete)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to file (required for write)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="note_manager",
            description="Manage notes in local database",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "read", "update", "delete", "search"],
                        "description": "Note operation to perform"
                    },
                    "title": {
                        "type": "string",
                        "description": "Note title"
                    },
                    "content": {
                        "type": "string",
                        "description": "Note content"
                    },
                    "note_id": {
                        "type": "integer",
                        "description": "Note ID (for read, update, delete)"
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Search query (for search)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="task_manager",
            description="Manage tasks and to-do items",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "update", "complete", "delete"],
                        "description": "Task operation to perform"
                    },
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "task_id": {
                        "type": "integer",
                        "description": "Task ID"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date (YYYY-MM-DD format)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="system_info",
            description="Get system information and execute safe system commands",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["disk_usage", "memory_info", "cpu_info", "current_time", "weather"],
                        "description": "System command to execute"
                    },
                    "location": {
                        "type": "string",
                        "description": "Location for weather (city name)"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="web_request",
            description="Make HTTP requests to external APIs",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to request"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "default": "GET",
                        "description": "HTTP method"
                    },
                    "headers": {
                        "type": "object",
                        "description": "HTTP headers"
                    },
                    "data": {
                        "type": "object",
                        "description": "Request data (for POST)"
                    }
                },
                "required": ["url"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """ツールを実行する"""
    
    try:
        if name == "file_operations":
            action = arguments.get("action")
            filename = arguments.get("filename")
            
            if action == "list":
                files = []
                for file_path in WORK_DIR.iterdir():
                    if file_path.is_file() and file_path.name != "notes.db":
                        files.append({
                            "name": file_path.name,
                            "size": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        })
                
                return [types.TextContent(
                    type="text",
                    text=f"ワークスペースファイル一覧:\n" + json.dumps(files, indent=2, ensure_ascii=False)
                )]
            
            elif action == "read":
                file_path = WORK_DIR / filename
                if file_path.exists():
                    content = file_path.read_text(encoding='utf-8')
                    return [types.TextContent(
                        type="text",
                        text=f"ファイル '{filename}' の内容:\n\n{content}"
                    )]
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"ファイル '{filename}' が見つかりません。"
                    )]
            
            elif action == "write":
                content = arguments.get("content", "")
                file_path = WORK_DIR / filename
                file_path.write_text(content, encoding='utf-8')
                return [types.TextContent(
                    type="text",
                    text=f"ファイル '{filename}' に書き込みました。"
                )]
            
            elif action == "delete":
                file_path = WORK_DIR / filename
                if file_path.exists():
                    file_path.unlink()
                    return [types.TextContent(
                        type="text",
                        text=f"ファイル '{filename}' を削除しました。"
                    )]
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"ファイル '{filename}' が見つかりません。"
                    )]
        
        elif name == "note_manager":
            action = arguments.get("action")
            conn = sqlite3.connect(DB_PATH)
            
            if action == "create":
                title = arguments.get("title", "無題")
                content = arguments.get("content", "")
                cursor = conn.execute(
                    "INSERT INTO notes (title, content) VALUES (?, ?)",
                    (title, content)
                )
                conn.commit()
                note_id = cursor.lastrowid
                conn.close()
                return [types.TextContent(
                    type="text",
                    text=f"ノート '{title}' を作成しました（ID: {note_id}）"
                )]
            
            elif action == "search":
                query = arguments.get("search_query", "")
                cursor = conn.execute(
                    "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC",
                    (f"%{query}%", f"%{query}%")
                )
                notes = cursor.fetchall()
                conn.close()
                
                if notes:
                    result = f"検索結果 ('{query}'):\n\n"
                    for note in notes:
                        result += f"ID: {note[0]} | {note[1]}\n{note[2][:100]}...\n\n"
                    return [types.TextContent(type="text", text=result)]
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"'{query}' に一致するノートが見つかりませんでした。"
                    )]
            
            # その他のnote_manager操作...
            conn.close()
        
        elif name == "system_info":
            command = arguments.get("command")
            
            if command == "disk_usage":
                result = subprocess.run(['df', '-h'], capture_output=True, text=True)
                return [types.TextContent(
                    type="text",
                    text=f"ディスク使用量:\n{result.stdout}"
                )]
            
            elif command == "current_time":
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return [types.TextContent(
                    type="text",
                    text=f"現在時刻: {current_time}"
                )]
            
            elif command == "weather":
                location = arguments.get("location", "Tokyo")
                # OpenWeatherMap API の例（APIキーが必要）
                return [types.TextContent(
                    type="text",
                    text=f"{location}の天気情報を取得するにはAPIキーが必要です。"
                )]
        
        elif name == "web_request":
            url = arguments.get("url")
            method = arguments.get("method", "GET")
            
            try:
                if method == "GET":
                    response = requests.get(url, timeout=10)
                    return [types.TextContent(
                        type="text",
                        text=f"HTTP {response.status_code} レスポンス:\n{response.text[:1000]}..."
                    )]
                else:
                    return [types.TextContent(
                        type="text",
                        text="POSTリクエストは実装中です。"
                    )]
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"リクエストエラー: {str(e)}"
                )]
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"エラーが発生しました: {str(e)}"
        )]
    
    return [types.TextContent(
        type="text",
        text=f"不明なツール: {name}"
    )]


async def main():
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="advanced-mcp-server",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
