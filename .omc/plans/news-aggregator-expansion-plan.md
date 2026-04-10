# News Aggregator Expansion Plan

## Requirements Summary

### New Data Sources to Add
| Source | Type | Categories | Notes |
|--------|------|------------|-------|
| Inc42 | RSS/Scrape | tech, industry, competitor | Indian startup news |
| The Ken | RSS/Scrape | tech, industry, competitor | Premium Indian business |
| Economic Times | RSS | tech, industry, competitor | Major Indian financial daily |
| RBI | RSS/API | industry | Regulatory announcements |
| Business Standard | RSS | tech, industry, competitor | Indian business news |
| Tracxn | Scrape/API | competitor, tech | Startup intelligence |
| Bloomberg | RSS | industry, competitor | International (high relevance threshold) |

### Time-Based Filtering
- Fetch news from last 24 hours only
- Filter articles by `published_at` timestamp
- Configurable lookback window (default: 1 day)

### Regional Focus Enhancement
- **Primary**: Indian domestic news (region: IN)
- **Secondary**: International news only if relevance score >= HIGH threshold (0.8+)
- Add region detection to Article model
- Implement region-based relevance boosting

---

## RALPLAN-DR Summary

### Principles
1. **Modularity**: Each fetcher is independent, swappable, and follows the BaseFetcher interface
2. **Configurability**: Sources defined in YAML; no code changes needed to add/remove
3. **Regional Relevance**: India-first approach with strict quality gates for international
4. **Freshness**: Time-bound fetching ensures only recent, relevant news
5. **Graceful Degradation**: Failed fetchers don't block others; fallback to cached data

### Decision Drivers
1. **Data Availability** - RSS feeds preferred (reliable, structured); scraping as fallback
2. **Rate Limiting** - Respect robots.txt and implement delays to avoid blocks
3. **Content Quality** - LLM-based relevance scoring for international sources

### Viable Options

#### Option A: RSS-First Approach
- **Approach**: Prioritize RSS feeds where available, implement custom scrapers only when needed
- **Pros**: Reliable, standardized format, easier parsing, respects rate limits
- **Cons**: Limited content, may not have full article text, some sources lack RSS

#### Option B: API-First with Fallback
- **Approach**: Use APIs (where available like Tracxn), fallback to scraping
- **Pros**: Structured data, authenticated access, better rate limits
- **Cons**: Requires API keys, rate limiting, not all sources have APIs

#### Option C: Hybrid (Selected)
- **Approach**: RSS for standard news sources, custom scrapers for complex sites, API for data providers
- **Pros**: Balanced coverage, flexibility per source type
- **Cons**: More code paths to maintain

**Why Chosen**: Best coverage across diverse source types (news sites, regulatory, data platforms)

---

## Implementation Steps

### Phase 1: Regional & Time Filtering Infrastructure

#### 1.1 Update Article Model (src/models.py:64-99)
```python
# Add to Article class:
- region: str = "IN"  # ISO country code
- relevance_score: float = 0.0  # 0.0-1.0
- is_international: bool = False
```

#### 1.2 Create Time Filter Utility (src/processors/time_filter.py)
```python
class TimeFilter:
    """Filter articles by publication time."""

    def __init__(self, hours: int = 24):
        self.cutoff = datetime.utcnow() - timedelta(hours=hours)

    def is_recent(self, article: Article) -> bool:
        """Check if article is within the time window."""
        if not article.published_at:
            return True  # Include if no date (safer)
        return article.published_at >= self.cutoff
```

#### 1.3 Create Region Filter (src/processors/region_filter.py)
```python
class RegionFilter:
    """Filter and score articles by region relevance."""

    INDIAN_DOMAINS = [
        '.in', 'india', 'hindu', 'timesofindia', 'economictimes',
        'business-standard', 'inc42', 'the-ken', 'yourstory'
    ]

    INTERNATIONAL_HIGH_THRESHOLD = 0.8

    def detect_region(self, article: Article) -> str:
        """Detect region from URL, content, source."""
        # Implementation

    def should_include(self, article: Article) -> bool:
        """Include if Indian OR international with high relevance."""
        if article.region == "IN":
            return True
        if article.is_international and article.relevance_score >= self.INTERNATIONAL_HIGH_THRESHOLD:
            return True
        return False
```

