import logging
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from core.config import settings

logger = logging.getLogger("cipher.email")

def send_verification_email(to_email: str, username: str, code: str, token: str) -> bool:
    """
    Sends an email verification code and direct verification link to the user using Brevo HTTP API.
    Falls back gracefully to logging to console if BREVO_API_KEY is not configured or placeholder.
    """
    verify_link = f"{settings.FRONTEND_URL}/verify?token={token}&email={to_email}"

    # Check if Brevo is configured with a real API key
    brevo_api_key = settings.BREVO_API_KEY
    is_placeholder = (
        not brevo_api_key
        or brevo_api_key.startswith("your_")
        or "placeholder" in brevo_api_key.lower()
    )
    brevo_configured = bool(brevo_api_key and not is_placeholder)

    # Print prominent developer notice in logs/console
    dev_notice = f"""
======================================================================
[CIPHER AUTH VERIFICATION]
Recipient: {to_email} ({username})
6-Digit Verification Code: {code}
Direct Verification Link:  {verify_link}
Status: {'Attempting Brevo API Delivery...' if brevo_configured else 'DEV MODE (No BREVO_API_KEY configured)'}
======================================================================
"""
    print(dev_notice)
    logger.info(f"Verification code generated for {to_email}: {code}")

    if not brevo_configured:
        logger.info("BREVO_API_KEY not set in .env. Falling back to console delivery.")
        return True

    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = brevo_api_key
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        from_email_raw = settings.BREVO_FROM_EMAIL or "noreply@cipher.ai"
        if "<" in from_email_raw and ">" in from_email_raw:
            sender_email = from_email_raw[from_email_raw.find("<") + 1 : from_email_raw.find(">")].strip()
        else:
            sender_email = from_email_raw.strip()

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

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email, "name": username}],
            sender={"email": sender_email, "name": "CIPHER"},
            subject=f"Verify your CIPHER account - Code: {code}",
            html_content=html_content,
            text_content=plain_text
        )

        response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Verification email successfully sent to {to_email} via Brevo. Response: {response}")
        return True

    except ApiException as e:
        logger.error(f"Failed to send email via Brevo to {to_email} (ApiException {e.status}): {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while sending email via Brevo to {to_email}: {e}")
        return False
