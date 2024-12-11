import json
from typing import Any, Union

from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter
from core.tools.provider.builtin.easyai.tools.easyai_client import EasyAiClient
from core.tools.tool.builtin_tool import BuiltinTool


class EasyAiWorkflowTool(BuiltinTool):
    def _invoke(
        self, user_id: str, tool_parameters: dict[str, Any]
    ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        
        # 获取配置
        base_url = self.runtime.credentials.get("base_url", "")
        if not base_url:
            return self.create_text_message("请输入base_url")
        refresh_token = self.runtime.credentials.get("refresh_token", "")
        if not refresh_token:
            return self.create_text_message("请输入refresh_token")
        socket_url = self.runtime.credentials.get("socket_url", "")
        if not socket_url:
            return self.create_text_message("请输入socket_url")
        send_msg_api = self.runtime.credentials.get("send_msg_api", "")
        if not send_msg_api:
            return self.create_text_message("请输入send_msg_api")
        easyai = EasyAiClient(base_url, socket_url, send_msg_api, refresh_token)
        
        # 获取参数
        params = tool_parameters.get("params", "")
        if not params:
            return self.create_text_message("请输入params")
        params = json.loads(params)
        options = tool_parameters.get("options", "")
        if not options:
            return self.create_text_message("请输入options")
        options = json.loads(options)
        receiver_name = tool_parameters.get("receiver_name", "")
        group_name = tool_parameters.get("group_name", "")
        #message_interval = tool_parameters.get("message_interval", 25)

        images_url = easyai.submit_task(params, options, receiver_name, group_name)
        results = {}
        for idx, image_url in enumerate(images_url):
            if not isinstance(image_url, str):
                return self.create_text_message("无效的图片URL")
            
            if not image_url:
                results[str(idx)] = ""
                continue
            results[str(idx)] = image_url
        return self.create_json_message(results)

    def get_runtime_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="params",
                label=I18nObject(en_US="Workflow Parameters", zh_Hans="工作流参数"),
                human_description=I18nObject(
                    en_US="The parameters of the workflow",
                    zh_Hans="工作流参数",
                ),
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="The parameters of the workflow",
                required=True,
            ),
            ToolParameter(
                name="options",
                label=I18nObject(en_US="Workflow", zh_Hans="工作流"),
                human_description=I18nObject(en_US="The options of the workflow", zh_Hans="工作流"),
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="The options of the workflow",
                required=True,
            ),
            ToolParameter(
                name="receiver_name",
                label=I18nObject(en_US="Receiver Name", zh_Hans="微信接收者昵称"),
                human_description=I18nObject(en_US="The name of the receiver", zh_Hans="微信接收者昵称"),
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="The name of the receiver",
                required=False,
            ),
            ToolParameter(
                name="group_name",
                label=I18nObject(en_US="Group Name (Optional)", zh_Hans="微信群名称（可选）"),
                human_description=I18nObject(en_US="The name of the group", zh_Hans="微信群名称"),
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="The name of the group",
                required=False,
            ),
        ]