#### 1.4 Update RelevanceChecker (src/processors/relevance_checker.py:14-147)
Add region-aware relevance scoring:
```python
# Add to check_relevance method:
- Detect if article is international
- Boost score for India-specific content
- Require higher threshold for non-Indian sources
```

### Phase 2: New Fetcher Implementations

#### 2.1 Inc42 Fetcher (src/fetchers/inc42_fetcher.py)
```python
class Inc42Fetcher(BaseFetcher):
    """Fetch from Inc42 RSS and API."""

    RSS_URL = "https://inc42.com/feed/"
    CATEGORIES = [Category.TECH, Category.INDUSTRY, Category.COMPETITOR]

    def fetch(self, max_articles: int = 20) -> list[Article]:
        # Use RSSFetcher as base
        # Filter for fintech/lending keywords
```

**File to create**: src/fetchers/inc42_fetcher.py (50-80 lines)

#### 2.2 The Ken Fetcher (src/fetchers/ken_fetcher.py)
```python
class TheKenFetcher(BaseFetcher):
    """Fetch from The Ken (may require subscription)."""

    RSS_URL = "https://the-ken.com/feed/"

    def fetch(self, max_articles: int = 20) -> list[Article]:
        # RSS-based with keyword filtering
```

**File to create**: src/fetchers/ken_fetcher.py (50-80 lines)

#### 2.3 Economic Times Fetcher (src/fetchers/et_fetcher.py)
```python
class EconomicTimesFetcher(BaseFetcher):
    """Fetch from Economic Times RSS feeds."""

    RSS_FEEDS = {
        "tech": "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms",
        "industry": "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
        "fintech": "https://economictimes.indiatimes.com/prime/fintech-and-bfsi/rssfeeds/91925810.cms",
        "companies": "https://economictimes.indiatimes.com/news/company/rssfeeds/2143429.cms",  # Competitor news
        "all": [
            "https://economictimes.indiatimes.com/rssfeedsdefault.cms",  # Default/all news
            "https://economictimes.indiatimes.com/news/rssfeeds/1715249553.cms"  # Latest news
        ]
    }

    def __init__(self, category: Category, section: str | None = None):
        """Initialize for a category, optionally override section."""
        self.category = category
        # Map category to default section, or use 'all' for mixed content
        self.section = section or self._get_section_for_category(category)
```

**File to create**: src/fetchers/et_fetcher.py (60-90 lines)

#### 2.4 RBI Fetcher (src/fetchers/rbi_fetcher.py)
```python
class RBIFetcher(BaseFetcher):
    """Fetch RBI press releases and notifications."""

    RSS_URL = "https://www.rbi.org.in/Scripts/RSSFeed.aspx?type=PR"
    CATEGORY = Category.INDUSTRY

    def fetch(self, max_articles: int = 20) -> list[Article]:
        # Parse RBI RSS
        # Mark all as regulatory content
```

**File to create**: src/fetchers/rbi_fetcher.py (40-60 lines)

#### 2.5 Business Standard Fetcher (src/fetchers/bs_fetcher.py)
```python
class BusinessStandardFetcher(BaseFetcher):
    """Fetch from Business Standard RSS."""

    RSS_FEEDS = {
        "tech": "https://www.business-standard.com/rss/technology-101.rss",
        "industry": "https://www.business-standard.com/rss/companies-101.rss",
        "finance": "https://www.business-standard.com/rss/finance-101.rss"
    }
```

**File to create**: src/fetchers/bs_fetcher.py (60-90 lines)

