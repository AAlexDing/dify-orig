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
        
        # 获取参数
        params = tool_parameters.get("params", "")
        if not params:
            return self.create_text_message("请输入params")
        params = json.loads(params)
        print(f"params: {params}")
        options = tool_parameters.get("options", "")
        if not options:
            return self.create_text_message("请输入options")
        options = json.loads(options)
        print(f"options: {options}")
        receiver_name = tool_parameters.get("receiver_name", "")
        group_name = tool_parameters.get("group_name", "")
        message_interval = tool_parameters.get("message_interval", 25)

        images_url = easyai.submit_task(params, options, receiver_name, group_name, message_interval)
        if not images_url:
            return self.create_text_message("任务执行失败")
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
            ToolParameter(
                name="message_interval",
                label=I18nObject(en_US="Message Interval", zh_Hans="微信进度通知消息间隔"),
                human_description=I18nObject(en_US="The interval of the message", zh_Hans="微信进度通知消息间隔"),
                llm_description="The interval of the message",
                type=ToolParameter.ToolParameterType.NUMBER,
                form=ToolParameter.ToolParameterForm.FORM,
                required=True,
                default=25,
                min=1,
                max=100
            )
        ]

