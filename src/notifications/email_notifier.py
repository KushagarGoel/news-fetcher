"""Email notification system with SMTP and HTML templates."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.models import Article, Category, EmailConfig, Priority, SMTPConfig

# Load .env file if it exists
load_dotenv()

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send email notifications for news articles."""

    def __init__(self, config_file: str = "config/email.yaml"):
        """Initialize the email notifier.

        Args:
            config_file: Path to email configuration YAML
 """
        self.config: dict[str, Any] = {}
        self.smtp_config: SMTPConfig | None = None
        self._load_config(config_file)

    def _load_config(self, config_file: str) -> None:
        """Load email configuration from YAML and .env."""
        base_path = Path(__file__).parent.parent.parent

        try:
            with open(base_path / config_file, "r") as f:
                data = yaml.safe_load(f)
                self.config = data

                # Parse SMTP config with environment variable substitution
                smtp_data = data.get("smtp", {})
                self.smtp_config = SMTPConfig(
                    host=self._get_config_value(smtp_data, "host", "SMTP_HOST", "smtp.gmail.com"),
                    port=int(self._get_config_value(smtp_data, "port", "SMTP_PORT", "587")),
                    username=self._get_config_value(smtp_data, "username", "SMTP_USERNAME", ""),
                    password=self._get_config_value(smtp_data, "password", "SMTP_PASSWORD", ""),
                    use_tls=self._get_config_value(smtp_data, "use_tls", "SMTP_USE_TLS", "true").lower() == "true"
                )

            logger.info("Loaded email configuration")
        except Exception as e:
            logger.error(f"Failed to load email config: {e}")
            self.config = {}

    def _get_config_value(self, smtp_data: dict, yaml_key: str, env_key: str, default: str) -> str:
        """Get config value from .env first, then YAML, then default.

        Args:
            smtp_data: SMTP data from YAML
            yaml_key: Key in YAML config
            env_key: Environment variable name
            default: Default value if not found

        Returns:
            Config value
        """
        # Priority: env var > YAML > default
        env_value = os.environ.get(env_key)
        if env_value:
            return env_value

        yaml_value = smtp_data.get(yaml_key)
        if yaml_value and not str(yaml_value).startswith("${"):
            return str(yaml_value)

        # Handle ${VAR} syntax in YAML
        if yaml_value and str(yaml_value).startswith("${"):
            var_name = str(yaml_value)[2:-1]  # Remove ${ and }
            return os.environ.get(var_name, default)

        return default

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Create and configure SMTP connection.

        Returns:
            Configured SMTP connection

        Raises:
            ConnectionError: If SMTP connection fails
        """
        if not self.smtp_config:
            raise ValueError("SMTP configuration not loaded")

        try:
            smtp = smtplib.SMTP(self.smtp_config.host, self.smtp_config.port)
            smtp.starttls() if self.smtp_config.use_tls else None
            smtp.login(self.smtp_config.username, self.smtp_config.password)
            return smtp
        except Exception as e:
            logger.error(f"SMTP connection failed: {e}")
            raise ConnectionError(f"Failed to connect to SMTP: {e}") from e

    def _create_html_email(
        self,
        subject: str,
        articles: list[Article],
        is_digest: bool = False
    ) -> MIMEMultipart:
        """Create HTML email with article cards.

        Args:
            subject: Email subject
            articles: List of articles to include
            is_digest: Whether this is a digest email

        Returns:
            Multipart email message
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Credit news alert: {subject}"
        from_addr = self.smtp_config.username if self.smtp_config else "news-aggregator@localhost"
        msg["From"] = f"CreditNews <{from_addr}>"

        # Generate HTML body
        html_body = self._generate_html_body(articles, is_digest)
        text_body = self._generate_text_body(articles, is_digest)

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        return msg

    def _generate_html_body(
        self,
        articles: list[Article],
        is_digest: bool = False
    ) -> str:
        """Generate HTML email body.

        Args:
            articles: List of articles
            is_digest: Whether this is a digest

        Returns:
            HTML string
        """
        article_cards = []
        for article in articles:
            card = self._create_article_card_html(article)
            article_cards.append(card)

        priority_badge = ""
        if articles and articles[0].email_routing.priority == Priority.CRITICAL:
            priority_badge = '<div style="background-color: #dc2626; color: white; padding: 10px; text-align: center; margin-bottom: 20px;"><strong>CRITICAL PRIORITY</strong></div>'
        elif articles and articles[0].email_routing.priority == Priority.HIGH:
            priority_badge = '<div style="background-color: #f59e0b; color: white; padding: 10px; text-align: center; margin-bottom: 20px;"><strong>HIGH PRIORITY</strong></div>'

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background-color: #1e40af;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 0 0 8px 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .article-card {{
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 16px;
                    margin-bottom: 16px;
                    background-color: #fafafa;
                }}
                .article-title {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #1e40af;
                    margin-bottom: 8px;
                    text-decoration: none;
                }}
                .article-meta {{
                    font-size: 12px;
                    color: #6b7280;
                    margin-bottom: 8px;
                }}
                .article-snippet {{
                    color: #4b5563;
                    margin-bottom: 12px;
                }}
                .tags {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 6px;
                    margin-top: 8px;
                }}
                .tag {{
                    background-color: #dbeafe;
                    color: #1e40af;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                .entity {{
                    background-color: #fef3c7;
                    color: #92400e;
                }}
                .priority-critical {{
                    background-color: #fecaca;
                    color: #991b1b;
                }}
                .priority-high {{
                    background-color: #fed7aa;
                    color: #9a3412;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    font-size: 12px;
                    color: #6b7280;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{"News Digest" if is_digest else "News Alert"}</h1>
                <p>{len(articles)} article(s) found</p>
            </div>
            {priority_badge}
            <div class="content">
                {''.join(article_cards)}
            </div>
            <div class="footer">
                <p>Generated by News Aggregator on {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
            </div>
        </body>
        </html>
        """
        return html

    def _create_article_card_html(self, article: Article) -> str:
        """Create HTML card for a single article.

        Args:
            article: Article to render

        Returns:
            HTML string for article card
        """
        # Tags
        tags_html = []
        for tag in article.tags[:5]:  # Limit to 5 tags
            tags_html.append(f'<span class="tag">{tag}</span>')

        # Entities
        for entity in article.competitor_mentions[:2]:
            tags_html.append(f'<span class="tag entity">{entity}</span>')

        for client in article.client_mentions[:2]:
            client_name = client.get("name", "")
            client_type = client.get("type", "")
            if client_type:
                tags_html.append(f'<span class="tag entity">{client_name} ({client_type})</span>')
            else:
                tags_html.append(f'<span class="tag entity">{client_name}</span>')

        # Priority tag
        if article.email_routing.priority == Priority.CRITICAL:
            tags_html.append('<span class="tag priority-critical">CRITICAL</span>')
        elif article.email_routing.priority == Priority.HIGH:
            tags_html.append('<span class="tag priority-high">HIGH</span>')

        # Source and date
        source_info = article.source
        if article.published_at:
            source_info += f" | {article.published_at.strftime('%Y-%m-%d')}"

        # Content snippet
        snippet = article.summary or article.content[:200]
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."

        return f"""
        <div class="article-card">
            <a href="{article.url}" class="article-title">{article.title}</a>
            <div class="article-meta">{source_info}</div>
            <div class="article-snippet">{snippet}</div>
            <div class="tags">{''.join(tags_html)}</div>
        </div>
        """

    def _generate_text_body(
        self,
        articles: list[Article],
        is_digest: bool = False
    ) -> str:
        """Generate plain text email body.

        Args:
            articles: List of articles
            is_digest: Whether this is a digest

        Returns:
            Plain text string
        """
        lines = [
            f"{'News Digest' if is_digest else 'News Alert'}",
            f"{len(articles)} article(s) found",
            "=" * 50,
            ""
        ]

        for article in articles:
            lines.append(f"Title: {article.title}")
            lines.append(f"URL: {article.url}")
            lines.append(f"Source: {article.source}")

            if article.published_at:
                lines.append(f"Published: {article.published_at.strftime('%Y-%m-%d')}")

            if article.tags:
                lines.append(f"Tags: {', '.join(article.tags)}")

            if article.competitor_mentions:
                lines.append(f"Competitors: {', '.join(article.competitor_mentions)}")

            if article.client_mentions:
                clients = [f"{c.get('name')} ({c.get('type')})" for c in article.client_mentions]
                lines.append(f"Clients: {', '.join(clients)}")

            lines.append(f"Priority: {article.email_routing.priority.value}")

            snippet = article.summary or article.content[:200]
            if snippet:
                lines.append(f"Snippet: {snippet}...")

            lines.append("")
            lines.append("-" * 40)
            lines.append("")

        lines.append(f"Generated by News Aggregator on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(lines)

    def send_article_alert(
        self,
        article: Article,
        subject: str | None = None
    ) -> bool:
        """Send immediate alert for a single article.

        Args:
            article: Article to send alert for
            subject: Optional custom subject

        Returns:
            True if sent successfully
        """
        if not article.email_routing.recipients:
            logger.warning(f"No recipients for article: {article.title}")
            return False

        if not self.smtp_config or not self.smtp_config.username:
            logger.error("SMTP not configured, cannot send email")
            return False

        try:
            smtp = self._create_smtp_connection()

            subject = subject or f"[News Alert] {article.title[:50]}"
            msg = self._create_html_email(subject, [article], is_digest=False)

            # Send to all recipients
            for recipient in article.email_routing.recipients:
                msg["To"] = recipient
                smtp.send_message(msg)
                del msg["To"]  # Remove for next recipient

            smtp.quit()
            logger.info(f"Sent alert for: {article.title[:50]}")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def send_digest(
        self,
        articles: list[Article],
        recipients: list[str],
        subject: str | None = None
    ) -> bool:
        """Send digest email for multiple articles.

        Args:
            articles: List of articles to include
            recipients: List of recipient emails
            subject: Optional custom subject

        Returns:
            True if sent successfully
        """
        if not articles or not recipients:
            logger.warning("No articles or recipients for digest")
            return False

        if not self.smtp_config or not self.smtp_config.username:
            logger.error("SMTP not configured, cannot send email")
            return False

        try:
            smtp = self._create_smtp_connection()

            # Group by category for subject
            categories = set(a.category.value for a in articles)
            cat_str = ", ".join(sorted(categories))

            subject = subject or f"[News Digest - {cat_str}] {len(articles)} articles"
            msg = self._create_html_email(subject, articles, is_digest=True)

            # Send to all recipients
            for recipient in recipients:
                msg["To"] = recipient
                smtp.send_message(msg)
                del msg["To"]

            smtp.quit()
            logger.info(f"Sent digest with {len(articles)} articles to {len(recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send digest: {e}")
            return False

    def send_test_email(self, recipient: str) -> bool:
        """Send a test email to verify configuration.

        Args:
            recipient: Email address to send test to

        Returns:
            True if sent successfully
        """
        if not self.smtp_config or not self.smtp_config.username:
            logger.error("SMTP not configured")
            return False

        try:
            smtp = self._create_smtp_connection()

            subject = "News Aggregator - Test Email"
            body = """
            <html>
            <body>
                <h2>News Aggregator Test</h2>
                <p>This is a test email from your News Aggregator system.</p>
                <p>If you received this, your email configuration is working correctly!</p>
                <hr>
                <p><small>Sent at: {}</small></p>
            </body>
            </html>
            """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_config.username
            msg["To"] = recipient
            msg.attach(MIMEText(body, "html"))

            smtp.send_message(msg)
            smtp.quit()

            logger.info(f"Test email sent to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return False

    def is_configured(self) -> bool:
        """Check if email is properly configured.

        Returns:
            True if SMTP config is valid
        """
        if not self.smtp_config:
            return False
        return bool(
            self.smtp_config.host and
            self.smtp_config.username and
            self.smtp_config.password
        )
