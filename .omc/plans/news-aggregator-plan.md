# News Aggregation System - Implementation Plan

## Requirements Summary

Build a news aggregation system that:
1. Fetches news from multiple sources (Google News RSS, Hacker News, Medium, web scraping)
2. Monitors specific **competitors** in Indian fintech credit/loan space
3. Monitors **clients** (2 types: **lenders** and **merchants**) - track what they're doing
4. Tracks industry news for credit, loan systems, and fintech regulations
5. Tracks tech news (Hacker News, Medium, etc.)
6. Uses **ChromaDB with category-wise collections** (tech, industry, competitor, clients)
7. Uses **Ollama local embedding models** for semantic search
8. **Sends email notifications** when new articles are found per category
9. Supports hybrid search (semantic + exact keyword matching)
10. Runs on a cron schedule every 3 hours

## Tech Stack

- **Language**: Python 3.11+
- **Vector DB**: ChromaDB with 4 separate collections (tech, industry, competitor, clients)
- **Embeddings**: Ollama local models (nomic-embed-text or mxbai-embed-large)
- **Scraping**: Playwright (headless browser) + feedparser (RSS)
- **Search**: ChromaDB hybrid search per collection
- **Scheduling**: APScheduler (every 3 hours)
- **Email**: smtplib (Gmail/Outlook/SMTP)
- **Config**: YAML for sources, competitors, keywords, email settings

## Data Model

```
Article:
  - id: UUID
  - title: string
  - url: string (unique constraint per collection)
  - source: string (google_news, hacker_news, medium, scraped)
  - published_at: datetime
  - fetched_at: datetime
  - content: text (full text or summary)
  - content_hash: string (for deduplication)
  - embedding: vector(dims depend on Ollama model)
  - category: string (tech | industry | competitor | clients)
  - matched_keywords: list[string]
  - competitor_mentions: list[string] (if category=competitor)
  - client_mentions: list[dict] (if category=clients)
    - name: string
    - type: string (lender | merchant)
  - tags: list[string]  # Auto-generated tags (funding, acquisition, RBI_regulation, etc.)
  - email_routing: dict  # Computed routing decision
    - matched_entities: list[string]  # Which entities matched
    - matched_tags: list[string]  # Which tags matched
    - recipients: list[string]  # Final deduplicated recipient list
    - priority: string (low | medium | high | critical)
```

## Project Structure

```
news-aggregator/
├── config/
│   ├── sources.yaml          # RSS feeds, URLs to scrape per category
│   ├── competitors.yaml      # List of competitor names/websites
│   ├── clients.yaml          # List of clients: lenders and merchants
│   ├── keywords.yaml         # Industry and tech keywords
│   └── email.yaml            # SMTP settings, recipients per category
├── src/
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract base class
│   │   ├── rss_fetcher.py    # Google News RSS
│   │   ├── hn_fetcher.py     # Hacker News API
│   │   ├── medium_fetcher.py # Medium scraping
│   │   └── web_scraper.py    # Generic headless scraper
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── deduplicator.py   # Content hash + embedding similarity
│   │   ├── classifier.py     # Assign category based on keywords
│   │   ├── embedder.py       # Ollama embedding client
│   │   ├── tagger.py         # Auto-generate tags from article content
│   │   └── email_router.py   # Compute email routing (entity + tag based)
│   ├── storage/
│   │   ├── __init__.py
│   │   └── vector_store.py   # ChromaDB with 3 collections
│   ├── search/
│   │   ├── __init__.py
│   │   └── hybrid_search.py  # Semantic + keyword search per collection
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── email_notifier.py # Send email alerts per category
│   └── main.py               # Entry point
├── scripts/
│   ├── fetch_news.py         # Manual run
│   └── search_news.py        # CLI search tool
├── data/
│   └── chroma_db/            # Vector DB storage
│       ├── tech/
│       ├── industry/
│       ├── competitor/
│       └── clients/
├── cron.py                   # Scheduled job runner with email alerts
├── requirements.txt
└── README.md
```

## Implementation Steps

### Phase 1: Core Infrastructure

**Step 1.1: Project Setup**
- Create directory structure
- Set up virtual environment
- Create requirements.txt with dependencies:
  - chromadb, feedparser, playwright, requests, pyyaml
  - apscheduler, pydantic, beautifulsoup4

**Step 1.2: Configuration System**

