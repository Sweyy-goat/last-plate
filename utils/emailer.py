import os
import requests

RESEND_API_KEY = os.getenv("EMAIL_API_KEY")
FROM_EMAIL = os.getenv("EMAIL_FROM")

def send_email(to, subject, html):
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": FROM_EMAIL,
                "to": [to],
                "subject": subject,
                "html": html
            },
            timeout=10
        )

        if response.status_code >= 400:
            print("❌ EMAIL FAILED:", response.text)
        else:
            print(f"📧 Email sent to {to}")

    except Exception as e:
        print("❌ EMAIL ERROR:", str(e))
