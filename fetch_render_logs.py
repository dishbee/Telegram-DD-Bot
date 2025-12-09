"""
Fetch Render logs using API
Usage: python fetch_render_logs.py [hours]
Example: python fetch_render_logs.py 24  # Fetch last 24 hours
         python fetch_render_logs.py     # Fetch last 6 hours (default)
"""

import sys
import requests
from datetime import datetime, timedelta

# Configuration
API_KEY = "rnd_7AT2OkbYomjMCx6xFshxJDIXsW8z"
SERVICE_ID = "srv-ctbnhd08fa8c739kiqr0"
BASE_URL = "https://api.render.com/v1"

def fetch_logs(hours=6):
    """Fetch logs for the specified number of hours"""
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    # Convert to ISO format (Render API expects UTC timestamps)
    start_iso = start_time.isoformat() + "Z"
    end_iso = end_time.isoformat() + "Z"
    
    print(f"Fetching logs from {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Time range: {hours} hours")
    print("-" * 80)
    
    all_logs = []
    page = 1
    has_more = True
    current_start = start_iso
    current_end = end_iso
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    
    while has_more:
        # Build URL with query parameters
        url = f"{BASE_URL}/logs"
        params = {
            "resourceId": SERVICE_ID,
            "startTime": current_start,
            "endTime": current_end,
            "limit": 1000  # Max per page
        }
        
        print(f"Fetching page {page}...", end=" ", flush=True)
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logs = data.get("logs", [])
            has_more = data.get("hasMore", False)
            
            print(f"Got {len(logs)} log entries")
            
            # Add logs to collection
            all_logs.extend(logs)
            
            # If there are more logs, update time range for next page
            if has_more and "nextStartTime" in data and "nextEndTime" in data:
                current_start = data["nextStartTime"]
                current_end = data["nextEndTime"]
                page += 1
            else:
                has_more = False
                
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error fetching logs: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            sys.exit(1)
    
    print("-" * 80)
    print(f"✅ Total log entries fetched: {len(all_logs)}")
    
    return all_logs

def save_logs(logs, filename="render_logs.txt"):
    """Save logs to file"""
    
    with open(filename, "w", encoding="utf-8") as f:
        # Write header
        f.write("=" * 80 + "\n")
        f.write(f"Render Logs - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(f"Service ID: {SERVICE_ID}\n")
        f.write(f"Total entries: {len(logs)}\n")
        f.write("=" * 80 + "\n\n")
        
        # Write logs (they come in reverse chronological order from API)
        for log in logs:
            timestamp = log.get("timestamp", "")
            message = log.get("message", "")
            
            # Format: [timestamp] message
            if timestamp:
                # Parse and format timestamp for readability
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    formatted_time = timestamp
                
                f.write(f"[{formatted_time}] {message}\n")
            else:
                f.write(f"{message}\n")
    
    print(f"✅ Logs saved to: {filename}")

def main():
    # Parse command line arguments
    hours = 6  # Default: last 6 hours
    
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
            if hours < 1:
                print("❌ Hours must be at least 1")
                sys.exit(1)
            if hours > 168:  # 7 days
                print("⚠️  Warning: Fetching more than 7 days (168 hours) may take a long time")
        except ValueError:
            print(f"❌ Invalid hours value: {sys.argv[1]}")
            print("Usage: python fetch_render_logs.py [hours]")
            sys.exit(1)
    
    # Fetch and save logs
    logs = fetch_logs(hours)
    save_logs(logs, "render_logs.txt")
    
    print("\n📋 You can now paste the contents of render_logs.txt to share with AI assistant")

if __name__ == "__main__":
    main()
