from flask import Flask
import os
import socket

app = Flask(__name__)

@app.route("/")
def home():
    app_name = os.getenv("APP_NAME", socket.gethostname())
    return f"Hello from {app_name}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)