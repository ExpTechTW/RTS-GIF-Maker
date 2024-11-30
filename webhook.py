from PIL import Image
from datetime import datetime
import requests
from io import BytesIO
import time
from time import sleep as slp
import os
from tqdm import tqdm
import shutil
from threading import Thread
import threading
import json
import atexit
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

webhook = ""
name = "ExpTech | 探索科技"
avatar = "https://i.ibb.co/9HwcdXX/Exptech.png"

@dataclass
class GlobalData:
    event: threading.Event = threading.Event()

    def log(self, msg: str, type_: int = 1) -> None:
        if type_ == 1:  # Info
            color_code = "92"  # Bright Green
            type_str = "Info"
        elif type_ == 2:  # Warn
            color_code = "93"  # Bright Yellow
            type_str = "Warn"
        else:  # Error
            color_code = "91"  # Bright Red
            type_str = "Error"

        print(f"\033[{color_code}m[{type_str}][{self.time_to_string()}]: {msg}\033[0m")


    @staticmethod
    def time_to_string() -> str:
        now = time.time()
        return time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(now))  # 調整時區

class SendWebhook:
    def __init__(self):
        self.webhook_url = ""
        self.api_trem_list_url = "https://api-2.exptech.dev/api/v1/trem/list"
        self.folder_path = "./images"
        self.output_gif_folder = "output.gif"
        self.first_5_timestamp_folder = "first_5_timestamp.json"
        self.global_data = GlobalData(
            event=threading.Event()
        )
        self.debug = False #False
        self.first_5_timestamp = self.get_data_from_json()
        self.session = self._create_session()

    def log(self, msg: str, type_: int = 1) -> None:
        self.global_data.log(msg, type_)

    def _create_session(self):
        """建立一個具有重試機制的 session"""
        session = requests.Session()

        # 設定重試策略
        retry_strategy = Retry(
            total=3,  # 總重試次數
            backoff_factor=1,  # 重試間隔 (1秒 -> 2秒 -> 4秒)
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重試的 HTTP 狀態碼
            allowed_methods=["GET"]  # 允許重試的 HTTP 方法
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_response_with_retry(self, max_retries=3, delay=1):
        """使用自定義重試機制獲取回應"""
        for attempt in range(max_retries):
            try:
                result = self.get_response()
                if result is not None:
                    return result

            except Exception as e:
                self.log(f"第 {attempt + 1} 次嘗試失敗: {e}", 3)

            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # 漸進式延遲

        return None

    def get_response(self):
        """獲取 API 回應並處理可能的錯誤"""
        try:
            response = self.session.get(
                self.api_trem_list_url,
                timeout=10,  # 設定超時時間
                verify=True  # SSL 驗證
            )
            response.raise_for_status()  # 檢查 HTTP 狀態碼
            return response.json()

        except requests.exceptions.JSONDecodeError as e:
            self.log(f"JSON 解析錯誤: {e}", 3)
            return None

        except requests.exceptions.ConnectionError as e:
            self.log(f"連線錯誤: {e}", 3)
            return None

        except requests.exceptions.Timeout as e:
            self.log(f"請求超時: {e}", 3)
            return None

        except requests.exceptions.RequestException as e:
            self.log(f"請求錯誤: {e}", 3)
            return None

        finally:
            self.session.close()

    def get_first_5_timestamp(self, got_first):
        return [eq['ID'] for eq in got_first[:5]]

    def get_latest_timestamps(self, earthquake_data):
        timestamps = json.loads(earthquake_data['List'])

        clean_timestamps = [ts.split('-')[0] for ts in timestamps]

        return max(clean_timestamps)

    def get_latest_5_timestamp(self, got_first):
        return [self.get_latest_timestamps(eq) for eq in got_first[:5]]

    def get_data_from_json(self):
        if os.path.exists(self.first_5_timestamp_folder):
            with open(self.first_5_timestamp_folder, "r") as f:
                return json.load(f)
        else:
            return []

    def save_data_to_json(self, data):
        with open(self.first_5_timestamp_folder, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def init(self) -> None:
        if self.global_data.event.is_set():
            self.log("Init Already!", 3)
            return

        if not os.path.exists(self.first_5_timestamp_folder):
            got_response = self.get_response_with_retry()
            if got_response:
                first_5_ids = self.get_first_5_timestamp(got_response)
                with open(self.first_5_timestamp_folder, "w") as f:
                    json.dump(first_5_ids, f, ensure_ascii=False, indent=4)
                self.first_5_timestamp = first_5_ids
            else:
                self.log("無法獲取初始資料，創建空的 JSON 文件", 2)
                with open(self.first_5_timestamp_folder, "w") as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
        else:
            self.first_5_timestamp = self.get_data_from_json()

        self.raw = Image.open("./rts-image.png")

        def cleanup():
            if os.path.exists(self.folder_path):
                shutil.rmtree(self.folder_path)
                os.makedirs(self.folder_path)

        def cleanup2():
            if os.path.exists(self.folder_path):
                shutil.rmtree(self.folder_path)

        atexit.register(cleanup2)

        cleanup()

        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

    def search(self, timestamp, got_response):
        for eq in got_response:
            if round(float(eq['ID']) / 1000) == timestamp or int(float(eq['ID']) / 1000) == timestamp:
                return eq
        return None

    def start(self):
        got_response = self.get_response_with_retry()
        if got_response is None:
            self.log("無法獲取有效的回應，請檢查網路連線或 API 狀態。", 3)
            return
        got_first_5_timestamp = self.get_first_5_timestamp(got_response)
        if self.first_5_timestamp == got_first_5_timestamp:
            return

        self.first_5_timestamp = got_first_5_timestamp
        unix_time = int(self.first_5_timestamp[0])

        got_latest_5_timestamp = self.get_latest_5_timestamp(got_response)
        latest_time = int(got_latest_5_timestamp[0])

        os.system("cls")

        latest_eq = self.search(int(unix_time/1000),got_response)
        if latest_eq:
            if latest_eq['Alarm'] != 1:
                if self.debug == False:
                    self.log(f"最新地震檢知未公開，不製作GIF，時間戳: {unix_time}", 1)
                    return

        self.save_data_to_json(self.first_5_timestamp)
        timestamp_ms_start = unix_time - 10000
        timestamp_ms_end = latest_time + 240000
        self.log(f"處理ID: {unix_time}", 1)
        self.log(f"開始時間: {datetime.fromtimestamp(timestamp_ms_start / 1000).strftime('%Y-%m-%d %H:%M:%S')} ({timestamp_ms_start})", 1)
        self.log(f"結束時間: {datetime.fromtimestamp(timestamp_ms_end / 1000).strftime('%Y-%m-%d %H:%M:%S')} ({timestamp_ms_end})", 1)

        _t = round((timestamp_ms_end - timestamp_ms_start) / 1000)
        missing_count = 0

        with tqdm(total=_t, desc="進度") as pbar:
            for t in range(_t):
                timestamp = timestamp_ms_start + t * 1000

                max_retries = 3
                retry_count = 0
                success = False

                while retry_count < max_retries:
                    try:
                        response = requests.get(f"https://api-1.exptech.dev/api/v1/trem/rts-image/{timestamp}",)

                        if response.status_code == 200:
                            result_image = self.raw.copy()
                            image_data = BytesIO(response.content)
                            variable_img = Image.open(image_data)
                            variable_img = variable_img.convert("RGBA")
                            result_image = Image.alpha_composite(result_image, variable_img)
                            result_image.save(f"./images/{timestamp}.png", format="PNG")
                            success = True
                            break
                        else:
                            self.log(f"請求失敗，狀態碼: {response.status_code}，時間戳: {timestamp}", 2)
                            break
                    except Exception as e:
                        self.log(f"處理時間戳 {timestamp} 時發生錯誤: {e}", 3)
                        retry_count += 1

                if not success:
                    missing_count += 1
                missing_percentage = (missing_count / _t) * 100

                pbar.update(1)
                time.sleep(0.1)

        def prepare_for_gif(im):
            rgba = im.convert('RGBA')
            alpha = rgba.split()[3]
            rgb = rgba.convert('RGB')
            p_img = rgb.convert('P', palette=Image.ADAPTIVE, colors=255)
            p_img.info['transparency'] = 255
            mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
            p_img.paste(255, mask)

            if self.debug:
                self.log(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 已處理 prepare_for_gif", 2)
            return p_img

        def create_gif(output_path , image_folder):
            if os.path.exists(image_folder):
                if self.debug:
                    self.log(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 正在刪除舊的 GIF", 2)
                os.remove(image_folder)
                if self.debug:
                    self.log(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 已刪除舊的 GIF", 2)

            file_list = sorted(os.listdir(output_path))
            images = []

            for filename in file_list:
                img_path = os.path.join(output_path, filename)
                img = Image.open(img_path)
                prepared_img = prepare_for_gif(img)
                images.append(prepared_img)

            try:
                images[0].save(
                    image_folder,
                    save_all=True,
                    append_images=images[1:],
                    duration=200,
                    loop=0,
                    transparency=255,
                    disposal=2
                )

                webhook_url = webhook
                webhook_data = {
                    "username": name,
                    "avatar_url": avatar,
                    "content": (
                            f"{datetime.fromtimestamp(unix_time // 1000).strftime('%Y-%m-%d %H:%M:%S')} (<t:{unix_time // 1000}:R>)\n"
                            f"檢知報告：[點我前往](<https://api-2.exptech.dev/file/trem_info.html?id={unix_time}>)"
                    )
                }

                with open(image_folder, 'rb') as f:
                    files = {
                        'file': (self.output_gif_folder, f)
                    }
                    webhook_response = requests.post(webhook_url, data=webhook_data, files=files)

                if webhook_response.status_code == 200:
                    self.log(f"webhook 發送成功", 1)
                else:
                    self.log(f"webhook 發送失敗，狀態碼: {webhook_response.status_code}", 2)
            except Exception as e:
                self.log(f"Error creating GIF: {e}", 3)
                raise e

            return image_folder

        def verify_image_sequence(image_folder, start_time, end_time, interval=1000):
            missing_timestamps = []
            current = start_time
            while current <= end_time:
                if not os.path.exists(f"{image_folder}/{current}.png"):
                    missing_timestamps.append(current)
                current += interval
            return missing_timestamps

        missing = verify_image_sequence(self.folder_path, timestamp_ms_start, timestamp_ms_end)
        if missing:
            self.log(f"{len(missing)} 個缺失的時間戳 | 丟失率: {missing_percentage:.1f}%", 1)

        create_gif(self.folder_path, self.output_gif_folder)

        for filename in os.listdir(self.folder_path):
            if filename.endswith(".png"):
                file_path = os.path.join(self.folder_path, filename)
                os.remove(file_path)
        self.log(f"ID: {unix_time} 已刪除舊的 PNG", 1)

if __name__ == "__main__":
    Send_Webhook = SendWebhook()
    Send_Webhook.init()

    def run():
        while True:
            Send_Webhook.start()
            slp(1)

    thread = Thread(target=run)
    thread.daemon = True

    try:
        thread.start()
        while True:
            slp(1)
    except KeyboardInterrupt:
        Send_Webhook.log("程式被用戶中斷。正在退出...", 2)
    finally:
        Send_Webhook.log("退出...", 1)