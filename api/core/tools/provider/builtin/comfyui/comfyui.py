from typing import Any

import websocket
from yarl import URL

from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class ComfyUIProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        ws = websocket.WebSocket()
        base_url = URL(credentials.get("base_url"))
        token = URL(credentials.get("token"))
        ws_address = f"ws://{base_url.authority}/ws?clientId=test123"
        if token:
            ws_address += "&token={}".format(token)
        try:
            ws.connect(ws_address)
        except Exception as e:
            raise ToolProviderCredentialValidationError(f"can not connect to {ws_address}")
        finally:
            ws.close()
