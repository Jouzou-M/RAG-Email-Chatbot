from datetime import datetime, timezone

from email_rag.rag.retriever import parse_query_filters


class TestQueryFilterParsing:
    def test_sender_email(self):
        filters = parse_query_filters("emails from john@example.com about budget")
        assert filters.sender == "john@example.com"

    def test_sender_name(self):
        filters = parse_query_filters("what did sarah say about the project?")
        # Name-only without "from" keyword won't match
        assert filters.sender is None

    def test_sender_with_from(self):
        filters = parse_query_filters("messages from sarah about project")
        assert filters.sender == "sarah"

    def test_today_filter(self):
        filters = parse_query_filters("what emails did I get today?")
        assert filters.date_after is not None
        assert filters.date_after.date() == datetime.now(timezone.utc).date()

    def test_this_week_filter(self):
        filters = parse_query_filters("emails from this week")
        assert filters.date_after is not None
        # "this" must NOT be captured as a sender name
        assert filters.sender is None

    def test_last_month_filter(self):
        filters = parse_query_filters("show me emails from last month")
        assert filters.date_after is not None
        assert filters.date_before is not None
        # "last" must NOT be captured as a sender name
        assert filters.sender is None

    def test_sent_filter(self):
        filters = parse_query_filters("emails I sent about the proposal")
        assert filters.is_sent is True

    def test_received_filter(self):
        filters = parse_query_filters("emails I received about invoices")
        assert filters.is_sent is False

    def test_no_filters(self):
        filters = parse_query_filters("what is the meaning of life?")
        assert filters.sender is None
        assert filters.date_after is None
        assert filters.date_before is None
        assert filters.is_sent is None
