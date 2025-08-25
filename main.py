import niquests as requests
import base64
import datetime
from urllib.parse import urlparse

def ts_to_datetime(ts):
    return datetime.datetime.fromtimestamp(int(ts))

# Use demo token directly for testing
setup_token = "aHR0cHM6Ly9iZXRhLWJyaWRnZS5zaW1wbGVmaW4ub3JnL3NpbXBsZWZpbi9jbGFpbS9ERU1PLXYyLTMyNDZGOTkxNEQ1MkYxNDkxNTY3"

# Step 1: Decode the Setup Token to get the Claim URL
claim_url = base64.b64decode(setup_token).decode('utf-8')
print("Claim URL:", claim_url)

# Step 2: POST to Claim URL (must be done once, and only once)
response = requests.post(claim_url, headers={"Content-Length": "0"})
print("Claim Response Status Code:", response.status_code)
print("Claim Response Text:", response.text)

if response.status_code != 200:
    print("Failed to claim token.")
    exit(1)

# Step 3: The response is the Access URL
access_url = response.text
parsed = urlparse(access_url)

# Extract credentials
username = parsed.username
password = parsed.password
url = f"{parsed.scheme}://{parsed.hostname}/accounts"
print("Accounts URL:", url)
print(username, password)

# Step 4: GET accounts with Basic Auth
response = requests.get(url, auth=(username, password))
print("Accounts Response Status Code:", response.status_code)
print("Raw Response Text:\n", response.text)

try:
    data = response.json()
except Exception as e:
    print("JSON decode error:", e)
    exit(1)

# Step 5: Display the data
print("\n" + "="*60)
for account in data['accounts']:
    balance_date = ts_to_datetime(account['balance-date'])
    print(f"\n{balance_date} {account['balance']:>8} {account['name']}")
    print("-" * 60)
    for transaction in account['transactions']:
        posted_date = ts_to_datetime(transaction['posted'])
        print(f"{posted_date} {transaction['amount']:>8} {transaction['description']}")