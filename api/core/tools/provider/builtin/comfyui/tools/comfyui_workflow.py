import json
import re
from typing import Any, Union

from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter
from core.tools.provider.builtin.comfyui.tools.comfyui_client import ComfyUiClient
from core.tools.tool.builtin_tool import BuiltinTool


def sanitize_json_string(s):
    escape_dict = {
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\b": "\\b",
        "\f": "\\f",
    }
    for char, escaped in escape_dict.items():
        s = s.replace(char, escaped)

    return s


class ComfyWorkflowTool(BuiltinTool):
    def _invoke(
        self, user_id: str, tool_parameters: dict[str, Any]
    ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        base_url = self.runtime.credentials.get("base_url", "")
        if not base_url:
            return self.create_text_message("请输入base_url")
        token = self.runtime.credentials.get("token", "")
        comfyui = ComfyUiClient(base_url, token)
        json_string = tool_parameters.get("json_string", "")
        if not json_string:
            return self.create_text_message("请输入json_string")

        try:
            # 清理JSON字符串
            json_string = re.sub(r'[\t\n\r]', '', json_string)  # 移除制表符和换行符
            json_string = re.sub(r'[\xa0]', '', json_string)  # 移除不间断空格
            json_string = json_string.replace("\\", "/!")  # 绕过反斜杠错误
            workflow = json.loads(json_string, strict=False)
            workflow = replace_in_object(workflow)
            images = comfyui.generate_image_by_prompt(prompt=workflow)

            result = []
            for img in images:
                result.append(
                    self.create_blob_message(
                        blob=img, meta={"mime_type": "image/png"}, save_as=self.VariableKey.IMAGE.value
                    )
                )
            return result

        except json.JSONDecodeError as e:
            return self.create_text_message(f"无效的JSON字符串: {str(e)}")
        except Exception as e:
            return self.create_text_message(f"生成图像失败: {str(e)}")

    def get_runtime_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="json_string",
                label=I18nObject(en_US="Json String", zh_Hans="Json 字符串"),
                human_description=I18nObject(
                    en_US="An API format json string exported from ComfyUI(You need to enable the developer options in ComfyUI and click 'Export(API Format)')",
                    zh_Hans="由ComfyUI导出的API格式的json字符串（注意：需要先在ComfyUI中启用开发者选项，并点击“Export(API Format)”）",
                ),
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="The API format json string exported from ComfyUI Workflow",
                required=True,
            ),
        ]


def replace_in_object(obj):
    '''
    绕过反斜杠错误
    '''
    if isinstance(obj, dict):
        return {k: replace_in_object(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_in_object(elem) for elem in obj]
    elif isinstance(obj, str):
        return obj.replace('/!', '\\')
    else:
        return obj
