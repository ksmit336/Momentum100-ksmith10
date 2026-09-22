from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import config
def send_alert_email(subject, html):
    if not config.SENDGRID_API_KEY: return False, "No API key"
    message = Mail(config.ALERT_EMAIL_FROM, config.ALERT_EMAIL_TO, subject, html_content=html)
    try:
        SendGridAPIClient(config.SENDGRID_API_KEY).send(message)
        return True, "Sent"
    except Exception as e: return False, str(e)
