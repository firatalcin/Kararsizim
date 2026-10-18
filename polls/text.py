"""Cleaning and comparing user-written poll text."""

import unicodedata

# Zero-width and bidirectional-control characters make text look different from what it is
# (blank-looking polls, spoofed look-alike options). ZWJ/ZWNJ are kept: emoji sequences such as
# family and flag emoji need them.
_INVISIBLE = dict.fromkeys(
    map(
        ord,
        "​⁠﻿"  # zero-width space, word joiner, BOM
        "‎‏؜"  # LRM, RLM, Arabic letter mark
        "‪‫‬‭‮"  # embeddings and overrides
        "⁦⁧⁨⁩",  # isolates
    )
)
_NOT_VISIBLE = {"Cc", "Cf", "Zs", "Zl", "Zp"}


def clean_text(value, multiline=False):
    """NFC-normalise, drop invisible look-alike characters and tidy the whitespace."""
    value = unicodedata.normalize("NFC", value).translate(_INVISIBLE)
    return value.strip() if multiline else " ".join(value.split())


def has_visible_text(value):
    """True if at least one character actually shows up (not whitespace, joiners or controls)."""
    return any(unicodedata.category(char) not in _NOT_VISIBLE for char in value)


def fold_key(value):
    """Comparison key for "the same text": case-insensitive, with Turkish dotted/dotless i alike."""
    return value.casefold().replace("i̇", "i").replace("ı", "i")