- `config/sources.yaml`:
  ```yaml
  tech:
    rss_feeds:
      - name: "hacker_news"
        url: "https://news.ycombinator.com/rss"
      - name: "medium_fintech"
        url: "https://medium.com/feed/tag/fintech"
    scrape_targets: []

  industry:
    rss_feeds:
      - name: "google_news_fintech"
        url: "https://news.google.com/rss/search?q=fintech+india+credit+loan"
      - name: "google_news_rbi"
        url: "https://news.google.com/rss/search?q=RBI+regulation+lending"
    scrape_targets: []

  competitor:
    rss_feeds:
      - name: "google_news_paytm"
        url: "https://news.google.com/rss/search?q=Paytm"
      - name: "google_news_phonepe"
        url: "https://news.google.com/rss/search?q=PhonePe"
    scrape_targets:
      - name: "paytm_blog"
        url: "https://blog.paytm.com"
        selector: "article"

  clients:
    # Monitors lenders and merchants (your clients)
    rss_feeds:
      - name: "google_news_lenders"
        url: "https://news.google.com/rss/search?q=HDFC+ICICI+Axis+lending+India"
      - name: "google_news_merchants"
        url: "https://news.google.com/rss/search?q=Amazon+Flipkart+India+ecommerce"
    scrape_targets:
      - name: "hdfc_blog"
        url: "https://www.hdfcbank.com/about-us/news-room"
        selector: ".news-item"
  ```

- `config/competitors.yaml`:
  ```yaml
  competitors:
    - name: "Paytm"
      domains: ["paytm.com", "paytmblog.com"]
      keywords: ["Paytm", "Paytm Credit", "Paytm Loans"]
    - name: "PhonePe"
      domains: ["phonepe.com"]
      keywords: ["PhonePe", "PhonePe Lending", "PhonePe Loans"]
    - name: "BharatPe"
      domains: ["bharatpe.com"]
      keywords: ["BharatPe", "BharatPe Lending"]
    - name: "CRED"
      domains: ["cred.club"]
      keywords: ["CRED", "CRED Cash"]
    - name: "Razorpay"
      domains: ["razorpay.com"]
      keywords: ["Razorpay", "Razorpay Capital"]
    - name: "Slice"
      domains: ["sliceit.com"]
      keywords: ["Slice", "Slice BNPL"]
    - name: "Uni Cards"
      domains: ["unicards.in"]
      keywords: ["Uni Cards", "Uni Paychek"]
  ```

- `config/clients.yaml`:
  ```yaml
  # Lenders: Banks, NBFCs, and lending platforms you work with
  lenders:
    - name: "HDFC Bank"
      keywords: ["HDFC Bank", "HDFC", "HDFC loans", "HDFC lending"]
    - name: "ICICI Bank"
      keywords: ["ICICI Bank", "ICICI", "ICICI loans"]
    - name: "Axis Bank"
      keywords: ["Axis Bank", "Axis", "Axis lending"]
    - name: "Kotak Mahindra Bank"
      keywords: ["Kotak", "Kotak Bank", "Kotak lending"]
    - name: "Bajaj Finance"
      keywords: ["Bajaj Finance", "Bajaj Finserv", "Bajaj loans"]
    - name: "Tata Capital"
      keywords: ["Tata Capital", "Tata loans"]
    - name: "Aditya Birla Finance"
      keywords: ["Aditya Birla Finance", "ABFL"]
    - name: "L&T Finance"
      keywords: ["L&T Finance", "LTF"]
    - name: "Cholamandalam Finance"
      keywords: ["Cholamandalam", "Chola loans"]
    - name: "Muthoot Finance"
      keywords: ["Muthoot", "Muthoot gold loan"]
    - name: "Manappuram Finance"
      keywords: ["Manappuram", "Manappuram gold loan"]

  # Merchants: E-commerce, retail partners, platforms you integrate with
  merchants:
    - name: "Amazon India"
      keywords: ["Amazon India", "Amazon Pay", "Amazon lending"]
    - name: "Flipkart"
      keywords: ["Flipkart", "Flipkart Pay Later"]
    - name: "Myntra"
      keywords: ["Myntra", "Myntra fashion"]
    - name: "Swiggy"
      keywords: ["Swiggy", "Swiggy Dineout"]
    - name: "Zomato"
      keywords: ["Zomato", "Zomato lending"]
    - name: "BigBasket"
      keywords: ["BigBasket", "BigBasket financing"]
    - name: "Reliance Retail"
      keywords: ["Reliance Retail", "JioMart", "AJIO"]
    - name: "Nykaa"
      keywords: ["Nykaa", "Nykaa fashion"]
    - name: "MakeMyTrip"
      keywords: ["MakeMyTrip", "MMT", "MMT loans"]
    - name: "Ola"
      keywords: ["Ola", "Ola Financial"]
  ```

