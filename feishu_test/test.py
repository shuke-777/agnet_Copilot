import requests
import json


WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/cd5994e6-a4d5-467d-a482-385802f24069"


def send_message(text):
    data = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }

    response = requests.post(
        WEBHOOK_URL,
        headers={
            "Content-Type": "application/json"
        },
        data=json.dumps(data)
    )

    print(response.text)


i = 0
for i in range(3):
    send_message(f"text = '这个是数字'{i}")
    i += 1

