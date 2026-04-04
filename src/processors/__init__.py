"""Article processors."""

from src.processors.classifier import Classifier
from src.processors.email_router import EmailRouter
from src.processors.embedder import OllamaEmbedder
from src.processors.summarizer import Summarizer
from src.processors.tagger import Tagger
from src.processors.url_checker import URLChecker

__all__ = [
    "OllamaEmbedder",
    "Classifier",
    "Tagger",
    "EmailRouter",
    "Summarizer",
    "URLChecker",
]
