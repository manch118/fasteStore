# Template-ecommerce

## Quick start

Run:

```
uvicorn main:app --reload
```

## Environment (.env)

Create `Template-ecommerce/.env` with the following keys (fill your values):

```
openssl rand -base64 64
python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=change-me
BASE_URL=http://127.0.0.1:8000

# Admin bootstrap (first-run admin password)
ADMIN_PASSWORD=admin123

# SMTP (required for contact and reset-password emails)
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=587
SMTP_USERNAME=your_login@yandex.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=your_login@yandex.com
SMTP_USE_TLS=true

# PayPal (optional for local dev; needed for payments)
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=
PAYPAL_SECRET=

# GetResponse (optional; needed for subscribe/newsletter)
GETRESPONSE_API_KEY=
GETRESPONSE_LIST_ID=
GETRESPONSE_FROM_FIELD_ID=
```
