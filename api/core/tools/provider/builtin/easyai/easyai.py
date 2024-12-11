from typing import Any

import socketio
from httpx import post
from yarl import URL

from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class EasyAiProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        base_url = URL(credentials.get("base_url"))
        refresh_token = credentials.get("refresh_token")
        socket_url = credentials.get("socket_url")
        try:
            response = post(
                f"{base_url}/auth/refreshTokens", 
                json={"refreshToken": refresh_token},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*"
                }
            )
            if response.status_code == 401:
                raise ToolProviderCredentialValidationError("认证失败：refresh token 无效或已过期")
            
            # 检查 HTTP 响应状态码
            response.raise_for_status()
            # 获取响应的 JSON 数据
            response_data = response.json()
            
            if not response_data.get("token"):
                raise ToolProviderCredentialValidationError("Invalid response: token not found")

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
