import requests
import hashlib
import os

URL = "https://www.apple.com/ca/shop/refurbished/mac/mac-mini"  # The site to monitor
FILE_NAME = "data.txt"

# 1. Fetch the site content
response = requests.get(URL)
content_hash = hashlib.md5(response.text.encode()).hexdigest()

# 2. Compare with previous hash
if os.path.exists(FILE_NAME):
    with open(FILE_NAME, "r") as f:
        old_hash = f.read().strip()
else:
    old_hash = ""

if content_hash != old_hash:
    print("Change detected!")
    # Send your notification here (Telegram/Discord/ntfy.sh)
    requests.post(
        "https://ntfy.sh/apple_mac_mini",
        data="The website you are monitoring has changed!".encode(encoding='utf-8')
    )
    
    # 3. Update the hash file
    with open(FILE_NAME, "w") as f:
        f.write(content_hash)
else:
    print("No change.")
