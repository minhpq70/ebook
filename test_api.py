import requests
import json

url = "http://127.0.0.1:8080/api/v1/rag/query/stream"
payload = {
    "book_id": "e4f8d3ad-8986-4a7c-a435-11ef4ffc48cf",
    "query": "tóm tắt sách này",
    "task_type": "qa"
}

with requests.post(url, json=payload, stream=True) as r:
    print("Status:", r.status_code)
    for line in r.iter_lines():
        if line:
            print(line.decode('utf-8'))
