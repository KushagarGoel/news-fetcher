"""News fetchers for different sources."""

from src.fetchers.base import BaseFetcher
from src.fetchers.bloomberg_fetcher import BloombergFetcher
from src.fetchers.bs_fetcher import BusinessStandardFetcher
from src.fetchers.et_fetcher import EconomicTimesFetcher
from src.fetchers.hn_fetcher import HNFetcher
from src.fetchers.inc42_fetcher import Inc42Fetcher
from src.fetchers.ken_fetcher import TheKenFetcher
from src.fetchers.medium_fetcher import MediumFetcher
from src.fetchers.rbi_fetcher import RBIFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.tracxn_fetcher import TracxnFetcher
from src.fetchers.web_scraper import WebScraper

__all__ = [
    "BaseFetcher",
    "RSSFetcher",
    "HNFetcher",
    "MediumFetcher",
    "WebScraper",
    "Inc42Fetcher",
    "TheKenFetcher",
    "EconomicTimesFetcher",
    "RBIFetcher",
    "BusinessStandardFetcher",
    "TracxnFetcher",
    "BloombergFetcher",
]
