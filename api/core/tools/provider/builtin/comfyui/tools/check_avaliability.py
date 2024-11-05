
from typing import Any, Union

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.provider.builtin.comfyui.tools.comfyui_client import ComfyUiClient
from core.tools.tool.builtin_tool import BuiltinTool


class CheckAvaliabilityTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        base_url = self.runtime.credentials.get("base_url", "")
        token = self.runtime.credentials.get("token", "")
        if not base_url:
            return self.create_text_message("请输入base_url")
        comfyui_api = ComfyUiClient(base_url, token)
        result = comfyui_api.check_connection()
        if result:
            return self.create_text_message("1")
        else:
            return self.create_text_message("0")

