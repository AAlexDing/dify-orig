import json
from pathlib import Path
from typing import Any

import socketio
from httpx import post
from yarl import URL

from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class EasyAiProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        base_url = URL(credentials.get("base_url"))
        username = credentials.get("username")
        password = credentials.get("password")
        socket_url = credentials.get("socket_url")
        try:
            response = post(
                f"{base_url}/users/loginByUsername", 
                json={"username": username, "password": password},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            json_data = response.json()
            if not json_data.get("status") == "success":
                raise ToolProviderCredentialValidationError("认证失败：用户名或密码错误")
            
            data = json_data.get("data")
            
            if not data.get("token"):
                raise ToolProviderCredentialValidationError("Invalid response: token not found")
            
            Path("easyai.json").write_text(json.dumps(data))

            # 检查socketio连接
            sio = socketio.Client()
            sio.connect(
                socket_url,
                transports=['websocket'],
                wait_timeout=10,
                headers={
                    'Accept': '*/*',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Connection': 'Upgrade',
                    'Origin': socket_url,
                }
            )
            if not sio.connected:
                raise ToolProviderCredentialValidationError(f"无法连接到SocketIO: {socket_url}")
            sio.disconnect()
                
        except Exception as e:
            raise ToolProviderCredentialValidationError(f"无法连接到 {base_url}: {str(e)}")
