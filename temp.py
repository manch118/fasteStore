import os
from dotenv import load_dotenv
import requests

load_dotenv()  # Загружает .env
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")

if not all([PAYPAL_CLIENT_ID, PAYPAL_SECRET]):
    print("Ошибка: PAYPAL_CLIENT_ID или PAYPAL_SECRET не заданы в .env")
    exit(1)

if PAYPAL_MODE == "sandbox":
    base_url = "https://api-m.sandbox.paypal.com"
else:
    base_url = "https://api-m.paypal.com"

url = f"{base_url}/v1/oauth2/token"
headers = {"Accept": "application/json", "Accept-Language": "en_US"}
data = {"grant_type": "client_credentials"}
auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)

print(f"Requesting token from: {url}")
response = requests.post(url, headers=headers, data=data, auth=auth, timeout=10)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✅ Токен получен успешно! (PayPal подключение работает)")
    print(f"Token preview: {response.json()['access_token'][:20]}...")
else:
    print(f"❌ Ошибка: {response.text}")