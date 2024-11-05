import io
from typing import Any, Union

from httpx import get

from core.file.models import File
from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter
from core.tools.provider.builtin.comfyui.tools.comfyui_client import ComfyUiClient
from core.tools.tool.builtin_tool import BuiltinTool


class UploadImageTool(BuiltinTool):
    def _invoke(
        self, user_id: str, tool_parameters: dict[str, Any]
    ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        base_url = self.runtime.credentials.get("base_url", "")
        token = self.runtime.credentials.get("token", "")
        if not base_url:
            return self.create_text_message("请输入base_url")
        comfyui_api = ComfyUiClient(base_url, token)
        image_file = tool_parameters.get("image_file", [])

        if not image_file or not isinstance(image_file, list) or len(image_file) == 0:
            return self.create_text_message("未提供有效的图片文件")
        
        file_info = image_file[0]
        if not isinstance(file_info, File):
            return self.create_text_message("无效的文件对象")
        
        file_content = self.get_file_content(file_info)
        if not file_content:
            return self.create_text_message("无法获取图片文件内容")
        
        file_object = io.BytesIO(file_content)
        file_object.name = file_info.filename or "uploaded_image.png"
        
        result = comfyui_api.upload_image(file_object)
        if result:
            return self.create_text_message(f"{result}")
        else:
            return self.create_text_message("")
        
    def get_file_content(self, file: File):
        url = file.generate_url()
        if url:
            if not url.startswith("http"):
                url = "http://kanju.la:33333" + url
            response = get(url)
            if response.status_code == 200:
                return response.content
        return None
    
    def get_runtime_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="image_file",
                label=I18nObject(en_US="Image File", zh_Hans="图片文件"),
                human_description=I18nObject(
                    en_US="The image file in the conversation",
                    zh_Hans="对话内的图片文件",
                ),
                type=ToolParameter.ToolParameterType.FILES,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="The image file in the conversation",
                required=True,
            ),
        ]