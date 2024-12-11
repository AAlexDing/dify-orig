import json
import os
import time
from pathlib import Path

import httpx
import socketio
from yarl import URL


class EasyAiClient:
    def __init__(self, base_url: str, socket_url: str, send_msg_api: str = "", refresh_token: str = ""):
        self.base_url = URL(base_url)
        self.refresh_token = refresh_token
        self.socket_url = socket_url
        self.send_msg_api = send_msg_api
        self.send_msg_total = None
        self.sent_progress_points = set()
        
        self.client_id = ""
        self.client_username = ""
        self.output = []
        self.get_token()

    def get_token(self):
        # 把获取到的状态放在本地easyai.json文件中，如果token有效，则返回token，否则重新获取
        if os.path.exists("easyai.json"):
            local_status = Path("easyai.json").read_text()
            if self.check_token_valid(local_status):
                status = json.loads(local_status)
                self.client_id = status.get("_id")
                self.client_username = status.get("username")
                return status.get("token")
        response = httpx.post(
            f"{self.base_url}/auth/refreshTokens",
            json={"refreshToken": self.refresh_token},
            headers={"Content-Type": "application/json", "Accept": "*/*"},
        )
        response_data = response.json()
        self.client_id = response_data.get("_id")
        self.client_username = response_data.get("username")
        Path("easyai.json").write_text(json.dumps(response_data))
        return response_data.get("token")

    def check_token_valid(self, status: str):
        """
        检查token是否有效
        """
        status = json.loads(status)
        token = status.get("token")
        if not token:
            return False
        response = httpx.get(
            f"{self.base_url}/auth-token",
            headers={"Content-Type": "application/json", "Accept": "*/*", "Authorization": f"Bearer {token}"},
        )
        return response.status_code == 200

    def get_draw_server(self):
        try:
            response = httpx.get(f"{self.base_url}/draw/server", timeout=(2, 10), 
                                 headers={"Authorization": f"Bearer {self.get_token()}"})
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []

    def create_history(self, workflow_id: str, user_id: str, params: dict, options: dict, type: str = "image"):
        """
        创建绘图历史
        """
        # created_at 格式 1733758176606
        created_at = int(time.time() * 1000)
        response = httpx.post(
            f"{self.base_url}/draw/history",
            json={"workflow_id": workflow_id, "user_id": user_id, "params": params, "options": options, "type": type,
                  "status": 0, "created_at": created_at},
            headers={"Authorization": f"Bearer {self.get_token()}"},
        )
        response_data = response.json()
        task_id = response_data.get("_id", "")
        return task_id
        
    def submit_custom_workflow(self, socket_id: str, params: dict, options: dict):
        """
        提交自定义工作流
        """
        response = httpx.post(
            f"{self.base_url}/draw/customeWorkflow",
            json={"client_id": self.client_id, "socket_id": socket_id, "params": params, "options": options},
            headers={"Authorization": f"Bearer {self.get_token()}"}, timeout=(2, 10)
        )
        if response.status_code == 201:
            status = response.json().get("status")
            # status: 'submitted' | 'success' | 'failed' | 'rejected';
            return status
        else:
            return "failed"

    def upload_image(self, image_file):
        """
        上传图片
        """
        response = httpx.post(
            f"{self.base_url}/file/upload",
            headers={"Authorization": f"Bearer {self.get_token()}"},
            files={"file": image_file} 
        )
        return response.json()

    def send_message_to_dow(self, message: str):
        """
        发送消息到dow
        """
        if not self.send_msg_api:
            return
        if not self.receiver_name:
            return
        template = {
            "data_list": [{"receiver_name": [self.receiver_name], "message": message, "group_name": [self.group_name]}]
        }
        httpx.post(self.send_msg_api, json=template)

    def init_socket(self):
        # socketio连接
        self.sio = socketio.Client()

        @self.sio.on('connect')
        def on_connect():
            # print("连接成功，当前sid：", self.sio.sid)
            # 连接成功后发送认证消息
            auth_message = {
                "user_id": self.client_id,
                "type": "auth"
            }
            self.sio.emit("message", auth_message)
            # print(f"已发送认证消息: {auth_message}")
            
        @self.sio.on('connect_error')
        def on_connect_error(data):
            print(f"连接错误: {data}")
            
        @self.sio.on('disconnect')
        def on_disconnect():
            print("连接断开")

        @self.sio.on('message')
        def on_message(data):
            # print(f"收到消息: {data}")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    print("消息格式不是JSON")
                    return
                    
            if isinstance(data, dict) and 'queue_status' in data:
                message = ""
                queue_status = data['queue_status']
                time_remained = queue_status.get('time_remained', None)
                progress = queue_status.get('progress', 0)
                status = queue_status.get('status')
                queue = queue_status.get('queue')
                
                if self.send_msg_total is None:
                    # 第一次接收到的time_remained 决定发送几次
                    self.send_msg_total = max(1, int(time_remained / self.message_interval))
                    message = f"开始任务，预计时间: {time_remained}秒"
                    if queue:
                        message += f"队列人数: {queue}"
                else:
                    # 发送n次就均分100/(n+1)段
                    interval = 100 / (self.send_msg_total + 1)
                    progress_points = [int(interval * i) for i in range(1, self.send_msg_total + 1)]
                    for point in progress_points:
                        if progress > point and point not in self.sent_progress_points:
                            message = f"绘图进度: {progress}%，剩余时间: {time_remained}秒"
                            if queue:
                                message += f"队列人数: {queue}"
                            self.sent_progress_points.add(point)
                if status == "success":
                    message = "任务完成"
                    # {"queue_status":{"task_id":"675818777fec874a8e390453","server":"NAS","status":"success","data":{"status":"success","output":["http://kanju.la:59000/comfyui/image/temps/674f2650869e89835a6ef3e4/g4Zxa2-1K_00339_.png"],"type":"image","message":""},"message":""}}
                    self.output = data['queue_status']['data']['output']
                elif status == "failed":
                    message = "任务失败"
                
                # 如果message不为空，则发送消息
                if message:
                    print(message)
                    self.send_message_to_dow(message)
                
                # 如果任务完成，则断开连接
                if status == "success":
                    self.sio.disconnect()

    def submit_task(self, params: dict, options: dict, receiver_name: str, group_name: str, message_interval: int = 25):
        """
        提交任务主入口
        """
        self.receiver_name = receiver_name
        self.group_name = group_name
        self.message_interval = message_interval
        
        # 创建绘图历史
        if not self.client_id:
            self.get_token()
        task_id = self.create_history(options["workflow_id"], self.client_id, params, options)
        if not task_id:
            print("创建绘图历史失败")
            return "failed"
        options["task_id"] = task_id

        try:
            self.init_socket()
            # 使用正确的连接参数
            self.sio.connect(
                self.socket_url,
                transports=['websocket'],
                wait_timeout=10,
                headers={
                    'Accept': '*/*',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Connection': 'Upgrade',
                    'Origin': self.socket_url,
                }
            )
            # 提交自定义工作流
            status = self.submit_custom_workflow(self.sio.sid, params, options)
            if status == "failed":
                print("提交自定义工作流失败")
                return "failed"
            # print(f"task_id:{task_id}, socket_id:{socket_id}, client_id:{self.client_id}, status:{status}")
            
            # 等待消息
            self.sio.wait()
            return self.output

        except Exception as e:
            print(f"连接发生错误: {str(e)}")
            return "failed"
        finally:
            if self.sio.connected:
                self.sio.disconnect()
        
