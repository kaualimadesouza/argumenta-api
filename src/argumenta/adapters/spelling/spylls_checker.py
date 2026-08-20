import re
from functools import lru_cache
from importlib import resources

from spylls.hunspell import Dictionary

from argumenta.domain.evaluation import SpellingAnchor

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿ]+)*")


@lru_cache(maxsize=1)
def _dictionary() -> Dictionary:
    """Loaded once per process (a few seconds); vendored VERO pt_BR."""
    base = resources.files("argumenta.adapters.spelling") / "dictionaries" / "pt_BR"
    return Dictionary.from_files(str(base))


class SpyllsSpellChecker:
    """Deterministic pt-BR detection layer: flags words the dictionary does not
    know, with exact spans; classification and suggestions are the LLM's job.

    Capitalized words mid-text are skipped (proper nouns such as character
    names are not in the dictionary); the LLM still sees the full text.
    """

    def find_unknown_words(self, text: str) -> tuple[SpellingAnchor, ...]:
        dictionary = _dictionary()
        anchors: list[SpellingAnchor] = []
        for match in _WORD.finditer(text):
            word = match.group()
            if word[0].isupper():
                continue
            if dictionary.lookup(word):
                continue
            anchors.append(
                SpellingAnchor(word=word, span_start=match.start(), span_end=match.end())
            )
        return tuple(anchors)
