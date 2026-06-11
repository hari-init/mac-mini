import requests
import hashlib
import os
import json

# Add as many sites as you want here
SITES = [
    {"name": "apple_mac_mini", "url": "https://www.apple.com/ca/shop/refurbished/mac/mac-mini"},
    {"name": "another_site", "url": "https://www.apple.com/ca/shop/refurbished/mac"}
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

DATA_FILE = "sites_state.json"

# Load existing states
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        state = json.load(f)
else:
    state = {}

for site in SITES:
    name = site["name"]
    url = site["url"]
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        current_hash = hashlib.md5(response.text.encode()).hexdigest()
        
        old_hash = state.get(name)
        
        if old_hash != current_hash:
            print(f"Change detected on {name}!")
            # Send notification
            requests.post(
                "https://ntfy.sh/apple_mac_mini", # Use your same topic
                data=f"Change detected on {name}: {url}".encode('utf-8')
            )
            # Update state
            state[name] = current_hash
            
    except Exception as e:
        print(f"Error checking {name}: {e}")

# Save all states to one file
with open(DATA_FILE, "w") as f:
    json.dump(state, f)
