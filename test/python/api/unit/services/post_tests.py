import pytest

from takumi.gql.mutation.post import BriefSectionType
from takumi.services import PostService
from takumi.services.exceptions import ServiceException
from takumi.services.post import BRIEF_TYPES
from takumi.services.post.utils import _href_items, _replace_nbsp, _strip_edges


def test_set_post_brief_validates_values(app, post):
    brief = [
        {"type": "heading", "value": "heading value", "extra": "to be ignored"},
        {"type": "sub_heading", "value": "sub heading value", "extra": "to be ignored"},
        {"type": "paragraph", "value": "some paragraph", "items": "to be ignored"},
        {"type": "important", "value": "important text", "items": "to be ignored"},
        {"type": "divider", "value": "divider has no value"},
        {
            "type": "dos_and_donts",
            "value": "not used",
            "dos": ["do", "do more"],
            "donts": ["do", "not", "do"],
        },
        {"type": "unordered_list", "value": "no value", "items": ["dont", "count", "on", "me"]},
        {"type": "ordered_list", "value": "no value", "items": ["do", "count", "on", "me"]},
    ]
    post.brief = []

    PostService(post).update_brief(brief)

    assert post.brief == [
        {"type": "heading", "value": "heading value"},
        {"type": "sub_heading", "value": "sub heading value"},
        {"type": "paragraph", "value": "some paragraph"},
        {"type": "important", "value": "important text"},
        {"type": "divider"},
        {"type": "dos_and_donts", "dos": ["do", "do more"], "donts": ["do", "not", "do"]},
        {"type": "unordered_list", "items": ["dont", "count", "on", "me"]},
        {"type": "ordered_list", "items": ["do", "count", "on", "me"]},
    ]


def test_set_post_brief_raises_if_invalid_section(app, post):
    with pytest.raises(ServiceException, match="Invalid brief section type: foo"):
        PostService(post).update_brief([{"type": "foo", "value": "erm"}])


def test_set_post_brief_raises_if_section_missing_defined_value(app, post):
    with pytest.raises(ServiceException, match="'dos' is missing"):
        PostService(post).update_brief([{"type": "dos_and_donts", "value": "Do things"}])


def test_brief_types_match_gql_types(app):
    graphq_types = {
        enum.value for key, enum in BriefSectionType.__dict__.items() if not key.startswith("_")
    }
    service_types = set(BRIEF_TYPES.keys())

    assert graphq_types == service_types


def test_set_post_brief_strips_whitespace_from_section_values_and_items(app, post):
    brief = [
        {"type": "heading", "value": " prefix"},
        {"type": "heading", "value": "postfix "},
        {"type": "heading", "value": " both "},
        {
            "type": "dos_and_donts",
            "dos": [" prefix", "postfix ", " both "],
            "donts": [" prefix", "postfix ", " both "],
        },
        {"type": "ordered_list", "items": [" prefix", "postfix ", " both "]},
    ]
    post.brief = []

    PostService(post).update_brief(brief)

    assert post.brief == [
        {"type": "heading", "value": "prefix"},
        {"type": "heading", "value": "postfix"},
        {"type": "heading", "value": "both"},
        {
            "type": "dos_and_donts",
            "dos": ["prefix", "postfix", "both"],
            "donts": ["prefix", "postfix", "both"],
        },
        {"type": "ordered_list", "items": ["prefix", "postfix", "both"]},
    ]


def test_set_post_brief_strips_br_tags_from_section_values_and_items(app, post):
    brief = [
        {"type": "heading", "value": "<br>prefix"},
        {"type": "heading", "value": "postfix<br>"},
        {"type": "heading", "value": "<br>both<br>"},
        {
            "type": "dos_and_donts",
            "dos": ["<br>prefix", "postfix<br>", "<br>both<br>"],
            "donts": ["<br>prefix", "postfix<br>", "<br>both<br>"],
        },
        {"type": "ordered_list", "items": ["<br>prefix", "postfix<br>", "<br>both<br>"]},
    ]

    post.brief = []

    PostService(post).update_brief(brief)

    assert post.brief == [
        {"type": "heading", "value": "prefix"},
        {"type": "heading", "value": "postfix"},
        {"type": "heading", "value": "both"},
        {
            "type": "dos_and_donts",
            "dos": ["prefix", "postfix", "both"],
            "donts": ["prefix", "postfix", "both"],
        },
        {"type": "ordered_list", "items": ["prefix", "postfix", "both"]},
    ]


