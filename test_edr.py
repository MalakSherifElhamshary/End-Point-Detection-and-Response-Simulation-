import requests
import json
import time

# API address
BASE_URL = "http://localhost:5000"

def send_event(computer, timestamp, level, source, message):
    """Send a single event to the API"""
    url = f"{BASE_URL}/event"
    payload = {
        "computer": computer,
        "timestamp": timestamp,
        "level": level,
        "source": source,
        "message": message
    }
    try:
        response = requests.post(url, json=payload)
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def reset_computer(computer):
    """Clear the buffer for a specific computer"""
    url = f"{BASE_URL}/reset/{computer}"
    try:
        response = requests.post(url)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def test_single_computer(computer_name, num_events=10):
    """Test sending multiple events to the same computer"""
    print(f"\n🧪 Starting test for computer: {computer_name}")
    print("-" * 50)

    # Basic event data (message can be changed each time)
    base_message = "Starting TrustedInstaller initialization."
    level = "Info"
    source = "CBS"
    timestamp_base = "2026-03-16 10:30:"

    for i in range(1, num_events + 1):
        # Change seconds slightly each event
        timestamp = f"{timestamp_base}{45 + i:02d}"
        message = f"{base_message} (event #{i})"

        print(f"📤 Sending event {i}: {timestamp}")
        result, status = send_event(computer_name, timestamp, level, source, message)

        print(f"📥 Response (HTTP {status}):")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()

        # Wait a little between events
        time.sleep(0.5)

        # If status becomes "normal" or "anomaly", we can stop (optional)
        if result.get("status") in ["normal", "anomaly"]:
            print(f"✅ Sequence completed, status: {result['status']}")
            if result['status'] == 'anomaly':
                print("🚨 Anomaly detected!")
            break

    print("=" * 50)

if __name__ == "__main__":
    print("🔍 EDR Testing Tool")
    print("Choose an option:")
    print("1. Test a single computer (send 10 events)")
    print("2. Reset a computer")
    print("3. Send a single event")

    choice = input("Enter your choice (1/2/3): ").strip()

    if choice == "1":
        computer = input("Enter computer name (default PC-01): ") or "PC-01"
        test_single_computer(computer, 10)
    elif choice == "2":
        computer = input("Enter computer name to reset: ")
        result = reset_computer(computer)
        print("Reset result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif choice == "3":
        computer = input("Computer name: ") or "PC-01"
        timestamp = input("Timestamp (default 2026-03-16 10:30:45): ") or "2026-03-16 10:30:45"
        level = input("Level (Info/Warning/Error): ") or "Info"
        source = input("Source (CBS/CSI/...): ") or "CBS"
        message = input("Message: ") or "Test event"
        result, status = send_event(computer, timestamp, level, source, message)
        print(f"Response (HTTP {status}):")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Invalid choice.")