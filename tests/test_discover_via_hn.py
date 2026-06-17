import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from discover_via_hn import extract_texts_from_tree, find_tokens, GREENHOUSE_URL_RE, ASHBY_URL_RE

# Test nested comment tree extraction
tree = {
    "text": "Top level comment, not relevant",
    "children": [
        {
            "text": "Acme Corp | Backend Engineer | https://job-boards.greenhouse.io/acmecorp/jobs/123",
            "children": [
                {"text": "Reply mentioning https://jobs.ashbyhq.com/widgetco/abc (AI engineer role).", "children": []}
            ],
        },
        {"text": "Unrelated sales role at https://example.com/careers", "children": []},
    ],
}
texts = extract_texts_from_tree(tree)
assert len(texts) == 4

relevant = [t for t in texts if "backend" in t.lower() or "ai" in t.lower()]
gh_tokens = find_tokens(relevant, GREENHOUSE_URL_RE)
ashby_tokens = find_tokens(relevant, ASHBY_URL_RE)
assert gh_tokens == {"acmecorp"}
assert ashby_tokens == {"widgetco"}

# Test trailing punctuation gets stripped
texts2 = ["Check out https://jobs.ashbyhq.com/foobar, great AI team."]
assert find_tokens(texts2, ASHBY_URL_RE) == {"foobar"}

print("ALL HN DISCOVERY TESTS PASSED")
