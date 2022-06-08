import re
from dataclasses import dataclass
from typing import Optional, Tuple

from itp import itp

from takumi._boto import connections
from takumi.utils.emojis import remove_emojis


class SentimentException(Exception):
    pass


class UnknownLanguage(SentimentException):
    pass


class UnsupportedLanguage(SentimentException):
    pass


class CommentTooShort(SentimentException):
    pass


COUNTRY_CODES = ["hi", "de", "zh-TW", "ko", "pt", "en", "it", "fr", "zh", "es", "ar", "ja"]


@dataclass
class Sentiment:
    text: str
    language_code: str
    sentiment: str
    positive_score: float
    neutral_score: float
    negative_score: float
    mixed_score: float


class SentimentAnalyser:
    def __init__(
        self, min_confidence: float = 0.75, min_comment_length: int = 5, ignore_emoji: bool = True
    ) -> None:
        self.min_confidence = min_confidence
        self.min_comment_length = min_comment_length
        self.ignore_emoji = ignore_emoji

    def clean_up_text(self, text: str) -> str:
        """Clean up the text before analysis"""

        # Remove emojis if set
        if self.ignore_emoji:
            text = remove_emojis(text)

        # Remove hashtags and mentions
        parsed = itp.Parser().parse(text)
        tags = {f"#{tag}" for tag in parsed.tags}
        mentions = {f"@{mention}" for mention in parsed.users}

        text = re.sub("|".join(tags | mentions), "", text)

        # Remove long spaces
        text = re.sub(r" {2,}", " ", text)

        return text.strip()

    def analyse(self, text: str, language_code: Optional[str] = None) -> Sentiment:
        text = self.clean_up_text(text)
        if len(text) < self.min_comment_length:
            raise CommentTooShort(
                f"Comment has to be at least {self.min_comment_length} characters"
            )

        if language_code is None:
            language_code, confidence = self.identify_language(text)

        if language_code.lower() not in COUNTRY_CODES:
            raise UnsupportedLanguage(f"{language_code} is not supported")

        client = connections.comprehend

        response = client.detect_sentiment(Text=text, LanguageCode=language_code.lower())  # type: ignore
        scores = response["SentimentScore"]

        return Sentiment(
            text=text,
            language_code=language_code,
            sentiment=response["Sentiment"],
            positive_score=scores["Positive"],
            neutral_score=scores["Neutral"],
            negative_score=scores["Negative"],
            mixed_score=scores["Mixed"],
        )

    def identify_language(self, text: str) -> Tuple[str, float]:
        client = connections.comprehend

        response = client.detect_dominant_language(Text=text)

        languages = response["Languages"]
        if not languages:
            raise UnknownLanguage()

        primary_language = languages[0]
        return primary_language["LanguageCode"], primary_language["Score"]
