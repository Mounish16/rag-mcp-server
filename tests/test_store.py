def test_search_ranks_the_relevant_chunk_first(indexed_store):
    hits = indexed_store.search("What is on Deck 2? Laboratories", top_k=3)
    assert hits[0]["source"] == "manuals/blueprint_notes.txt"
    assert "Laboratories" in hits[0]["text"]
    assert [h["citation"] for h in hits] == ["[1]", "[2]", "[3]"]


def test_search_can_be_limited_to_one_source(indexed_store):
    hits = indexed_store.search("crew", top_k=5, source="crew/crew_profiles.json")
    assert hits and {h["source"] for h in hits} == {"crew/crew_profiles.json"}


def test_search_on_empty_index_returns_nothing(empty_store):
    assert empty_store.search("anything") == []


def test_get_chunk_found_and_missing(indexed_store):
    found = indexed_store.get_chunk("manuals/blueprint_notes.txt", 0)
    assert found and found["chunk"] == 0 and "Deck" in found["text"]
    assert indexed_store.get_chunk("manuals/blueprint_notes.txt", 9999) is None
    assert indexed_store.get_chunk("nope.txt", 0) is None


def test_sources_and_stats_agree(indexed_store):
    sources = indexed_store.list_sources()
    stats = indexed_store.stats()
    assert stats["sources"] == len(sources) > 0
    assert stats["chunks"] == sum(s["chunks"] for s in sources) == indexed_store.count()
