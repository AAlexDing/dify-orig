import io
from typing import Any, Union

from httpx import get

from configs import dify_config
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
        image_files = tool_parameters.get("image_file", [])

        if not image_files or not isinstance(image_files, list) or len(image_files) == 0:
            return self.create_text_message("未提供有效的图片文件")
        
        results = {}
        for idx, file_info in enumerate(image_files):
            if not isinstance(file_info, File):
                return self.create_text_message("无效的文件对象")
            
            file_content = self.get_file_content(file_info)
            if not file_content:
                return self.create_text_message("无法获取图片文件内容")
            
            file_object = io.BytesIO(file_content)
            file_object.name = file_info.filename or "uploaded_image.png"
            
            upload_resp = comfyui_api.upload_image(file_object)
            if not upload_resp:
                results[str(idx)] = ""
                continue
            
            subfolder = upload_resp.get("subfolder")
            name = upload_resp.get("name")
            if not subfolder:
                results[str(idx)] = name
            else:
                results[str(idx)] = subfolder + '\\' + name
        
        return self.create_json_message(results)
        
    def get_file_content(self, file: File):
        url = file.generate_url()
        if url:
            if not url.startswith("http"):
                base_url = dify_config.FILES_URL.rstrip("/")
                url = base_url + url
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