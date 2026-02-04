import os

from dotenv import load_dotenv

from app import create_app
from config import get_config

load_dotenv()

app = create_app(get_config())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
