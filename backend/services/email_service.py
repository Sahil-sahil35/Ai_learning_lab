"""
Email service for user verification and notifications.
Handles email template generation and SMTP delivery.
"""

import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
from jinja2 import Template

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails with templates and verification tokens."""

    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
        self.base_url = os.getenv('BASE_URL', 'http://localhost:3000')
        self.use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

    def _create_verification_token(self, user_id: str) -> tuple[str, datetime]:
        """Create a secure verification token with expiry."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)  # 24 hour expiry
        return token, expires_at

    def _send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"AI Learning Lab <{self.from_email}>"
            msg['To'] = to_email

            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)

            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)

                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_verification_email(self, user_email: str, user_name: str, verification_token: str) -> bool:
        """Send email verification message."""
        verification_url = f"{self.base_url}/verify-email?token={verification_token}"

        # Email templates
        subject = "Verify Your AI Learning Lab Account"

        text_content = f"""
Hello {user_name},

Welcome to AI Learning Lab! Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.

Best regards,
The AI Learning Lab Team
        """.strip()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify Your AI Learning Lab Account</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI Learning Lab</h1>
        <p>Welcome to the Future of AI Education!</p>
    </div>

    <div class="content">
        <h2>Hello {user_name}!</h2>

        <p>Thank you for joining AI Learning Lab! To get started with your AI learning journey, please verify your email address by clicking the button below:</p>

        <div style="text-align: center;">
            <a href="{verification_url}" class="button">Verify Email Address</a>
        </div>

        <p><strong>Note:</strong> This verification link will expire in 24 hours for security reasons.</p>

        <p>If you didn't create an account with AI Learning Lab, you can safely ignore this email. Your account will not be activated without verification.</p>

        <p>If the button above doesn't work, you can copy and paste this link into your browser:</p>
        <p style="word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 5px;">
            {verification_url}
        </p>
    </div>

    <div class="footer">
        <p>Best regards,<br>The AI Learning Lab Team</p>
        <p><small>This is an automated message. Please do not reply to this email.</small></p>
    </div>
</body>
</html>
        """.strip()

        return self._send_email(user_email, subject, html_content, text_content)

    def send_password_reset_email(self, user_email: str, user_name: str, reset_token: str) -> bool:
        """Send password reset email."""
        reset_url = f"{self.base_url}/reset-password?token={reset_token}"

        subject = "Reset Your AI Learning Lab Password"

        text_content = f"""
Hello {user_name},

You requested to reset your password for AI Learning Lab. Click the link below to reset your password:

{reset_url}

This link will expire in 1 hour for security reasons.

If you didn't request a password reset, you can safely ignore this email.

Best regards,
The AI Learning Lab Team
        """.strip()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your AI Learning Lab Password</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            background: #dc3545;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .alert {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔐 Password Reset</h1>
        <p>AI Learning Lab Security</p>
    </div>

    <div class="content">
        <h2>Hello {user_name}!</h2>

        <div class="alert">
            <strong>Security Alert:</strong> You requested to reset your password. If this wasn't you, please ignore this email.
        </div>

        <p>To reset your password, click the button below:</p>

        <div style="text-align: center;">
            <a href="{reset_url}" class="button">Reset Password</a>
        </div>

        <p><strong>Important:</strong> This reset link will expire in 1 hour for security reasons.</p>

        <p>If the button above doesn't work, you can copy and paste this link into your browser:</p>
        <p style="word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 5px;">
            {reset_url}
        </p>

        <p>If you didn't request a password reset, please contact our support team immediately.</p>
    </div>

    <div class="footer">
        <p>Best regards,<br>The AI Learning Lab Team</p>
        <p><small>This is an automated message. Please do not reply to this email.</small></p>
    </div>
</body>
</html>
        """.strip()

        return self._send_email(user_email, subject, html_content, text_content)

    def send_welcome_email(self, user_email: str, user_name: str) -> bool:
        """Send welcome email after successful verification."""
        subject = "Welcome to AI Learning Lab!"

        text_content = f"""
Hello {user_name},

Welcome to AI Learning Lab! Your account has been successfully verified and you're ready to start your AI learning journey.

What you can do now:
- Explore built-in ML models
- Upload and clean your own datasets
- Create custom AI models
- Visualize training in real-time

Get started at: {self.base_url}

If you have any questions, don't hesitate to reach out to our support team.

Best regards,
The AI Learning Lab Team
        """.strip()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to AI Learning Lab!</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .features {{
            background: white;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .feature {{
            margin: 10px 0;
            padding-left: 25px;
            position: relative;
        }}
        .feature:before {{
            content: "✨";
            position: absolute;
            left: 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Welcome!</h1>
        <p>Your AI Learning Journey Begins Now</p>
    </div>

    <div class="content">
        <h2>Hello {user_name}!</h2>

        <p>Congratulations! Your account has been successfully verified and you're ready to start exploring the fascinating world of AI and Machine Learning.</p>

        <div class="features">
            <h3>What You Can Do Now:</h3>
            <div class="feature">Explore built-in ML models like Random Forest and Neural Networks</div>
            <div class="feature">Upload and clean your own datasets with our intelligent tools</div>
            <div class="feature">Create custom AI models from scratch in our secure sandbox</div>
            <div class="feature">Visualize model training in real-time with interactive graphs</div>
            <div class="feature">Download trained models and comprehensive reports</div>
        </div>

        <div style="text-align: center;">
            <a href="{self.base_url}" class="button">Start Learning Now!</a>
        </div>

        <p>We're excited to be part of your AI learning journey. If you have any questions or need help getting started, our support team is here to help!</p>
    </div>

    <div class="footer">
        <p>Happy Learning!<br>The AI Learning Lab Team</p>
        <p><small>This is an automated message. Please do not reply to this email.</small></p>
    </div>
</body>
</html>
        """.strip()

        return self._send_email(user_email, subject, html_content, text_content)

# Initialize email service
email_service = EmailService()