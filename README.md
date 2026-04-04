# News Aggregator for Indian Fintech

A news aggregation system that monitors competitors, clients (lenders and merchants), industry news, and tech news for the Indian fintech lending space.

## Features

- **Multi-source fetching**: Google News RSS, Hacker News, Medium, web scraping
- **Category-wise storage**: Separate ChromaDB collections for tech, industry, competitor, and clients
- **Entity detection**: Automatically identifies mentions of competitors and clients
- **Auto-tagging**: Tags articles with event types (funding, acquisition, RBI regulation, etc.)
- **Smart email routing**: Routes notifications based on entities, tags, and categories
- **Hybrid search**: Combines semantic (Ollama embeddings) and keyword search
- **Scheduled execution**: Runs every 3 hours via cron/APScheduler

## Architecture

```
news-aggregator/
├── config/                 # YAML configuration files
│   ├── sources.yaml        # RSS feeds and scrape targets
│   ├── competitors.yaml    # Competitor list
│   ├── clients.yaml        # Lenders and merchants
│   ├── keywords.yaml       # Industry and tech keywords
│   └── email.yaml          # SMTP and routing config
├── src/
│   ├── fetchers/           # News source fetchers
│   ├── processors/         # Classification, tagging, routing
│   ├── storage/            # ChromaDB vector store
│   ├── search/             # Hybrid search
│   ├── notifications/      # Email notifications
│   ├── news_service.py     # Orchestration service
│   └── main.py             # CLI entry point
├── data/chroma_db/         # Vector database storage
├── cron.py                 # Scheduled job runner
└── requirements.txt
```

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Install and Start Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model
ollama pull nomic-embed-text

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 3. Configure Email (Optional)

Edit `config/email.yaml` or set environment variables:

```bash
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
```

### 4. Run

```bash
# Fetch all categories
python -m src.main fetch --all

# Fetch specific category
python -m src.main fetch --category tech
python -m src.main fetch --category competitor
python -m src.main fetch --category clients --client-type lender

# Search
python -m src.main search --category industry "RBI regulation"
python -m src.main search --category clients --client-type merchant "partnership"

# Check stats
python -m src.main stats

# Test email
python -m src.main test-email --recipient your@email.com
```

### 5. Run Scheduled

```bash
# Run once
python cron.py --run-once

# Start scheduler (every 3 hours)
python cron.py

# Custom interval
python cron.py --interval 1  # every hour
```

### 6. Setup System Cron

```bash
# Add to crontab
crontab -e

# Add line:
0 */3 * * * cd /path/to/news-aggregator && python cron.py --run-once >> logs/cron.log 2>&1
```

## Configuration

### Competitors

Edit `config/competitors.yaml`:

```yaml
competitors:
  - name: "Paytm"
    domains: ["paytm.com"]
    keywords: ["Paytm", "Paytm Credit"]
```

### Clients

Edit `config/clients.yaml`:

```yaml
lenders:
  - name: "HDFC Bank"
    keywords: ["HDFC Bank", "HDFC loans"]

merchants:
  - name: "Amazon India"
    keywords: ["Amazon India", "Amazon Pay"]
```

### Email Routing

Edit `config/email.yaml` for routing rules:

- Entity-specific routing (per competitor/client)
- Tag-based routing (funding, acquisition, etc.)
- Category defaults (fallback)

## Data Model

### Article

- `id`: UUID
- `title`: Article title
- `url`: Source URL
- `source`: Source name
- `published_at`: Original publication date
- `fetched_at`: When we fetched it
- `content`: Full text or summary
- `category`: tech | industry | competitor | clients
- `matched_keywords`: Keywords that matched
- `competitor_mentions`: Detected competitors
- `client_mentions`: Detected clients with type
- `tags`: Auto-generated tags
- `email_routing`: Computed routing decision

## Development

### Running Tests

```bash
pytest tests/
```

### Adding a New Fetcher

1. Create fetcher in `src/fetchers/`
2. Inherit from `BaseFetcher`
3. Add to `NewsService._create_fetchers()`

### Adding New Tags

Edit `src/processors/tagger.py` and add to `TAG_PATTERNS`.

## License

MIT
