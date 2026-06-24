"""Harness doc index for Agent Window."""

from meris.ui.harness_data import list_harness_docs_for_ui, read_harness_doc_for_ui


def test_list_harness_docs_for_ui() -> None:
    docs = list_harness_docs_for_ui()
    assert len(docs) >= 5
    ids = {d["id"] for d in docs}
    assert "routing" in ids
    assert all(d.get("available") == "true" for d in docs)


def test_read_harness_doc_routing() -> None:
    doc = read_harness_doc_for_ui("routing")
    assert doc is not None
    assert "routing" in doc["content"].lower() or "路由" in doc["content"]
    assert doc["path"] == "docs/harness/routing.md"
