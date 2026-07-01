"""Translator — translate English content to Chinese using Google Translate."""

from __future__ import annotations

import logging
import re
from typing import Any

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Simple language detection: if >50% of alpha chars are ASCII, consider English
_ASCII_ALPHA_RE = re.compile(r"[a-zA-Z]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def is_english(text: str) -> bool:
    """Detect if text is predominantly English using character ratio.

    Returns True if >50% of alphabetic characters are ASCII.
    """
    if not text:
        return False
    ascii_count = len(_ASCII_ALPHA_RE.findall(text))
    cjk_count = len(_CJK_RE.findall(text))
    total = ascii_count + cjk_count
    if total == 0:
        return False
    return ascii_count / total > 0.5


def translate_text(
    text: str,
    source: str = "en",
    target: str = "zh-CN",
    max_length: int = 4500,
) -> str:
    """Translate text from source to target language.

    Args:
        text: Text to translate.
        source: Source language code.
        target: Target language code.
        max_length: Max chars per request (Google limit ~5000).

    Returns:
        Translated text, or original if translation fails.
    """
    if not text or not text.strip():
        return text

    # Truncate to avoid API limits
    if len(text) > max_length:
        text = text[:max_length]

    try:
        translator = GoogleTranslator(source=source, target=target)
        result = translator.translate(text)
        if result:
            return result
        return text
    except Exception as exc:
        logger.warning("Translation failed: %s", exc)
        return text


def translate_entry_summary(
    summary: str,
    source_lang: str = "en",
    target_lang: str = "zh-CN",
) -> str:
    """Translate an entry's summary if it's in the source language.

    Only translates if the text is detected as the source language.
    Returns the original text if already in target language or on failure.
    """
    if not summary:
        return summary

    if source_lang == "en" and not is_english(summary):
        return summary  # Already Chinese or mixed

    return translate_text(summary, source=source_lang, target=target_lang)
