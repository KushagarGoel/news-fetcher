"""Pydantic data models for the news aggregation system."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class Category(str, Enum):
    """Article category enumeration."""
    TECH = "tech"
    INDUSTRY = "industry"
    COMPETITOR = "competitor"
    CLIENTS = "clients"


class ClientType(str, Enum):
    """Client type enumeration."""
    LENDER = "lender"
    MERCHANT = "merchant"


class Priority(str, Enum):
    """Email priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Source(BaseModel):
    """News source configuration."""
    name: str
    url: str
    type: str = "rss"  # rss, api, scrape
    category: Category


class Competitor(BaseModel):
    """Competitor configuration."""
    name: str
    domains: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ClientConfig(BaseModel):
    """Client configuration."""
    name: str
    keywords: list[str] = Field(default_factory=list)
    client_type: Optional[ClientType] = None


class EmailRouting(BaseModel):
    """Email routing decision for an article."""
    matched_entities: list[str] = Field(default_factory=list)
    matched_tags: list[str] = Field(default_factory=list)
    recipients: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    digest_mode: bool = True


class Article(BaseModel):
    """News article data model."""
    id: UUID = Field(default_factory=uuid4)
    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    content: str = ""
    summary: str = ""
    content_hash: Optional[str] = None
    embedding: Optional[list[float]] = None
    category: Category = Category.INDUSTRY
    matched_keywords: list[str] = Field(default_factory=list)
    competitor_mentions: list[str] = Field(default_factory=list)
    client_mentions: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    email_routing: EmailRouting = Field(default_factory=EmailRouting)

    # Duplicate handling
    send_in_mail: bool = True  # Whether to include in email notifications
    duplicate_group_id: Optional[UUID] = None  # ID of the article this is a duplicate of

    def get_embedding_text(self) -> str:
        """Get text for embedding generation (title + summary only)."""
        text_parts = [self.title]
        if self.summary:
            text_parts.append(self.summary)
        return "\n".join(text_parts)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            UUID: lambda v: str(v)
        }


class SMTPConfig(BaseModel):
    """SMTP configuration for email notifications."""
    host: str
    port: int = 587
    username: str
    password: str
    use_tls: bool = True


class EntityRouting(BaseModel):
    """Routing configuration for a specific entity."""
    recipients: list[str] = Field(default_factory=list)
    digest_mode: bool = True
    client_type: Optional[ClientType] = None


class TagRouting(BaseModel):
    """Routing configuration for a specific tag."""
    recipients: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM


class CategoryRouting(BaseModel):
    """Routing configuration for a category."""
    recipients: list[str] = Field(default_factory=list)
    digest_mode: bool = True


class RoutingConfig(BaseModel):
    """Complete email routing configuration."""
    category_defaults: dict[str, CategoryRouting] = Field(default_factory=dict)
    entities: dict[str, dict[str, EntityRouting]] = Field(default_factory=dict)
    tags: dict[str, TagRouting] = Field(default_factory=dict)


class EmailConfig(BaseModel):
    """Complete email configuration."""
    smtp: SMTPConfig
    routing: RoutingConfig
    settings: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Search result from hybrid search."""
    article: Article
    semantic_score: float
    keyword_score: float
    combined_score: float


class FetchResult(BaseModel):
    """Result of a fetch operation."""
    source: str
    category: Category
    articles_found: int
    articles_added: int
    articles_duplicated: int
    errors: list[str] = Field(default_factory=list)
