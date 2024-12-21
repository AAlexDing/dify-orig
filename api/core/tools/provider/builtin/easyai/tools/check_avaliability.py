
from typing import Any, Union

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.provider.builtin.easyai.tools.easyai_client import EasyAiClient
from core.tools.tool.builtin_tool import BuiltinTool


class CheckAvaliabilityTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        # 获取配置
        base_url = self.runtime.credentials.get("base_url", "")
        if not base_url:
            return self.create_text_message("请输入base_url")
        username = self.runtime.credentials.get("username", "")
        if not username:
            return self.create_text_message("请输入username")
        password = self.runtime.credentials.get("password", "")
        if not password:
            return self.create_text_message("请输入password")
        socket_url = self.runtime.credentials.get("socket_url", "")
        if not socket_url:
            return self.create_text_message("请输入socket_url")
        send_msg_api = self.runtime.credentials.get("send_msg_api", "")
        if not send_msg_api:
            return self.create_text_message("请输入send_msg_api")
        easyai = EasyAiClient(base_url, socket_url, send_msg_api, username, password)
        
        draw_server = easyai.get_draw_server()
        # 0: 不可用，1: 可用，2: 未连接
        if draw_server is None:
            return self.create_text_message("2")
        if draw_server:
            for server in draw_server:
                if server.get("status") == 1:
                    return self.create_text_message("1")
            return self.create_text_message("0")
        else:
            return self.create_text_message("0")

