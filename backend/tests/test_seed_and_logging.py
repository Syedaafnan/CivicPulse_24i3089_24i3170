import json
import logging

from app.logging_setup import JsonFormatter, request_id_var
from app.repositories.complaint_repository import ComplaintRepository
from app.seed import SEEDS, run_seed


def test_seed_is_idempotent_and_varied(container):
    with container.repository() as repo:
        first = run_seed(repo)
    with container.repository() as repo:
        second = run_seed(repo)
        agg = repo.aggregates()
    assert first == len(SEEDS) >= 30
    assert second == 0
    assert agg.total == len(SEEDS)
    assert len([c for c, n in agg.by_category.items() if n > 0]) >= 5


def test_json_log_line_carries_request_id():
    token = request_id_var.set("req-42")
    try:
        record = logging.LogRecord("x", logging.WARNING, __file__, 1, "triage fallback", None, None)
        record.provider = "llm:groq"
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "req-42" and line["provider"] == "llm:groq" and line["level"] == "WARNING"


def test_repository_list_orders_newest_first(container):
    from app.repositories.complaint_repository import ComplaintFilters

    with container.repository() as repo:
        run_seed(repo)
    with container.repository() as repo:
        items, total = ComplaintRepository.list(repo, ComplaintFilters(), 1, 5)
    assert total == len(SEEDS)
    assert items[0].created_at >= items[-1].created_at
