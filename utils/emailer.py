# utils/emailer.py
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_EMAIL = os.getenv("SMTP_EMAIL")        # your gmail
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # app password


def send_email(to, subject, html):
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
        smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
        smtp.send_message(msg)


def send_email_async(*args, **kwargs):
    t = threading.Thread(target=send_email, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()
