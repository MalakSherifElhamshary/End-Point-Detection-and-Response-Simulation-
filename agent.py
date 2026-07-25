import win32evtlog
import win32evtlogutil
import time
import requests
from datetime import datetime
import socket
import os

# Configuration
SERVER_URL = "http://your-server-ip:5000/event"  # Change to your Flask server
COMPUTER_NAME = socket.gethostname()
LAST_TIME_FILE = "last_event_time.txt"

# Map Windows event types to our level strings
EVENT_LEVEL_MAP = {
    win32evtlog.EVENTLOG_SUCCESS: "Success",
    win32evtlog.EVENTLOG_ERROR_TYPE: "Error",
    win32evtlog.EVENTLOG_WARNING_TYPE: "Warning",
    win32evtlog.EVENTLOG_INFORMATION_TYPE: "Info",
    win32evtlog.EVENTLOG_AUDIT_SUCCESS: "AuditSuccess",
    win32evtlog.EVENTLOG_AUDIT_FAILURE: "AuditFailure",
}

def get_last_event_time():
    """Return last processed event timestamp as string or None"""
    if os.path.exists(LAST_TIME_FILE):
        with open(LAST_TIME_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_last_event_time(timestamp):
    """Save last processed event timestamp"""
    with open(LAST_TIME_FILE, 'w') as f:
        f.write(timestamp)

def get_event_level(event_type):
    """Convert Windows event type to our level string"""
    return EVENT_LEVEL_MAP.get(event_type, "Info")

def fetch_and_send_events(log_type="System"):
    """Read events from a specific log and send them to the server"""
    hand = win32evtlog.OpenEventLog(None, log_type)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    events = win32evtlog.ReadEventLog(hand, flags, 0)
    
    last_time = get_last_event_time()
    new_events = []
    newest_time = None
    
    for event in events:
        # Event time as datetime object
        event_time = event.TimeGenerated
        time_str = event_time.strftime('%Y%m%d%H%M%S')
        
        # Skip if older than last processed
        if last_time and time_str <= last_time:
            continue
        
        # Format timestamp for API
        timestamp = event_time.strftime('%Y-%m-%d %H:%M:%S')
        level = get_event_level(event.EventType)
        source = event.SourceName
        
        # Get message safely
        try:
            message = win32evtlogutil.SafeFormatMessage(event, hand)
        except:
            message = "Unable to format message"
        
        new_events.append({
            "computer": COMPUTER_NAME,
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "message": message
        })
        
        # Track the newest event time
        if newest_time is None or time_str > newest_time:
            newest_time = time_str
        
        # Send in batches of 10 to avoid large payloads
        if len(new_events) >= 10:
            send_events_batch(new_events)
            new_events = []
    
    # Send remaining events
    if new_events:
        send_events_batch(new_events)
    
    # Update last processed time
    if newest_time:
        save_last_event_time(newest_time)

def send_events_batch(events):
    """Send a batch of events to the Flask API"""
    for event in events:
        try:
            response = requests.post(SERVER_URL, json=event, timeout=5)
            if response.status_code == 202:
                print(f"⚠️ ANOMALY on {event['computer']} at {event['timestamp']}: {event['message'][:80]}")
            elif response.status_code == 200:
                print(f"✓ Normal: {event['timestamp']} - {event['source']}")
            else:
                print(f"❌ Server error {response.status_code}: {response.text[:100]}")
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}. Event will be retried later.")
            # Optionally: save failed events to disk for retry

def main():
    print(f"🚀 Starting Windows Event Agent on {COMPUTER_NAME}")
    log_types = ["System", "Application"]  # Add "Security" if running as admin
    
    while True:
        for log_type in log_types:
            try:
                fetch_and_send_events(log_type)
            except Exception as e:
                print(f"Error processing {log_type} log: {e}")
        time.sleep(5)  # Wait 5 seconds before next scan

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Agent stopped by user.")