import threading
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# === CONFIG ===
TARGET_URL = "https://localhost:8443"
REQUEST_COUNT = 20
MAX_WORKERS = 5
TIMEOUT = (5, 3)

SUCCESS_COUNT = 0
FAIL_COUNT = 0
LOCK = threading.Lock()
STOP_EVENT = threading.Event()


def send_request():
    global SUCCESS_COUNT, FAIL_COUNT

    if STOP_EVENT.is_set():
        return

    try:
        with requests.Session() as session:
            response = session.get(
                TARGET_URL,
                timeout=TIMEOUT,
                verify=True
            )

            with LOCK:
                if response.status_code < 400:
                    SUCCESS_COUNT += 1
                else:
                    FAIL_COUNT += 1

            return response.status_code

    except requests.RequestException as error:
        with LOCK:
            FAIL_COUNT += 1

        print(f"[{datetime.now()}] Request failed: {error}")
        return None


def main():
    print(f"Starting controlled HTTP test: {TARGET_URL}")
    print(f"Requests: {REQUEST_COUNT} | Workers: {MAX_WORKERS}")

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(send_request)
                for _ in range(REQUEST_COUNT)
            ]

            for future in as_completed(futures):
                if STOP_EVENT.is_set():
                    break

                try:
                    status = future.result()
                    if status is not None:
                        print(f"HTTP status: {status}")
                except Exception as error:
                    print(f"Unexpected error: {error}")

    except KeyboardInterrupt:
        STOP_EVENT.set()
        print("\nStopping test...")

    finally:
        print("\n=== Test Summary ===")
        print(f"Successful responses: {SUCCESS_COUNT}")
        print(f"Failed responses: {FAIL_COUNT}")


if __name__ == "__main__":
    main()
