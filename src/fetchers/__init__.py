"""News fetchers for different sources."""

from src.fetchers.base import BaseFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.hn_fetcher import HNFetcher
from src.fetchers.medium_fetcher import MediumFetcher
from src.fetchers.web_scraper import WebScraper

__all__ = ["BaseFetcher", "RSSFetcher", "HNFetcher", "MediumFetcher", "WebScraper"]
