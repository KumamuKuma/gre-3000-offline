from gre_vocab_app.services.search import SearchService


class FakeContent:
    def __init__(self):
        self.calls = []

    def search(self, query, limit=50):
        self.calls.append((query, limit))
        return list(range(75))


def test_search_trims_delegates_and_caps_results_without_writes():
    content = FakeContent()
    service = SearchService(content)

    assert service.search("   ") == []
    assert content.calls == []
    assert service.search("  abat  ") == list(range(50))
    assert content.calls == [("abat", 50)]

