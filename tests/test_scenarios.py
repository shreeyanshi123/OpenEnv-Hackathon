from scenarios.registry import _keyword_match_score

def test_keyword_match_score():
    text = "The quick brown fox jumps over the lazy dog"
    assert _keyword_match_score(text, ["quick", "fox"]) == 1.0
    assert _keyword_match_score(text, ["quick", "fox", "cat"]) == 2 / 3
    assert _keyword_match_score("", ["dog"]) == 0.0
    assert _keyword_match_score(text, []) == 0.0
    
    # Case insensitivity check
    assert _keyword_match_score("THE QUICK", ["quick"]) == 1.0
