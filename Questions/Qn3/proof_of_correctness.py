import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

URL = "http://127.0.0.1:8000/buy_ticket"
TOTAL_REQUESTS = 1000

def buy():
    try:
        resp = requests.post(URL)
        return resp.status_code
    except Exception as e:
        print("Request failed:", e)
        return "error"

def main():
    results = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(buy) for _ in range(TOTAL_REQUESTS)]
        for future in as_completed(futures):
            results.append(future.result())

    code_counts = Counter(results)
    print(f"Result codes: {code_counts}")
    success = code_counts[200]
    sold_out = code_counts[410]
    errors = code_counts["error"]
    print(f"Success (200): {success}")
    print(f"Sold out (410): {sold_out}")
    print(f"Errors: {errors}")

    assert success == 100, f"Should sell exactly 100 items, sold {success}"
    assert sold_out == TOTAL_REQUESTS - 100, f"Should get 410 for rest ({sold_out} got 410)"
    print("Proof passed! No overselling and no underselling.")

if __name__ == "__main__":
    main()