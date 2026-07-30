"""Conservative validation for Latin and Devanagari/Nepali plate text."""

from __future__ import annotations

import re
import unicodedata


class PlateValidator:
    _allowed = re.compile(r"^[A-Z0-9\u0900-\u097F ]+$")
    _spaces = re.compile(r"\s+")

    def normalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text or "").upper()
        normalized = re.sub(r"[^A-Z0-9\u0900-\u097F]+", " ", normalized)
        return self._spaces.sub(" ", normalized).strip()

    def validate(self, text: str) -> tuple[bool, str]:
        normalized = self.normalize(text)
        compact = normalized.replace(" ", "")
        if not 4 <= len(compact) <= 18 or not self._allowed.fullmatch(normalized):
            return False, normalized
        has_digit = any(character.isdigit() for character in compact)
        has_letter = any(character.isalpha() for character in compact)
        if not has_digit or not has_letter:
            return False, normalized
        return True, normalized

