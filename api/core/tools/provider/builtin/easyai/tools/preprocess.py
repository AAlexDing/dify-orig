import io
from typing import Any, Union

from httpx import get
from PIL import Image

from configs import dify_config
from core.file.models import File
from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter
from core.tools.tool.builtin_tool import BuiltinTool


class PreprocessTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        # 获取参数
        max_resolution = tool_parameters.get("max_resolution", 1024)
        quality = tool_parameters.get("quality", 70)
        
        # 获取图片文件
        image_files = tool_parameters.get("image_file", [])
        if not image_files or not isinstance(image_files, list) or len(image_files) == 0:
            return self.create_text_message("请先上传图片")
            
        processed_images = []
        for file_info in image_files:
            if not isinstance(file_info, File):
                return self.create_text_message("无效的文件对象")
            
            # 获取文件内容
            file_content = self.get_file_content(file_info)
            if not file_content:
                return self.create_text_message("无法获取图片文件内容")
            
            # 打开图片
            img = Image.open(io.BytesIO(file_content))
            
            # 转换为RGB模式
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1])  # -1 是透明通道
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 计算缩放比例
            width, height = img.size
            if width > max_resolution or height > max_resolution:
                if width > height:
                    new_width = max_resolution
                    new_height = int(height * max_resolution / width)
                else:
                    new_height = max_resolution 
                    new_width = int(width * max_resolution / height)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 保存处理后的图片
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality)
            processed_images.append(output.getvalue())
            
        return [
            self.create_json_message({"count": len(processed_images)}),
            *[self.create_blob_message(blob=img, meta={"mime_type": "image/jpeg"}) 
              for img in processed_images]
        ]

    def get_file_content(self, file: File):
        url = file.generate_url()
        if url:
            if not url.startswith("http"):
                if dify_config.FILES_URL:
                    base_url = dify_config.FILES_URL.rstrip("/")
                    url = base_url + url
                else:
                    base_url = "http://127.0.0.1:5001"
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
            ToolParameter(
                name="max_resolution",
                label=I18nObject(en_US="Max Resolution", zh_Hans="最大分辨率"),
                human_description=I18nObject(
                    en_US="Maximum resolution for image scaling",
                    zh_Hans="图像缩放的最大分辨率"
                ),
                llm_description="Maximum resolution limit for scaling large images",
                type=ToolParameter.ToolParameterType.NUMBER,
                form=ToolParameter.ToolParameterForm.FORM,
                required=True,
                default=1024,
                min=128,
                max=4096
            ),
            ToolParameter(
                name="quality",
                label=I18nObject(en_US="Save Quality", zh_Hans="保存质量"),
                human_description=I18nObject(
                    en_US="Image save quality (1-100)",
                    zh_Hans="图像保存质量(1-100)"
                ),
                llm_description="Quality setting for saving processed images",
                type=ToolParameter.ToolParameterType.NUMBER,
                form=ToolParameter.ToolParameterForm.FORM,
                required=True,
                default=70,
                min=1,
                max=100
            )
        ]

