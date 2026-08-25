from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker


def test_flags_misspelled_words_with_exact_spans() -> None:
    text = "A escola presisa de mais atencao com a excessao dos casos."
    anchors = SpyllsSpellChecker().find_unknown_words(text)

    words = {anchor.word for anchor in anchors}
    assert "presisa" in words
    assert "excessao" in words
    for anchor in anchors:
        assert text[anchor.span_start : anchor.span_end] == anchor.word


def test_accepts_correct_portuguese() -> None:
    text = "a escola precisa de mais atencao, com excecao dos casos raros."
    anchors = SpyllsSpellChecker().find_unknown_words(text)
    words = {anchor.word for anchor in anchors}
    assert "precisa" not in words
    assert "casos" not in words


def test_skips_capitalized_proper_nouns() -> None:
    anchors = SpyllsSpellChecker().find_unknown_words("Dona Marta apoiou o Tenorio.")
    assert anchors == ()
