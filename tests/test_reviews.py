"""
Tests for human review queue helpers.
"""


def test_review_queue_create_list_resolve(mock_db_path):
    from servers.reviews import (
        create_review_item,
        get_review_item,
        list_review_items,
        resolve_review_item,
    )

    review_id = create_review_item(
        kind="guardrail",
        reason="Command requires approval",
        project="test",
        severity="high",
        trace_id="trace-1",
        span_id="span-1",
        payload={"allowed": False},
    )

    duplicate = create_review_item(
        kind="guardrail",
        reason="Command requires approval",
        project="test",
        severity="high",
        trace_id="trace-1",
        span_id="span-1",
    )
    assert duplicate == review_id

    items = list_review_items(project="test")
    assert len(items) == 1
    assert items[0]["payload"] == {"allowed": False}

    resolved = resolve_review_item(
        review_id,
        reviewer="alice",
        resolution="approved",
        notes="Reviewed manually",
    )
    assert resolved["status"] == "resolved"
    assert resolved["reviewer"] == "alice"
    assert get_review_item(review_id)["resolution"] == "approved"


def test_enqueue_trace_reviews(mock_db_path):
    from servers.reviews import enqueue_trace_reviews, list_review_items
    from servers.tracing import finish_span, start_span, start_trace

    trace_id = start_trace("review trace", project="test")
    span_id = start_span(trace_id, "guardrail:Bash", "guardrail")
    finish_span(
        span_id,
        status="warning",
        output={
            "allowed": False,
            "violations": [{"message": "Command matches denied pattern: rm -rf*"}],
        },
    )

    result = enqueue_trace_reviews(trace_id)
    assert result["created_count"] == 1

    items = list_review_items(project="test")
    assert len(items) == 1
    assert items[0]["trace_id"] == trace_id
    assert items[0]["span_id"] == span_id
