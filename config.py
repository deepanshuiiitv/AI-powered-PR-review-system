"""
Configuration — loads from .env file.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; env vars can be set manually


class Config:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.github_token = os.getenv("GITHUB_TOKEN", "").strip()

        if not self.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is missing.\n"
                "  → Get a FREE key at: https://console.groq.com\n"
                "  → Add it to your .env file: GROQ_API_KEY=gsk_..."
            )