"""Tests for formatter/translator.py"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from infodigest.formatter.translator import (
    is_english,
    translate_text,
    translate_entry_summary,
)


class TestIsEnglish:
    def test_english_text(self) -> None:
        assert is_english("New AI model released with breakthrough performance") is True

    def test_chinese_text(self) -> None:
        assert is_english("全新AI模型发布，性能突破") is False

    def test_mixed_text(self) -> None:
        # Mostly English with some Chinese
        assert is_english("This is an English article about AI 机器学习") is True

    def test_empty_string(self) -> None:
        assert is_english("") is False

    def test_no_alpha_chars(self) -> None:
        assert is_english("123 456 789") is False

    def test_short_english(self) -> None:
        assert is_english("Hello World") is True

    def test_chinese_with_english_words(self) -> None:
        assert is_english("这是一个关于AI的中文文章，内容很丰富") is False


class TestTranslateText:
    def test_translate_english_to_chinese(self) -> None:
        result = translate_text("Hello world", source="en", target="zh-CN")
        assert result != "Hello world"  # Should be translated
        assert len(result) > 0

    def test_translate_empty_string(self) -> None:
        assert translate_text("") == ""

    def test_translate_failure_returns_original(self) -> None:
        with patch("infodigest.formatter.translator.GoogleTranslator") as MockTranslator:
            mock = MagicMock()
            mock.translate.side_effect = Exception("API error")
            MockTranslator.return_value = mock
            result = translate_text("Hello", source="en", target="zh-CN")
            assert result == "Hello"  # Returns original on failure

    def test_translate_none_result_returns_original(self) -> None:
        with patch("infodigest.formatter.translator.GoogleTranslator") as MockTranslator:
            mock = MagicMock()
            mock.translate.return_value = None
            MockTranslator.return_value = mock
            result = translate_text("Hello", source="en", target="zh-CN")
            assert result == "Hello"


class TestTranslateEntrySummary:
    def test_english_summary_translated(self) -> None:
        result = translate_entry_summary("New breakthrough in AI research")
        # Should be translated to Chinese
        assert result != "New breakthrough in AI research"

    def test_chinese_summary_unchanged(self) -> None:
        original = "这是一个中文摘要"
        result = translate_entry_summary(original)
        assert result == original

    def test_empty_summary(self) -> None:
        assert translate_entry_summary("") == ""

    def test_short_english_translated(self) -> None:
        result = translate_entry_summary("AI model update")
        # Should attempt translation
        assert isinstance(result, str)
        assert len(result) > 0


class TestTranslationIntegration:
    def test_real_translation(self) -> None:
        """Test with actual Google Translate API."""
        result = translate_text(
            "The new language model achieves state-of-the-art performance on multiple benchmarks.",
            source="en",
            target="zh-CN",
        )
        assert result  # Should have content
        assert result != "The new language model achieves state-of-the-art performance on multiple benchmarks."
