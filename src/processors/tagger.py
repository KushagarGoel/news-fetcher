"""Auto-tagging system for articles."""

import logging
import re
from typing import Optional

from src.models import Article, Priority

logger = logging.getLogger(__name__)


class Tagger:
    """Auto-generate tags from article content."""

    # Tag patterns for different categories
    TAG_PATTERNS = {
        # Event tags
        "funding": [
            r"raises?\s+\$?\d+[\d,]*\s*[KMBkm]?\s*(?:million|billion|M|B)?",
            r"funding\s+round",
            r"series\s+[A-Fa-f]\s+funding",
            r"seed\s+funding",
            r"venture\s+capital",
            r"investment\s+of\s+\$?\d+",
            r"secures?\s+\$?\d+[\d,]*",
        ],
        "acquisition": [
            r"acquires?\s+",
            r"acquired\s+by",
            r"acquisition\s+of",
            r"buys?\s+(?:out\s+)?",
            r"takeover",
        ],
        "merger": [
            r"merger",
            r"merges?\s+with",
            r"combined\s+entity",
        ],
        "IPO": [
            r"IPO",
            r"initial\s+public\s+offering",
            r"going\s+public",
            r"lists?\s+on\s+(?:the\s+)?(?:NYSE|NASDAQ|BSE|NSE)",
        ],
        "layoffs": [
            r"layoffs?",
            r"lays?\s+off",
            r"job\s+cuts?",
            r"workforce\s+reduction",
            r"firing\s+\d+",
            r"\d+\s+(?:employees?|workers?)\s+(?:fired|laid\s+off)",
        ],
        # Product tags
        "product_launch": [
            r"launches?\s+(?:new\s+)?(?:product|service|feature)",
            r"introduces?\s+new",
            r"unveils?\s+",
            r"debuts?\s+",
            r"rolls?\s+out\s+",
        ],
        "feature_release": [
            r"new\s+feature",
            r"feature\s+update",
            r"enhancement",
        ],
        "partnership": [
            r"partners?\s+(?:with\s+)?",
            r"partnership",
            r"collaborates?\s+with",
            r"collaboration",
            r"alliance\s+with",
            r"ties?\s+up\s+with",
        ],
        # Regulatory tags
        "RBI_regulation": [
            r"RBI",
            r"Reserve\s+Bank\s+of\s+India",
            r"RBI\s+governor",
            r"monetary\s+policy",
            r"repo\s+rate",
            r"regulatory\s+guidelines?",
        ],
        "compliance": [
            r"compliance",
            r"regulatory\s+compliance",
            r"KYC",
            r"know\s+your\s+customer",
            r"AML",
            r"anti[-\s]?money\s+laundering",
        ],
        "policy_change": [
            r"policy\s+change",
            r"new\s+policy",
            r"regulatory\s+change",
            r"guidelines?\s+updated",
        ],
        # Security tags
        "data_breach": [
            r"data\s+breach",
            r"data\s+leak",
            r"exposed\s+data",
            r"customer\s+data\s+compromised",
            r"hacked",
            r"cyberattack",
        ],
        "security_incident": [
            r"security\s+incident",
            r"security\s+breach",
            r"vulnerability",
            r"security\s+flaw",
        ],
        # Financial tags
        "earnings": [
            r"quarterly\s+(?:results?|earnings?)",
            r"financial\s+results?",
            r"profit",
            r"revenue\s+\$?\d+",
        ],
        "quarterly_results": [
            r"Q[1-4]\s+(?:FY\d{2,4}|\d{4})",
            r"(?:first|second|third|fourth)\s+quarter",
            r"quarterly\s+(?:report|results?)",
        ],
        # Market tags
        "expansion": [
            r"expansion",
            r"expands?\s+(?:to|into|operations)",
            r"new\s+(?:office|branch|location)",
            r"grows?\s+(?:presence|footprint)",
        ],
        "new_market": [
            r"enters?\s+(?:the\s+)?(?:Indian?|new)\s+market",
            r"market\s+entry",
            r"launches?\s+in\s+",
        ],
        "international": [
            r"international",
            r"global\s+expansion",
            r"overseas",
            r"foreign\s+market",
        ],
    }

    # Tag priorities for routing
    TAG_PRIORITIES: dict[str, Priority] = {
        "acquisition": Priority.CRITICAL,
        "merger": Priority.CRITICAL,
        "RBI_regulation": Priority.CRITICAL,
        "data_breach": Priority.CRITICAL,
        "security_incident": Priority.CRITICAL,
        "funding": Priority.HIGH,
        "product_launch": Priority.HIGH,
        "IPO": Priority.HIGH,
        "partnership": Priority.MEDIUM,
        "layoffs": Priority.MEDIUM,
        "earnings": Priority.MEDIUM,
        "quarterly_results": Priority.MEDIUM,
        "expansion": Priority.MEDIUM,
        "new_market": Priority.MEDIUM,
    }

    def tag(self, article: Article) -> list[str]:
        """Generate tags for an article based on content.

        Args:
            article: Article to tag

        Returns:
            List of generated tags
        """
        text = f"{article.title} {article.content or ''}".lower()
        tags = []

        for tag_name, patterns in self.TAG_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    tags.append(tag_name)
                    break

        article.tags = tags
        return tags

    def get_priority(self, tags: list[str]) -> Priority:
        """Get the highest priority from a list of tags.

        Args:
            tags: List of tags

        Returns:
            Highest priority
        """
        highest = Priority.LOW
        for tag in tags:
            tag_priority = self.TAG_PRIORITIES.get(tag, Priority.LOW)
            if tag_priority.value > highest.value:
                highest = tag_priority
        return highest

    def has_critical_tags(self, tags: list[str]) -> bool:
        """Check if any tags are critical priority.

        Args:
            tags: List of tags

        Returns:
            True if any critical tags present
        """
        return any(
            self.TAG_PRIORITIES.get(tag) == Priority.CRITICAL
            for tag in tags
        )

    def get_tag_description(self, tag: str) -> Optional[str]:
        """Get a human-readable description for a tag.

        Args:
            tag: Tag name

        Returns:
            Description if available
        """
        descriptions = {
            "funding": "Funding round or investment",
            "acquisition": "Company acquisition",
            "merger": "Company merger",
            "IPO": "Initial Public Offering",
            "layoffs": "Job cuts or workforce reduction",
            "product_launch": "New product or service launch",
            "feature_release": "New feature announcement",
            "partnership": "Strategic partnership",
            "RBI_regulation": "RBI regulation or policy",
            "compliance": "Regulatory compliance",
            "policy_change": "Policy change",
            "data_breach": "Data breach or security incident",
            "security_incident": "Security-related incident",
            "earnings": "Financial earnings report",
            "quarterly_results": "Quarterly financial results",
            "expansion": "Business expansion",
            "new_market": "New market entry",
            "international": "International expansion",
        }
        return descriptions.get(tag)