def test_custom_strip_spaces(app):
    assert _strip_edges("foo") == "foo"
    assert _strip_edges("foo ") == "foo"
    assert _strip_edges("foo     ") == "foo"
    assert _strip_edges(" foo ") == "foo"
    assert _strip_edges("   foo") == "foo"
    assert _strip_edges("   foo    ") == "foo"
    assert _strip_edges("foo bar baz") == "foo bar baz"


def test_custom_strip_tags(app):
    assert _strip_edges("<br>foo") == "foo"
    assert _strip_edges("foo<br>") == "foo"
    assert _strip_edges("<br>foo<br>") == "foo"
    assert _strip_edges("<br><br>foo<br>") == "foo"
    assert _strip_edges("<br><br>foo<br><br>") == "foo"


def test_custom_strip_mixed(app):
    assert _strip_edges("<br><br> foo<br><br>") == "foo"
    assert _strip_edges(" <br>    <br> foo<br><br>") == "foo"
    assert _strip_edges("<br><br> foo     <br><br>") == "foo"
    assert _strip_edges("<br>  <br> foo     <br>  <br>") == "foo"


def test_replace_nbsp(app):
    assert _replace_nbsp("foo:&nbsp;bar") == "foo: bar"


def test_href_items_mention(app):
    result = _href_items("foo @bar baz")
    expected = 'foo <a href="https://www.instagram.com/bar/">@bar</a> baz'

    assert result == expected
    result = _href_items(result)

    assert result == expected

    # Edge cases
    assert _href_items("a@b") == 'a<a href="https://www.instagram.com/b/">@b</a>'
    assert _href_items("@a@b") == (
        '<a href="https://www.instagram.com/a/">@a</a>'
        '<a href="https://www.instagram.com/b/">@b</a>'
    )
    assert _href_items("@b") == '<a href="https://www.instagram.com/b/">@b</a>'
    assert _href_items("@@b") == '@<a href="https://www.instagram.com/b/">@b</a>'
    assert _href_items("@@b@") == '@<a href="https://www.instagram.com/b/">@b</a>@'
    assert _href_items("\n@b\n") == '\n<a href="https://www.instagram.com/b/">@b</a>\n'
    assert _href_items("@") == "@"


def test_href_items_hashtag(app):
    result = _href_items("foo #bar baz")
    expected = 'foo <a href="https://www.instagram.com/explore/tags/bar/">#bar</a> baz'

    assert result == expected
    result = _href_items(result)

    assert result == expected

    # Edge cases
    assert _href_items("a#b") == 'a<a href="https://www.instagram.com/explore/tags/b/">#b</a>'
    assert _href_items("#a#b") == (
        '<a href="https://www.instagram.com/explore/tags/a/">#a</a>'
        '<a href="https://www.instagram.com/explore/tags/b/">#b</a>'
    )
    assert _href_items("#b") == '<a href="https://www.instagram.com/explore/tags/b/">#b</a>'
    assert _href_items("##b") == '#<a href="https://www.instagram.com/explore/tags/b/">#b</a>'
    assert _href_items("##b#") == '#<a href="https://www.instagram.com/explore/tags/b/">#b</a>#'
    assert _href_items("\n#b\n") == '\n<a href="https://www.instagram.com/explore/tags/b/">#b</a>\n'
    assert _href_items("#") == "#"


def test_href_urls(app):
    result = _href_items("foo https://takumi.com bar")
    expected = 'foo <a href="https://takumi.com">https://takumi.com</a> bar'

    assert result == expected
    result = _href_items(result)

    assert result == expected

    # Edge cases
    assert (
        _href_items("https://takumi.com") == '<a href="https://takumi.com">https://takumi.com</a>'
    )


def test_href_items_not_required(app):
    assert (
        _href_items('foo <a href="https://www.instagram.com/bar/">@bar</a> baz')
        == 'foo <a href="https://www.instagram.com/bar/">@bar</a> baz'
    )


def test_href_items_fixes_spaces_in_tags(app):
    assert (
        _href_items('foo <a href="https://www.instagram.com/bar/">@bar </a>baz')
        == 'foo <a href="https://www.instagram.com/bar/">@bar</a> baz'
    )
    assert (
        _href_items('foo<a href="https://www.instagram.com/bar/"> @bar </a>baz')
        == 'foo <a href="https://www.instagram.com/bar/">@bar</a> baz'
    )
    assert (
        _href_items('foo<a href="https://www.instagram.com/bar/"> @bar</a> baz')
        == 'foo <a href="https://www.instagram.com/bar/">@bar</a> baz'
    )

    assert _href_items("<b> foo bar</b>") == " <b>foo bar</b>"
    assert _href_items("<b> foo bar </b>") == " <b>foo bar</b> "
    assert _href_items("<b>foo bar </b>") == "<b>foo bar</b> "
