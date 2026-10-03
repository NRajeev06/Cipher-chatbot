import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings

logger = logging.getLogger("cipher.email")

def send_verification_email(to_email: str, username: str, code: str, token: str) -> bool:
    """
    Sends an email verification code and direct verification link to the user.
    Falls back gracefully to logging to console if SMTP credentials are not configured.
    """
    verify_link = f"{settings.FRONTEND_URL}/verify?token={token}&email={to_email}"

    # Check if SMTP is configured
    smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)

    # Print prominent developer notice in logs/console
    dev_notice = f"""
======================================================================
[CIPHER AUTH VERIFICATION]
Recipient: {to_email} ({username})
6-Digit Verification Code: {code}
Direct Verification Link:  {verify_link}
Status: {'Attempting SMTP Delivery...' if smtp_configured else 'DEV MODE (No SMTP credentials configured)'}
======================================================================
"""
    print(dev_notice)
    logger.info(f"Verification code generated for {to_email}: {code}")

    if not smtp_configured:
        logger.info("SMTP_USER/SMTP_PASSWORD not set in .env. Falling back to console delivery.")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Verify your CIPHER account - Code: {code}"
        msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
        msg["To"] = to_email

        # Plain text alternative
        plain_text = f"""Hello {username},

Thank you for registering with CIPHER.

Your 6-digit verification code is: {code}

Or verify directly by clicking this link:
{verify_link}

This code will expire in 24 hours. If you did not create a CIPHER account, you can safely ignore this email.

— The CIPHER AI Team
"""

        # Sleek dark HTML template
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #0d0f17;
      color: #f1f3f9;
      margin: 0;
      padding: 30px 15px;
    }}
    .container {{
      max-width: 520px;
      margin: 0 auto;
      background-color: #161925;
      border: 1px solid #282d3e;
      border-radius: 14px;
      padding: 36px 28px;
    }}
    .header {{
      text-align: center;
      margin-bottom: 24px;
    }}
    .brand {{
      font-size: 20px;
      font-weight: 700;
      color: #818cf8;
      letter-spacing: 1px;
    }}
    .title {{
      font-size: 22px;
      font-weight: 600;
      color: #ffffff;
      margin: 14px 0 6px 0;
    }}
    .desc {{
      font-size: 14px;
      color: #94a3b8;
      line-height: 1.5;
    }}
    .code-box {{
      margin: 28px 0;
      background-color: #0f111a;
      border: 1px solid #31374a;
      border-radius: 10px;
      padding: 20px;
      text-align: center;
    }}
    .code-text {{
      font-family: monospace;
      font-size: 34px;
      font-weight: 700;
      letter-spacing: 8px;
      color: #a5b4fc;
    }}
    .code-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #64748b;
      margin-top: 6px;
    }}
    .btn-container {{
      text-align: center;
      margin: 24px 0;
    }}
    .btn {{
      display: inline-block;
      background-color: #6366f1;
      color: #ffffff !important;
      text-decoration: none;
      padding: 12px 28px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 14px;
    }}
    .footer {{
      margin-top: 30px;
      border-top: 1px solid #232734;
      padding-top: 16px;
      font-size: 12px;
      color: #64748b;
      text-align: center;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">✦ CIPHER AI</div>
      <div class="title">Verify your email address</div>
      <div class="desc">Hello {username}, enter this 6-digit code on the verification screen to activate your account:</div>
    </div>

    <div class="code-box">
      <div class="code-text">{code}</div>
      <div class="code-label">Verification Code</div>
    </div>

    <div class="btn-container">
      <a href="{verify_link}" class="btn">Verify Account Directly</a>
    </div>

    <div class="footer">
      This code is valid for 24 hours.<br>
      If you did not request this verification, you can safely ignore this email.
    </div>
  </div>
</body>
</html>
"""
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Verification email successfully sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
        # Return True anyway so signup doesn't crash if SMTP provider has temporary glitch
        return False
