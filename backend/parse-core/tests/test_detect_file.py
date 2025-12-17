import requests # type: ignore
import json

# path to code file
FILE_PATH = r"D:\SLIIT\Year 4\RP\PROJECT\PythonCode.py" 

# read the file content
with open(FILE_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# prepare data
payload = {
    "code": code,
    "filename": FILE_PATH.split("\\")[-1]
}

# send request to your running API
response = requests.post("http://127.0.0.1:7070/detect", json=payload)

# print result
print(json.dumps(response.json(), indent=2))
