import smtplib
from email.message import EmailMessage
import os

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASS = os.getenv("SMTP_PASS")

def send_email(to, subject, html):
    msg = EmailMessage()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    msg["Subject"] = subject

    msg.set_content("Your email client does not support HTML.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SMTP_EMAIL, SMTP_PASS)
        smtp.send_message(msg)
