from typing import Any, Union

from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter, ToolParameterOption
from core.tools.provider.builtin.comfyui.tools.comfyui_client import ComfyUiClient
from core.tools.tool.builtin_tool import BuiltinTool


class QueueTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        base_url = self.runtime.credentials.get("base_url", "")
        token = self.runtime.credentials.get("token", "")
        if not base_url:
            return self.create_text_message("请输入base_url")
        comfyui_api = ComfyUiClient(base_url, token)
        
        action = tool_parameters.get("action", "")
        if action == "remaining":
            return self.create_text_message(str(comfyui_api.get_queue_remaining()))
        elif action == "detail":
            return self.create_text_message(str(comfyui_api.get_queue_detail_status()))
        elif action == "clear":
            return self.create_text_message(str(comfyui_api.clear_queue()))
        elif action == "delete":
            task_id = tool_parameters.get("task_id", "")
            if not task_id:
                return self.create_text_message("请输入task_id")
            else:
                task_ids = [task_id]
                return self.create_text_message(str(comfyui_api.delete_queue_item(task_ids)))
        elif action == "interrupt":
            return self.create_text_message(str(comfyui_api.interrupt_current_task()))
        elif action == "history":
            task_id = tool_parameters.get("task_id", "")
            if not task_id:
                return self.create_text_message("请输入task_id")
            else:
                return self.create_text_message(str(comfyui_api.get_history(task_id)))
        else:
            return self.create_text_message("Invalid action")
        
    def get_runtime_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                label=I18nObject(en_US="Action", zh_Hans="操作"),
                human_description=I18nObject(
                    en_US="Action of the queue",
                    zh_Hans="队列操作方式"
                ),
                llm_description="Action of the queue",
                type=ToolParameter.ToolParameterType.SELECT,
                form=ToolParameter.ToolParameterForm.FORM,
                required=True,
                default="remaining",
                options=[
                    ToolParameterOption(value="remaining", label=I18nObject(en_US="Get Queue Remaining", zh_Hans="查询队列任务数")),
                    ToolParameterOption(value="detail", label=I18nObject(en_US="Get Queue Detail", zh_Hans="获取队列详情")),
                    ToolParameterOption(value="clear", label=I18nObject(en_US="Clear Queue", zh_Hans="清空队列任务")),
                    ToolParameterOption(value="delete", label=I18nObject(en_US="Delete Task", zh_Hans="删除指定任务")),
                    ToolParameterOption(value="interrupt", label=I18nObject(en_US="Interrupt Current Task", zh_Hans="中断当前任务")),
                    ToolParameterOption(value="history", label=I18nObject(en_US="Get History", zh_Hans="获取历史任务"))
                ],
            ),
            ToolParameter(
                name="task_id",
                label=I18nObject(en_US="Task ID", zh_Hans="任务ID"),
                human_description=I18nObject(en_US="Task ID for specific operations", zh_Hans="特定操作所需的任务ID"),
                llm_description="Task ID for specific operations",
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                required=False,
            )
        ]

