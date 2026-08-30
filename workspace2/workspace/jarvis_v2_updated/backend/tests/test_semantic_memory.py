from app.memory.semantic_search import SemanticIndex


def test_semantic_search_ranks_relevant_fact_first():
    index = SemanticIndex()
    index.build(
        {
            "fact1": "The user prefers tea in the morning, not coffee.",
            "fact2": "The user's meeting with the design team is on Tuesdays.",
            "fact3": "The user's favorite programming language is Python.",
        }
    )
    results = index.search("what does the user like to drink", top_k=1)
    assert len(results) == 1
    assert results[0]["key"] == "fact1"


def test_semantic_search_returns_empty_for_empty_index():
    index = SemanticIndex()
    index.build({})
    assert index.search("anything") == []


def test_semantic_search_respects_top_k():
    index = SemanticIndex()
    index.build({f"fact{i}": f"Python fact number {i} about programming" for i in range(5)})
    results = index.search("python programming", top_k=2)
    assert len(results) == 2
