"""Unit tests for custom template tags/filters in registry_tags."""

from apps.submissions.templatetags.registry_tags import linkify_description


class TestLinkifyDescriptionFilter:
    """Tests for the linkify_description template filter."""

    def test_empty_string(self):
        assert linkify_description("") == ""

    def test_none_is_handled(self):
        assert linkify_description(None) == ""

    def test_plain_text_passes_through(self):
        result = linkify_description("Hello world.")
        assert "Hello world." in result

    def test_bare_url_is_linked(self):
        result = linkify_description("See https://www.denbi.de for details.")
        assert 'href="https://www.denbi.de"' in result

    def test_markdown_link_renders_named_anchor(self):
        result = linkify_description("See [de.NBI](https://www.denbi.de) for details.")
        assert 'href="https://www.denbi.de"' in result
        assert ">de.NBI<" in result

    def test_markdown_link_text_is_escaped(self):
        result = linkify_description("[<evil>](https://example.com)")
        assert "<evil>" not in result
        assert "&lt;evil&gt;" in result

    def test_markdown_link_url_is_escaped(self):
        # URL with a quote should be escaped
        result = linkify_description('[text](https://example.com/?a="b")')
        assert '="b"' not in result

    def test_non_http_url_not_linked_as_markdown(self):
        # javascript: scheme must never appear as an href — only http/https are matched
        result = linkify_description("[click](javascript:alert(1))")
        assert 'href="javascript' not in result

    def test_raw_html_is_escaped(self):
        result = linkify_description('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_double_newline_produces_multiple_paragraphs(self):
        result = linkify_description("First.\n\nSecond.")
        assert result.count("<p>") == 2
        assert "First." in result
        assert "Second." in result

    def test_single_newline_produces_br(self):
        result = linkify_description("Line one.\nLine two.")
        assert "<br>" in result
        assert "Line one." in result
        assert "Line two." in result

    def test_single_paragraph_wrapped_in_p(self):
        result = linkify_description("Just one paragraph.")
        assert result.startswith("<p>")
        assert result.endswith("</p>")

    def test_markdown_and_bare_url_in_same_description(self):
        result = linkify_description(
            "[Guide](https://example.com/guide) or visit https://example.com/home"
        )
        assert 'href="https://example.com/guide"' in result
        assert 'href="https://example.com/home"' in result
        assert ">Guide<" in result