- `config/keywords.yaml`:
  ```yaml
  industry:
    - "digital lending"
    - "BNPL"
    - "buy now pay later"
    - "credit score"
    - "credit bureau"
    - "loan disbursement"
    - "RBI regulation"
    - "RBI guidelines"
    - "NBFC"
    - "microfinance"
    - "peer to peer lending"
    - "P2P lending"
    - "embedded finance"
    - "lending infrastructure"
    - "co-lending"
    - "priority sector lending"
    - "UPI credit"
    - "cash flow based lending"

  tech:
    - "fintech"
    - "API banking"
    - "open banking"
    - "payment gateway"
    - "loan management system"
    - "credit underwriting"
    - "alternative data"
    - "AI lending"
    - "machine learning credit"
    - "blockchain finance"
    - "SaaS fintech"
  ```

- `config/email.yaml`:
  ```yaml
  smtp:
    host: "smtp.gmail.com"
    port: 587
    username: "your-email@gmail.com"
    password: "your-app-password"  # Use app password for Gmail
    use_tls: true

  # Multi-dimensional email routing configuration
  # Articles are matched against rules in priority order:
  # 1. Entity-specific (competitor/client) → highest priority
  # 2. Tag-based rules
  # 3. Category default → fallback

  routing:
    # CATEGORY-LEVEL DEFAULTS (fallback if no specific match)
    category_defaults:
      tech:
        recipients: ["tech-team@company.com", "cto@company.com"]
        digest_mode: true
      industry:
        recipients: ["strategy@company.com", "ceo@company.com"]
        digest_mode: true
      competitor:
        recipients: ["strategy@company.com", "competitive-intel@company.com"]
        digest_mode: false  # Instant alerts for competitors
      clients:
        recipients: ["account-management@company.com", "partnerships@company.com"]
        digest_mode: false  # Instant alerts for clients

    # ENTITY-SPECIFIC ROUTING (per competitor/client)
    # These override category defaults when matched
    entities:
      # Per-competitor routing
      competitors:
        "Paytm":
          recipients: ["paytm-tracker@company.com", "strategy@company.com"]
          digest_mode: false
        "PhonePe":
          recipients: ["phonepe-tracker@company.com"]
          digest_mode: false
        "CRED":
          recipients: ["cred-tracker@company.com", "product@company.com"]
          digest_mode: false

      # Per-client routing with client type
      clients:
        # Lenders
        "HDFC Bank":
          recipients: ["hdfc-am@company.com", "lending-team@company.com"]
          client_type: "lender"
          digest_mode: false
        "ICICI Bank":
          recipients: ["icici-am@company.com", "lending-team@company.com"]
          client_type: "lender"
          digest_mode: false
        "Bajaj Finance":
          recipients: ["bajaj-am@company.com"]
          client_type: "lender"
          digest_mode: true

        # Merchants
        "Amazon India":
          recipients: ["amazon-am@company.com", "partnerships@company.com"]
          client_type: "merchant"
          digest_mode: false
        "Flipkart":
          recipients: ["flipkart-am@company.com", "partnerships@company.com"]
          client_type: "merchant"
          digest_mode: false

    # TAG-BASED ROUTING (matches auto-generated tags)
    # Applied in addition to entity/category routing
    tags:
      "funding":
        recipients: ["investor-relations@company.com", "ceo@company.com"]
        priority: "high"
      "acquisition":
        recipients: ["strategy@company.com", "ceo@company.com", "legal@company.com"]
        priority: "critical"
      "product_launch":
        recipients: ["product@company.com", "strategy@company.com"]
        priority: "high"
      "partnership":
        recipients: ["partnerships@company.com", "bd@company.com"]
        priority: "medium"
      "RBI_regulation":
        recipients: ["compliance@company.com", "legal@company.com", "ceo@company.com"]
        priority: "critical"
      "data_breach":
        recipients: ["security@company.com", "cto@company.com", "ceo@company.com"]
        priority: "critical"
      "layoffs":
        recipients: ["hr@company.com", "strategy@company.com"]
        priority: "medium"
      "IPO":
        recipients: ["strategy@company.com", "ceo@company.com", "cfo@company.com"]
        priority: "high"

  # Global email settings
  settings:
    default_digest_mode: true
    max_articles_per_email: 10
    deduplicate_recipients: true  # If article matches multiple rules, don't send duplicate emails
    include_tags_in_subject: true
    include_entities_in_subject: true
  ```

