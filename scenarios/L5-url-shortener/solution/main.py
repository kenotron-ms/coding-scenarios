import os
import random
import signal
import uvicorn
from solution.app import create_app

PORT = int(os.environ["PORT"])
DB_PATH = os.environ["URLSHORT_DB"]
BASE_URL = os.environ.get("URLSHORT_BASE_URL")
SEED = os.environ.get("URLSHORT_SEED")

# Init DB schema
from solution.storage import init_db
init_db(DB_PATH)

# Configure RNG — use seed if provided
rng = random.Random(int(SEED)) if SEED is not None else random.Random()

app = create_app(db_path=DB_PATH, base_url=BASE_URL, rng=rng)

# Log startup info
print(f"Starting URL shortener service on 127.0.0.1:{PORT}")
print(f"Database path: {os.path.abspath(DB_PATH)}")
if BASE_URL:
    print(f"Base URL: {BASE_URL}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_config=None)
