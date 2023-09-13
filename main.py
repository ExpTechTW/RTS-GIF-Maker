from PIL import Image
from datetime import datetime
import requests
from io import BytesIO
import time
import os
from tqdm import tqdm
import shutil

date_start = "2023-09-05 17:30:40"
date_end = "2023-09-05 17:35:00"

datetime_start = datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S")
datetime_end = datetime.strptime(date_end, "%Y-%m-%d %H:%M:%S")

timestamp_ms_start = int(datetime_start.timestamp() * 1000)
timestamp_ms_end = int(datetime_end.timestamp() * 1000)

raw = Image.open("./rts-image.png")

_t=round((timestamp_ms_end - timestamp_ms_start) / 1000)

if os.path.exists("./images"):
    shutil.rmtree("./images")

if not os.path.exists("./images"):
    os.makedirs("./images")

with tqdm(total=_t, desc="進度") as pbar:
    for t in range(_t):
        response = requests.get(
            "https://exptech.com.tw/api/v1/trem/rts-image?time={}".format(timestamp_ms_start + t * 1000))
        if response.status_code == 200:
            result_image = raw.copy()
            image_data = BytesIO(response.content)
            variable_img = Image.open(image_data)
            variable_img = variable_img.convert("RGBA")
            result_image = Image.alpha_composite(result_image, variable_img)
            result_image.save(
                "./images/{}.png".format(timestamp_ms_start + t * 1000))
        else:
            print(
                f"Failed to download image at timestamp {timestamp_ms_start + t * 1000}")
        time.sleep(0.5)
        pbar.update(1)

file_list = os.listdir("./images")
images = []

for filename in file_list:
    img = Image.open("./images/{}".format(filename))
    images.append(img)

images[0].save("output.gif", save_all=True,
               append_images=images[1:], duration=100, loop=0, disposal=2)