#### 2.6 Tracxn Fetcher (src/fetchers/tracxn_fetcher.py)
```python
class TracxnFetcher(BaseFetcher):
    """Fetch startup intelligence from Tracxn."""

    # Note: Requires API key for full access
    BASE_URL = "https://api.tracxn.com/api/2/"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("TRACXN_API_KEY")

    def fetch(self, max_articles: int = 20) -> list[Article]:
        # API-based fetch if key available
        # Otherwise, skip gracefully
```

**File to create**: src/fetchers/tracxn_fetcher.py (70-100 lines)

#### 2.7 Bloomberg Fetcher (src/fetchers/bloomberg_fetcher.py)
```python
class BloombergFetcher(BaseFetcher):
    """Fetch from Bloomberg with high relevance threshold."""

    RSS_URL = "https://feeds.bloomberg.com/business/news.rss"

    def fetch(self, max_articles: int = 20) -> list[Article]:
        # Fetch via RSS
        # Mark all as international
        # Require higher relevance score
```

**File to create**: src/fetchers/bloomberg_fetcher.py (50-80 lines)

### Phase 3: Update News Service Integration

#### 3.1 Update NewsService._create_fetchers (src/news_service.py:81-125)
```python
# Add new fetchers by category:

# All major Indian business sources available for ALL categories
# Each source fetches all content, keyword filtering happens post-fetch
fetchers.extend([
    Inc42Fetcher(category=category),
    TheKenFetcher(category=category),
    EconomicTimesFetcher(category=category),
    BusinessStandardFetcher(category=category),
])

# Category-specific additional sources
if category == Category.TECH:
    fetchers.extend([
        BloombergFetcher(),  # International, filtered by relevance
    ])
elif category == Category.INDUSTRY:
    fetchers.extend([
        RBIFetcher(),  # Regulatory only for industry
    ])
elif category == Category.COMPETITOR:
    fetchers.extend([
        TracxnFetcher(),  # Startup intelligence for competitors
    ])
elif category == Category.CLIENTS:
    # Clients category uses same Indian sources + client-specific Google News
    pass
```

**File to edit**: src/news_service.py (lines 81-125, add 30-50 lines)

#### 3.2 Update fetch_category with Time Filter (src/news_service.py:273-355)
```python
# In fetch_category method:
- Initialize TimeFilter(hours=24)
- After fetching articles, filter by time
- Apply region filter
- Then process through relevance checker
```

**File to edit**: src/news_service.py (lines 273-355, modify 20-30 lines)

### Phase 4: Configuration Updates

#### 4.1 Update config/sources.yaml
```yaml
tech:
  rss_feeds:
    - name: "hacker_news"
      url: "https://news.ycombinator.com/rss"
    - name: "inc42"
      url: "https://inc42.com/feed/"
      filter_keywords: ["fintech", "lending", "startup"]
    - name: "the_ken"
      url: "https://the-ken.com/feed/"
    - name: "et_tech"
      url: "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"
    - name: "bs_tech"
      url: "https://www.business-standard.com/rss/technology-101.rss"
    - name: "bloomberg"
      url: "https://feeds.bloomberg.com/business/news.rss"
      international: true
      min_relevance: 0.8

industry:
  rss_feeds:
    - name: "rbi_press"
      url: "https://www.rbi.org.in/Scripts/RSSFeed.aspx?type=PR"
      tags: ["regulatory", "RBI"]
    - name: "et_industry"
      url: "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms"
    - name: "et_fintech"
      url: "https://economictimes.indiatimes.com/prime/fintech-and-bfsi/rssfeeds/91925810.cms"
    - name: "bs_finance"
      url: "https://www.business-standard.com/rss/finance-101.rss"
    - name: "inc42_industry"
      url: "https://inc42.com/feed/"

competitor:
  rss_feeds:
    - name: "the_ken_comp"
      url: "https://the-ken.com/feed/"
    - name: "inc42_comp"
      url: "https://inc42.com/feed/"
    - name: "tracxn"
      type: "api"
      requires_auth: true
  scrape_targets:
    - name: "paytm_blog"
      url: "https://blog.paytm.com"
      selector: "article"
    - name: "phonepe_blog"
      url: "https://www.phonepe.com/blog/"
      selector: ".blog-post"

clients:
  rss_feeds: []
  scrape_targets:
    - name: "hdfc_news"
      url: "https://www.hdfcbank.com/about-us/news-room"
      selector: ".news-item"
```