**Step 1.3: Data Models**
- Pydantic models for Article, Source, Competitor, Client, EmailConfig
- Category enum: `tech`, `industry`, `competitor`, `clients`
- ClientType enum: `lender`, `merchant`

### Phase 2: Ollama Embedding Integration

**Step 2.1: Ollama Setup**
- Install Ollama locally
- Pull embedding model: `ollama pull nomic-embed-text` (768 dims) or `ollama pull mxbai-embed-large` (1024 dims)
- Create Ollama client wrapper

**Step 2.2: Embedder Module**
- `src/processors/embedder.py`:
  ```python
  class OllamaEmbedder:
      def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
          self.model = model
          self.base_url = base_url

      def embed(self, text: str) -> list[float]:
          # Call Ollama API to generate embedding
          # Handle batching for multiple texts
  ```

### Phase 3: Category-Wise Storage

**Step 3.1: ChromaDB Collections**
- Create 4 separate collections:
  - `tech_articles` - for Hacker News, Medium tech posts
  - `industry_articles` - for fintech, RBI, lending news
  - `competitor_articles` - for competitor mentions
  - `clients_articles` - for client (lenders + merchants) mentions

**Step 3.2: Deduplication Per Collection**
- Check URL existence in the specific category collection
- Semantic similarity check within same category only

### Phase 4: Classification

**Step 4.1: Category Classifier**
- Assign category based on keyword matching:
  1. Check competitor keywords first (highest priority)
  2. Check client keywords (lenders + merchants)
  3. Check industry keywords
  4. Check tech keywords
  5. Default to `industry` if no match

**Step 4.2: Competitor Detection**
- For `competitor` category, identify which competitors are mentioned
- Store competitor names in metadata

**Step 4.3: Client Detection**
- For `clients` category, identify which clients are mentioned
- Classify client type: `lender` or `merchant`
- Store client names and types in metadata

**Step 4.4: Auto-Tagging System**
- `src/processors/tagger.py` - Analyzes articles and assigns relevant tags
- Tag categories:
  - **Event tags**: `funding`, `acquisition`, `merger`, `IPO`, `layoffs`
  - **Product tags**: `product_launch`, `feature_release`, `partnership`
  - **Regulatory tags**: `RBI_regulation`, `compliance`, `policy_change`
  - **Security tags**: `data_breach`, `security_incident`
  - **Financial tags**: `earnings`, `profit`, `loss`, `quarterly_results`
  - **Market tags**: `expansion`, `new_market`, `international`
- Tag detection via:
  - Keyword patterns (e.g., "raises $50M" → `funding`)
  - NLP classification (title/content analysis)
  - Source-specific rules

**Step 4.5: Email Routing Decision**
- `src/processors/email_router.py` - Determines who gets notified
- Routing logic (priority order):
  1. Check entity-specific rules (competitor/client match)
  2. Check tag-based rules (article tags match configured tags)
  3. Fall back to category default
  4. Merge all recipients, deduplicate
  5. Determine priority (highest from all matched rules)
- Store routing decision in article for audit/debugging

### Phase 5: Email Notifications

**Step 5.1: Email Notifier**
- `src/notifications/email_notifier.py`:
  - SMTP client wrapper
  - HTML email template with article cards
  - Category-specific subject lines

**Step 5.2: Email Templates**
Subject formats:
- Tech: `[Tech] New Articles - 3 items [tags: API, fintech]`
- Industry: `[Industry] RBI Regulation Alert [tag: RBI_regulation, critical]`
- Competitor: `[Competitor: Paytm] Funding Round [tag: funding, high]`
- Client: `[Client: HDFC Bank/lender] Partnership [tag: partnership]`
- Multi-entity: `[Multi] Paytm, HDFC Bank - New Activity [tags: funding]`

Email body includes:
- Article title, snippet, URL
- Matched entities (competitors/clients)
- Auto-generated tags
- Priority level
- Source and timestamp

**Step 5.3: Notification Logic**
- After each fetch cycle:
  1. For each new article, compute email routing (entities + tags)
  2. Group articles by recipient list
  3. Apply digest rules per entity/tag configuration
  4. Send emails (individual or digest based on settings)
  5. Log all sent notifications with routing audit trail

**Step 5.4: Digest Mode**
- Per-entity/tag configurable digest mode
- Time-based digest windows (e.g., hourly, daily)
- Maximum articles per digest email
- Priority articles can force immediate send

### Phase 6: Fetchers

