import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def generate_otp() -> str:
    """Generates a cryptographically random 6-digit OTP code."""
    # SystemRandom uses os.urandom, which is cryptographically secure.
    return f"{random.SystemRandom().randint(100000, 999999)}"

def send_otp_email(to_email: str, otp: str) -> None:
    """
    Sends an OTP email to the requested address using a clean Zephyr Assist HTML template.
    If SMTP credentials are not configured, prints the OTP to the console as a development fallback.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@zephyrassist.ai")

    subject = "Zephyr Assist - Verification Code"

    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #eefdf7;
                margin: 0;
                padding: 40px 0;
                color: #072018;
            }}
            .container {{
                max-width: 500px;
                margin: 0 auto;
                background: #ffffff;
                border: 1px solid #d9eddf;
                border-radius: 12px;
                padding: 40px;
                text-align: center;
                box-shadow: 0 4px 15px rgba(0, 169, 123, 0.05);
            }}
            .logo {{
                font-size: 24px;
                font-weight: 800;
                color: #00a97b;
                margin-bottom: 24px;
            }}
            .title {{
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
            .description {{
                font-size: 15px;
                color: #3b574e;
                line-height: 1.6;
                margin-bottom: 32px;
            }}
            .otp-box {{
                background-color: rgba(0, 169, 123, 0.1);
                border: 1px solid rgba(0, 169, 123, 0.25);
                border-radius: 8px;
                padding: 24px;
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 6px;
                color: #00a97b;
                margin-bottom: 32px;
            }}
            .footer {{
                font-size: 13px;
                color: #648176;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">Zephyr Assist</div>
            <div class="title">Email Verification</div>
            <div class="description">
                Thank you for signing up for Zephyr Assist. Please use the verification code below to complete your registration.
            </div>
            <div class="otp-box">
                {otp}
            </div>
            <div class="footer">
                This code will expire in 10 minutes. If you did not request this, you can safely ignore this email.
            </div>
        </div>
    </body>
    </html>
    """

    # Development mode fallback
    if not smtp_host or not smtp_user or not smtp_password:
        print("\n" + "=" * 60)
        print("DEVELOPMENT MODE: Email sent (No SMTP config found)")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"OTP CODE: {otp}")
        print("=" * 60 + "\n")
        return

    # Production mode: send email via SMTP
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Zephyr Assist <{smtp_from}>"
    msg["To"] = to_email

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        # In a real app we might raise an HTTPException, but if SMTP fails unexpectedly
        # we can still log it and potentially gracefully handle it in the router.
        raise
