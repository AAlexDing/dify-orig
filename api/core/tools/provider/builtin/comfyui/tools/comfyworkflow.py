import json
import uuid
from typing import Any, Union
import re
import websocket

from httpx import get, post
from yarl import URL

from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolInvokeMessage, ToolParameter
from core.tools.tool.builtin_tool import BuiltinTool

class ComfyWorkflowTool(BuiltinTool):
    def _invoke(
        self, user_id: str, tool_parameters: dict[str, Any]
    ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        base_url = self.runtime.credentials.get("base_url", "")
        if not base_url:
            return self.create_text_message("请输入base_url")

        json_string = tool_parameters.get("json_string", "")
        if not json_string:
            return self.create_text_message("请输入json_string")

        try:
            # 清理JSON字符串
            json_string = re.sub(r'[\t\n\r]', '', json_string)  # 移除制表符和换行符
            json_string = re.sub(r'[\xa0]', '', json_string)  # 移除不间断空格
            workflow = json.loads(json_string)
            client_id = str(uuid.uuid4())
            result = self.queue_prompt_image(base_url, client_id, prompt=workflow)

            image = b""
            for node in result:
                for img in result[node]:
                    if img:
                        image = img
                        break

            return self.create_blob_message(
                blob=image, meta={"mime_type": "image/png"}, save_as=self.VariableKey.IMAGE.value
            )

        except json.JSONDecodeError as e:
            return self.create_text_message(f"无效的JSON字符串: {str(e)}")
        except Exception as e:
            return self.create_text_message(f"生成图像失败: {str(e)}")

    def queue_prompt_image(self, base_url, client_id, prompt):
        """
        send prompt task and rotate
        """
        # initiate task execution
        url = str(URL(base_url) / "prompt")
        respond = post(url, data=json.dumps({"client_id": client_id, "prompt": prompt}), timeout=(2, 10))
        prompt_id = respond.json()["prompt_id"]

        ws = websocket.WebSocket()
        if "https" in base_url:
            ws_url = base_url.replace("https", "ws")
        else:
            ws_url = base_url.replace("http", "ws")
        ws.connect(str(URL(f"{ws_url}") / "ws") + f"?clientId={client_id}", timeout=120)

        # websocket rotate execution status
        output_images = {}
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message["type"] == "executing":
                    data = message["data"]
                    if data["node"] is None and data["prompt_id"] == prompt_id:
                        break  # Execution is done
                elif message["type"] == "status":
                    data = message["data"]
                    if data["status"]["exec_info"]["queue_remaining"] == 0 and data.get("sid"):
                        break  # Execution is done
            else:
                continue  # previews are binary data

        # download image when execution finished
        history = self.get_history(base_url, prompt_id)[prompt_id]
        for o in history["outputs"]:
            for node_id in history["outputs"]:
                node_output = history["outputs"][node_id]
                if "images" in node_output:
                    images_output = []
                    for image in node_output["images"]:
                        image_data = self.download_image(base_url, image["filename"], image["subfolder"], image["type"])
                        images_output.append(image_data)
                    output_images[node_id] = images_output

        ws.close()

        return output_images
    
    def get_history(self, base_url, prompt_id):
        """
        get history
        """
        url = str(URL(base_url) / "history")
        respond = get(url, params={"prompt_id": prompt_id}, timeout=(2, 10))
        return respond.json()

    def download_image(self, base_url, filename, subfolder, folder_type):
        """
        download image
        """
        url = str(URL(base_url) / "view")
        response = get(url, params={"filename": filename, "subfolder": subfolder, "type": folder_type}, timeout=(2, 10))
        return response.content
    
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