**File to edit**: config/sources.yaml (complete rewrite, ~80 lines)

#### 4.2 Update config/keywords.yaml
```yaml
# Add international context keywords
industry:
  - "digital lending"
  # ... existing keywords
  - "India fintech"  # Boost Indian context
  - "Indian banking"

tech:
  - "fintech"
  # ... existing keywords
  - "India startup"
  - "Bengaluru"  # Tech hub
  - "Mumbai fintech"
```

**File to edit**: config/keywords.yaml (add 5-10 lines)

### Phase 5: Integration & Testing

#### 5.1 Update fetchers/__init__.py
Export all new fetcher classes.

**File to edit**: src/fetchers/__init__.py (add 7 exports)

#### 5.2 Add CLI Option for Time Window (src/main.py:131-222)
```python
fetch_parser.add_argument(
    "--hours",
    type=int,
    default=24,
    help="Only fetch articles from last N hours (default: 24)"
)
```

**File to edit**: src/main.py (add 6 lines)

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| RSS feeds change/break | Medium | Fallback to scraping; health checks; alerts |
| Rate limiting on new sources | Medium | Implement delays; respect robots.txt; rotate user agents |
| Tracxn API unavailable | Low | Skip gracefully if no API key; don't block other fetchers |
| False positives in international news | Medium | Strict relevance threshold (0.8+); manual review first week |
| Time filter excludes valid articles | Low | 24-hour default, configurable; include articles without dates |
| The Ken paywall blocks content | Medium | RSS gives summaries; mark as premium source |

---

## Verification Steps

1. **Unit Tests** for each new fetcher:
   ```python
   def test_inc42_fetcher():
       fetcher = Inc42Fetcher(category=Category.TECH)
       articles = fetcher.fetch(max_articles=5)
       assert len(articles) <= 5
       assert all(a.source == "inc42" for a in articles)
   ```

2. **Integration Test** for time filtering:
   ```python
   def test_time_filter():
       filter = TimeFilter(hours=24)
       old_article = Article(published_at=datetime.now() - timedelta(days=2))
       new_article = Article(published_at=datetime.now() - timedelta(hours=2))
       assert not filter.is_recent(old_article)
       assert filter.is_recent(new_article)
   ```

3. **End-to-End Test**:
   ```bash
   python -m src.main fetch --category tech --hours 24 --no-email
   # Verify only recent articles fetched from new sources
   ```

4. **Manual Verification** (first run):
   - Check articles from Bloomberg are high-quality and relevant
   - Verify RBI articles tagged correctly
   - Confirm Tracxn skipped if no API key

---

## ADR (Architecture Decision Record)

### Decision
Implement 7 new fetchers using a hybrid approach (RSS primary, scraping fallback, API for data providers) with time-based filtering (24h) and region-aware relevance scoring.

### Drivers
- Need broader coverage of Indian fintech news (Inc42, The Ken, ET, BS)
- Regulatory tracking requires RBI integration
- Competitive intelligence needs Tracxn
- International context valuable but must be high-quality (Bloomberg with threshold)

### Alternatives Considered
1. **Universal Scraper** - Single flexible scraper for all sites
   - Rejected: Too fragile, hard to maintain per-site logic
2. **NewsAPI Integration** - Use aggregator API instead of direct sources
   - Rejected: Cost, less control, limited Indian fintech coverage
3. **LLM-Based Extraction** - Use LLM to parse any webpage
   - Rejected: Expensive, slow, unnecessary for RSS-available sources

### Consequences
- **Positive**: Better coverage, modular design, clear per-source logic
- **Negative**: More files to maintain, need to monitor source changes

### Follow-ups
- Monitor fetcher success rates; add alerts if sources fail
- Consider caching layer for API sources (Tracxn)
- Evaluate need for more international sources after 2 weeks

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-04 | Initial plan created |
