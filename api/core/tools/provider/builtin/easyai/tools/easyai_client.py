import json
import os
import time
from pathlib import Path

import httpx
import socketio
from yarl import URL


class EasyAiClient:
    def __init__(self, base_url: str, socket_url: str, send_msg_api: str, username: str, password: str):
        self.base_url = URL(base_url)
        self.username = username
        self.password = password
        self.socket_url = socket_url
        self.send_msg_api = send_msg_api
        
        self.send_msg_total = None
        self.sent_progress_points = set()
        self.workflow_title = ""
        self.login_status = {}
        self.output = []
        self.refresh_login_status()

    def refresh_login_status(self):
        """
        刷新登录状态
        """
        
        # 使用缓存获取status
        if os.path.exists("easyai.json"):
            local_status = Path("easyai.json").read_text()
            self.login_status = json.loads(local_status)
            
        # 如果token有效，则返回True
        try:
            if self.login_status and self.check_token_valid(self.login_status.get("token")):    
                return True
        except Exception as e:
            print(f"读取本地状态失败: {e}")

        # 缓存token失效，用refresh_token获取status
        if self.login_status and self.login_status.get("refresh_token"):
            print("尝试使用refresh_token获取新status")
            response = httpx.post(
                f"{self.base_url}/auth/refreshTokens",
                json={"refreshToken": self.login_status.get("refresh_token")},
                headers={"Content-Type": "application/json", "Accept": "*/*"},
            )
            response_data = response.json()
            if response_data.get("_id"):
                Path("easyai.json").write_text(json.dumps(response_data))
                self.login_status = response_data
                return True

        # 如果refresh_token失效，则重新登录
        print("refresh_token失效，使用用户名密码重新登录")
        status = self.login_by_username(self.username, self.password)
        if status:
            Path("easyai.json").write_text(json.dumps(status))
            self.login_status = status
            return True
        else:
            return False
            
    def check_token_valid(self, token: str):
        """
        检查token是否有效
        """
        if not token:
            return False
        response = httpx.get(
            f"{self.base_url}/auth-token",
            headers={"Content-Type": "application/json", "Accept": "*/*", "Authorization": f"Bearer {token}"},
        )
        return response.status_code == 200

    def login_by_username(self, username: str, password: str):
        if not username or not password:
            return {}
        response = httpx.post(
            f"{self.base_url}/users/loginByUsername",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        json_data = response.json()
        if json_data.get("status") == "success":
            return json_data.get("data")
        else:
            print(f"登录失败: {json_data.get('message')}")
            return {}

    def get_draw_server(self):
        # 刷新登录状态
        self.refresh_login_status()
        try:
            response = httpx.get(f"{self.base_url}/draw/server", timeout=(2, 10), 
                                 headers={"Authorization": f"Bearer {self.login_status.get('token')}"})
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return None
            else:
                return []
        except Exception as e:
            return []

    def refresh_draw_server(self, server_id: str):
        """
        刷新绘图服务器
        """
        response = httpx.get(
            f"{self.base_url}/draw/server/verify/{server_id}",
            headers={"Authorization": f"Bearer {self.login_status.get('token')}"},
        )
        return response.json()

    def create_history(self, workflow_id: str, user_id: str, params: dict, options: dict, type: str = "image"):
        """
        创建绘图历史
        """
        # created_at 格式 1733758176606
        created_at = int(time.time() * 1000)
        self.refresh_login_status()
        response = httpx.post(
            f"{self.base_url}/draw/history",
            json={"workflow_id": workflow_id, "user_id": user_id, "params": params, "options": options, "type": type,
                  "status": 0, "created_at": created_at},
            headers={"Authorization": f"Bearer {self.login_status.get('token')}"},
        )
        response_data = response.json()
        task_id = response_data.get("_id", "")
        return task_id
        
    def submit_custom_workflow(self, socket_id: str, params: dict, options: dict):
        """
        提交自定义工作流
        """
        self.refresh_login_status()
        response = httpx.post(
            f"{self.base_url}/draw/customWorkflow",
            json={"client_id": self.login_status.get("_id"), "socket_id": socket_id, "params": params, "options": options},
            headers={"Authorization": f"Bearer {self.login_status.get('token')}"}, timeout=(2, 10)
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
        self.refresh_login_status()
        response = httpx.post(
            f"{self.base_url}/file/upload",
            headers={"Authorization": f"Bearer {self.login_status.get('token')}"},
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
                "user_id": self.login_status.get("_id"),
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
                    self.sio.disconnect()
                    return
                    
            if isinstance(data, dict) and 'queue_status' in data:
                message = ""
                queue_status = data['queue_status']
                time_remained = queue_status.get('time_remained', None)
                progress = queue_status.get('progress', 0)
                status = queue_status.get('status')
                queue = queue_status.get('queue')
                if self.group_name:
                    message = f"@{self.group_name} "
                else:
                    message = ""
                if self.send_msg_total is None:
                    # 第一次接收到的time_remained 决定发送几次
                    self.send_msg_total = max(1, int(time_remained / self.message_interval))
                    if self.workflow_title:
                        message += f"🧑‍🎨 正在生成图片... \n 当前模式：{self.workflow_title}\n 预计时间: {time_remained}秒"
                    else:
                        message += f"🧑‍🎨 正在生成图片... \n 预计时间: {time_remained}秒"
                    if queue:
                        message += f"\n🚶‍♂️🚶‍♀️ 队列人数: {queue}"
                else:
                    # 发送n次就均分100/(n+1)段
                    interval = 100 / (self.send_msg_total + 1)
                    progress_points = [int(interval * i) for i in range(1, self.send_msg_total + 1)]
                    for point in progress_points:
                        if progress > point and point not in self.sent_progress_points:
                            message = f"绘图进度: {progress}%，剩余时间: {time_remained}秒"
                            self.sent_progress_points.add(point)
                if status == "success":
                    message += "✅ 任务完成，开始下载图片..."
                    # {"queue_status":{"task_id":"675818777fec874a8e390453","server":"NAS","status":"success","data":{"status":"success","output":["http://kanju.la:59000/comfyui/image/temps/674f2650869e89835a6ef3e4/g4Zxa2-1K_00339_.png"],"type":"image","message":""},"message":""}}
                    self.output = data['queue_status']['data']['output']
                elif status == "failed":
                    message += "🚨 任务失败，请重试"
                
                # 如果message不为空，则发送消息
                if message:
                    self.send_message_to_dow(message)
                
                # 如果任务完成，则断开连接
                if status in {"success", "failed"}:
                    self.sio.disconnect()

    def submit_task(self, params: dict, options: dict, receiver_name: str, group_name: str, message_interval: int = 50):
        """
        提交任务主入口
        """
        self.receiver_name = receiver_name
        self.group_name = group_name
        self.message_interval = message_interval
        
        # 创建绘图历史
        if not self.login_status.get("_id"):
            self.refresh_login_status()
        task_id = self.create_history(options["workflow_id"], self.login_status.get("_id"), params, options)
        if not task_id:
            print("创建绘图历史失败")
            return []
        options["task_id"] = task_id
        self.workflow_title = options["workflow_title"]

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
                return []
            # print(f"task_id:{task_id}, socket_id:{socket_id}, client_id:{self.client_id}, status:{status}")
            
            # 等待消息
            self.sio.wait()
            return self.output

        except Exception as e:
            print(f"连接发生错误: {str(e)}")
            return []
        finally:
            if self.sio.connected:
                self.sio.disconnect()
        
