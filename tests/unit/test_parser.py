from email_rag.processing.parser import html_to_text, clean_email_body, get_clean_body


class TestHtmlToText:
    def test_empty_html(self):
        assert html_to_text("") == ""
        assert html_to_text("   ") == ""

    def test_plain_html(self):
        result = html_to_text("<p>Hello world</p>")
        assert "Hello world" in result

    def test_strips_scripts_and_styles(self):
        html = "<html><style>body{color:red}</style><script>alert(1)</script><p>Content</p></html>"
        result = html_to_text(html)
        assert "Content" in result
        assert "alert" not in result
        assert "color" not in result

    def test_converts_links(self):
        html = '<a href="https://example.com">Click here</a>'
        result = html_to_text(html)
        assert "Click here" in result
        assert "https://example.com" in result

    def test_converts_lists(self):
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = html_to_text(html)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_nested_html(self):
        html = "<div><p>Paragraph 1</p><div><p>Nested</p></div></div>"
        result = html_to_text(html)
        assert "Paragraph 1" in result
        assert "Nested" in result


class TestCleanEmailBody:
    def test_empty(self):
        assert clean_email_body("") == ""

    def test_normalizes_whitespace(self):
        text = "Hello\r\n\r\n\r\n\r\nWorld"
        result = clean_email_body(text)
        assert "\r" not in result
        assert "\n\n\n" not in result

    def test_strips_signature_at_end(self):
        text = "Main content here.\n\n\n\n\n\n\n\n\n--\nJohn Doe\nSenior Engineer"
        result = clean_email_body(text, strip_signatures=True)
        assert "Main content" in result
        assert "Senior Engineer" not in result


class TestGetCleanBody:
    def test_prefers_text_over_html(self):
        result = get_clean_body("Plain text body", "<p>HTML body</p>")
        assert "Plain text body" in result

    def test_falls_back_to_html(self):
        result = get_clean_body("", "<p>HTML body</p>")
        assert "HTML body" in result

    def test_empty_both(self):
        assert get_clean_body("", "") == ""
