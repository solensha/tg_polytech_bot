import subprocess
import json
import os

base_dir = os.path.dirname(os.path.abspath(__file__))  # папка со скриптом
sessions_path = os.path.join(base_dir, "sessions.json")
parser_path = os.path.join(base_dir, "parser.py")

with open(sessions_path, "r") as file:
    sessions = json.load(file)

for session in sessions:
    api_id = session["api_id"]
    api_hash = session["api_hash"]
    session_value = session["session_value"]

    command = [
        "pm2", "start", parser_path,
        "--interpreter", "python3",
        "--name", str(api_id),
        "--",
        str(api_id),
        str(api_hash),
        str(session_value)
    ]
    subprocess.run(command, shell=False)
