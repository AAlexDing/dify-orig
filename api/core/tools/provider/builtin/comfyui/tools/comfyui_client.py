import json
import random
import uuid

import httpx
from websocket import WebSocket
from yarl import URL

from core.file.file_manager import download
from core.file.models import File


class ComfyUiClient:
    def __init__(self, base_url: str, token: str = ''):
        self.base_url = URL(base_url)
        self.token = token

    def _get_url_with_token(self, path: str) -> str:
        url = URL(self.base_url) / path
        if self.token:
            url = url.with_query(token=self.token)
        return str(url)

    def check_connection(self):
        try:
            if not self.base_url:
                return False
            api_url = self._get_url_with_token("")
            response = httpx.get(url=api_url, timeout=(2, 10))
            if response.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
            return False

    def get_queue_remaining(self):
        url = self._get_url_with_token("prompt")
        response = httpx.get(url, timeout=(2, 10))
        return response.json().get("exec_info", {}).get("queue_remaining", 0)

    def get_queue_detail_status(self):
        url = self._get_url_with_token("queue")
        response = httpx.get(url, timeout=(2, 10))
        return response.json()
        
    def clear_queue(self):
        url = self._get_url_with_token("queue")
        response = httpx.post(url, data=json.dumps({"clear": True}), timeout=(2, 10))
        return response.json()
        
    def delete_queue_item(self, task_ids: list[str]):
        url = self._get_url_with_token("queue")
        response = httpx.post(url, data=json.dumps({"delete": task_ids}), timeout=(2, 10))
        return response.json()
    
    def interrupt_current_task(self):
        url = self._get_url_with_token("interrupt")
        response = httpx.post(url, timeout=(2, 10))
        return response.json()
    
    def get_history(self, prompt_id: str) -> dict:
        url = self._get_url_with_token("history")
        res = httpx.get(url, params={"prompt_id": prompt_id})
        history = res.json()[prompt_id]
        return history

    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        url = self._get_url_with_token("view")
        response = httpx.get(
            url,
            params={"filename": filename, "subfolder": subfolder, "type": folder_type},
        )
        return response.content

    def upload_image(self, image_file: File) -> dict:
        url = self._get_url_with_token("upload/image")
        file = download(image_file)
        files = {"image": (image_file.filename, file, image_file.mime_type), "overwrite": "true"}
        res = httpx.post(url, files=files)
        return res.json()

    def upload_mask(self, mask_file: File, type: str = "", subfolder: str = "", original_ref: str = ""):
        """
        上传蒙版图片接口，一般用于局部重绘
        original_ref	{“filename”:”下载.png”,”type”:”input”,”subfolder”:”clipspace”}	string
        """
        url = self._get_url_with_token("upload/mask")
        file = download(mask_file)
        req_body = {
            "image": file,
            "type": type,
            "subfolder": subfolder,
            "original_ref": original_ref
        }
        response = httpx.post(url, data=json.dumps(req_body), timeout=(2, 10))
        return response.json()

    def download_image(self, filename, subfolder, folder_type):
        url = self._get_url_with_token("view")
        response = httpx.get(url, params={"filename": filename, "subfolder": subfolder, "type": folder_type}, 
                             timeout=(2, 10))
        return response.content

    def queue_prompt(self, client_id: str, prompt: dict) -> str:
        url = self._get_url_with_token("prompt")
        res = httpx.post(url, json={"client_id": client_id, "prompt": prompt})
        prompt_id = res.json()["prompt_id"]
        return prompt_id

    def open_websocket_connection(self) -> tuple[WebSocket, str]:
        client_id = str(uuid.uuid4())
        ws = WebSocket()
        ws_address = f"ws://{self.base_url.authority}/ws?clientId={client_id}"
        if self.token:
            ws_address += "&token={}".format(self.token)
        ws.connect(ws_address)
        return ws, client_id

    def set_prompt_by_ksampler(self, origin_prompt: dict, positive_prompt: str, negative_prompt: str = "") -> dict:
        prompt = origin_prompt.copy()
        id_to_class_type = {id: details["class_type"] for id, details in prompt.items()}
        k_sampler = [key for key, value in id_to_class_type.items() if value == "KSampler"][0]
        prompt.get(k_sampler)["inputs"]["seed"] = random.randint(10**14, 10**15 - 1)
        positive_input_id = prompt.get(k_sampler)["inputs"]["positive"][0]
        prompt.get(positive_input_id)["inputs"]["text"] = positive_prompt

        if negative_prompt != "":
            negative_input_id = prompt.get(k_sampler)["inputs"]["negative"][0]
            prompt.get(negative_input_id)["inputs"]["text"] = negative_prompt

        return prompt

    def set_prompt_images_by_ids(self, origin_prompt: dict, image_names: list[str], image_ids: list[str]) -> dict:
        prompt = origin_prompt.copy()
        for index, image_node_id in enumerate(image_ids):
            prompt[image_node_id]["inputs"]["image"] = image_names[index]
        return prompt

    def set_prompt_images_by_default(self, origin_prompt: dict, image_names: list[str]) -> dict:
        prompt = origin_prompt.copy()
        id_to_class_type = {id: details["class_type"] for id, details in prompt.items()}
        load_image_nodes = [key for key, value in id_to_class_type.items() if value == "LoadImage"]
        for load_image, image_name in zip(load_image_nodes, image_names):
            prompt.get(load_image)["inputs"]["image"] = image_name
        return prompt

    def track_progress(self, prompt: dict, ws: WebSocket, prompt_id: str):
        node_ids = list(prompt.keys())
        finished_nodes = []

        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message["type"] == "progress":
                    data = message["data"]
                    current_step = data["value"]
                    print("In K-Sampler -> Step: ", current_step, " of: ", data["max"])
                if message["type"] == "execution_cached":
                    data = message["data"]
                    for itm in data["nodes"]:
                        if itm not in finished_nodes:
                            finished_nodes.append(itm)
                            print("Progress: ", len(finished_nodes), "/", len(node_ids), " Tasks done")
                if message["type"] == "executing":
                    data = message["data"]
                    if data["node"] not in finished_nodes:
                        finished_nodes.append(data["node"])
                        print("Progress: ", len(finished_nodes), "/", len(node_ids), " Tasks done")

                    if data["node"] is None and data["prompt_id"] == prompt_id:
                        break  # Execution is done
            else:
                continue

    def generate_image_by_prompt(self, prompt: dict) -> list[bytes]:
        try:
            ws, client_id = self.open_websocket_connection()
            prompt_id = self.queue_prompt(client_id, prompt)
            self.track_progress(prompt, ws, prompt_id)
            history = self.get_history(prompt_id)
            images = []
            for output in history["outputs"].values():
                for img in output.get("images", []):
                    image_data = self.get_image(img["filename"], img["subfolder"], img["type"])
                    images.append(image_data)
            return images
        finally:
            ws.close()

    def get_checkpoints(self) -> list[str]:
        """
        get checkpoints
        """
        try:
            if not self.base_url:
                return []
            api_url = self._get_url_with_token("models/checkpoints")
            response = httpx.get(url=api_url, timeout=(2, 10))
            if response.status_code != 200:
                return []
            else:
                return response.json()
        except Exception as e:
            return []
        
    def get_loras(self) -> list[str]:
        try:
            if not self.base_url:
                return []
            api_url = self._get_url_with_token("models/loras")
            response = httpx.get(url=api_url, timeout=(2, 10))
            if response.status_code != 200:
                return []
            else:
                return response.json()
        except Exception as e:
            return []

    def get_sample_methods(self) -> tuple[list[str], list[str]]:
        try:
            if not self.base_url:
                return [], []
            api_url = self._get_url_with_token("object_info/KSampler")
            response = httpx.get(url=api_url, timeout=(2, 10))
            if response.status_code != 200:
                return [], []
            else:
                data = response.json()["KSampler"]["input"]["required"]
                return data["sampler_name"][0], data["scheduler"][0]
        except Exception as e:
            return [], []

    def get_embeddings(self) -> list[str]:
        try:
            if not self.base_url:
                return []
            api_url = self._get_url_with_token("embeddings")
            response = httpx.get(url=api_url, timeout=(2, 10))
            if response.status_code != 200:
                return []
            else:
                return response.json()
        except Exception as e:
            return []

