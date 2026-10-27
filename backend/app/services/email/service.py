import asyncio
import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.client = None
        if settings.sendgrid_api_key:
            self.client = SendGridAPIClient(settings.sendgrid_api_key)

    async def send_html(
        self,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        html_content: str,
    ) -> bool:
        if not self.client:
            logger.warning("SendGrid not configured, skipping email to %s", to_email)
            return False

        try:
            message = Mail(
                from_email=Email(settings.from_email, "OpportunityRadar"),
                to_emails=To(to_email, to_name),
                subject=subject,
                html_content=Content("text/html", html_content),
            )
            response = await asyncio.to_thread(self.client.send, message)
            logger.info(f"Email sent to {to_email}: status {response.status_code}")
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    async def send_digest(
        self,
        to_email: str,
        to_name: Optional[str],
        opportunities: list[dict],
        profile_name: str,
        unsubscribe_token: str,
    ) -> bool:
        from app.services.email.templates import DigestEmailTemplate
        html = DigestEmailTemplate.render(
            opportunities=opportunities,
            profile_name=profile_name,
            frontend_url=settings.frontend_url,
            unsubscribe_token=unsubscribe_token,
        )
        return await self.send_html(
            to_email=to_email,
            to_name=to_name,
            subject=f"🎯 Your Weekly Internship Matches — OpportunityRadar",
            html_content=html,
        )