**Step 6.1: Category-Aware Fetchers**
- Each fetcher returns articles with suggested category
- RSS fetcher uses category from config
- Web scraper classifies content

**Step 6.2: RSS Fetcher**
- Parse Google News RSS feeds
- Parse Hacker News RSS
- Parse Medium RSS feeds

**Step 6.3: Web Scraper**
- Playwright for dynamic content
- Extract article content with readability-lxml
- Respect rate limits

### Phase 7: Search (Per Category)

**Step 7.1: Category-Specific Search**
- Search within one collection at a time
- Query parameter: `category: tech | industry | competitor | clients`
- Additional filter for clients: `client_type: lender | merchant`

**Step 7.2: Hybrid Search**
- Semantic search using Ollama embeddings
- Keyword filter on metadata
- Combine and rank results

### Phase 8: CLI & Scheduling

**Step 8.1: CLI Commands**
```bash
# Fetch all categories
python -m src.main fetch --all

# Fetch specific category
python -m src.main fetch --category tech
python -m src.main fetch --category industry
python -m src.main fetch --category competitor
python -m src.main fetch --category clients

# Fetch specific client type
python -m src.main fetch --category clients --client-type lender
python -m src.main fetch --category clients --client-type merchant

# Search within category
python -m src.main search --category tech "microservices architecture"
python -m src.main search --category industry "RBI regulation"
python -m src.main search --category competitor --competitor "Paytm"
python -m src.main search --category clients --client "HDFC Bank"
python -m src.main search --category clients --client-type lender

# Test email
python -m src.main test-email
```

**Step 8.2: Scheduled Job with Notifications**
- `cron.py` runs every 3 hours
- Fetches all categories (tech, industry, competitor, clients)
- Sends email notifications for new articles per category
- For clients category, includes client type (lender/merchant) in email subject
- Logs summary

**Step 8.3: System Cron Setup**
```bash
0 */3 * * * cd /path/to/news-aggregator && python cron.py >> logs/cron.log 2>&1
```

## Acceptance Criteria

- [ ] Uses Ollama local embeddings (nomic-embed-text or mxbai-embed-large)
- [ ] Category-wise ChromaDB collections (tech, industry, competitor, clients)
- [ ] Fetches from Google News RSS, Hacker News, Medium
- [ ] Can scrape arbitrary websites with Playwright
- [ ] Classifies articles into correct category based on keywords
- [ ] Detects competitor mentions and stores in competitor collection
- [ ] Detects client mentions (lenders + merchants) and stores in clients collection
- [ ] Classifies clients by type: lender or merchant
- [ ] Sends email notifications per category when new articles found
- [ ] Includes client type (lender/merchant) in client email notifications
- [ ] Deduplicates by URL and semantic similarity within each collection
- [ ] Supports hybrid search (semantic + keyword) per category
- [ ] Supports filtering clients by type (lender/merchant)
- [ ] Runs on 3-hour cron schedule
- [ ] CLI for manual fetch, search, and email testing
- [ ] Configuration via YAML files

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Ollama not running | Check Ollama status before fetch, fail gracefully with error message |
| Email rate limiting | Use batch digest mode, implement exponential backoff |
| Storage growth | Implement retention policy per category (e.g., 90 days) |
| False positives in classification | Priority: competitor > industry > tech, allow manual override |
| False positives in dedup | Tune similarity threshold per category |
| Scraping failures | Graceful degradation, fallback to RSS |

## Verification Steps

1. Start Ollama, verify model is available
2. Run fetch manually, verify articles stored in correct category collections
3. Verify new articles trigger email notification
4. Run fetch again, verify no duplicates added
5. Search within each category, verify relevant results
6. Test hybrid search with keywords
7. Let cron run for 24 hours, verify 8 runs + emails sent
8. Check logs for errors

## Ollama Setup Instructions

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model (choose one)
ollama pull nomic-embed-text    # 768 dims, fast
ollama pull mxbai-embed-large   # 1024 dims, more accurate

# Verify it's running
curl http://localhost:11434/api/tags
```

## Next Steps

1. Review and approve updated plan
2. Install Ollama and pull embedding model
3. Implement Phase 1 (setup + config)
4. Implement Ollama embedder (Phase 2)
5. Implement category-wise storage (Phase 3)
6. Implement classification and competitor detection (Phase 4)
7. Implement email notifications (Phase 5)
8. Implement fetchers (Phase 6)
9. Implement search (Phase 7)
10. Add CLI and scheduling (Phase 8)
11. Test and refine
