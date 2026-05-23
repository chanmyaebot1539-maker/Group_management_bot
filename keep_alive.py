import os
import threading
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is alive!", 200


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
