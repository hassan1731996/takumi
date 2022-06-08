from takumi.gql.types.post import Post


def test_post_brief_fallback(post):
    post.instructions = "\n".join(
        [
            "This is a post instructions",
            "It can have new lines",
            "",
            "And sometimes simulated paragraphs with",
            "Multiple new lines",
            "",
            "",
            "2+ newlines should be",
            "",
            "",
            "",
            "treated like a",
            "",
            "",
            "",
            "",
            "single paragraph space",
        ]
    )
    post.brief = None

    brief = Post.resolve_brief(post, "info")

    assert len(brief) == 8
    assert brief[0] == {"type": "heading", "value": "Brand Background"}
    assert brief[1] == {"type": "paragraph", "value": "Campaign description"}
    assert brief[2] == {"type": "heading", "value": "Instructions"}
    assert brief[3] == {
        "type": "paragraph",
        "value": "This is a post instructions<br>It can have new lines",
    }
    assert brief[4] == {
        "type": "paragraph",
        "value": "And sometimes simulated paragraphs with<br>Multiple new lines",
    }
    assert brief[5] == {"type": "paragraph", "value": "2+ newlines should be"}
    assert brief[6] == {"type": "paragraph", "value": "treated like a"}
    assert brief[7] == {"type": "paragraph", "value": "single paragraph space"}


def test_post_brief_fallback_strips_empty_lines(post):
    post.instructions = "\n".join(["Foo", "Bar", " ", "Baz", "Qux", " ", "  ", "Norf"])
    post.campaign.description = None
    post.brief = None

    brief = Post.resolve_brief(post, "info")

    assert len(brief) == 4
    assert brief[0] == {"type": "heading", "value": "Instructions"}
    assert brief[1] == {"type": "paragraph", "value": "Foo<br>Bar"}
    assert brief[2] == {"type": "paragraph", "value": "Baz<br>Qux"}
    assert brief[3] == {"type": "paragraph", "value": "Norf"}


def test_post_brief_fallback_returns_brand_background_and_instructions(post):
    post.campaign.description = "\n".join(["foo bar", "", "baz qux", "", "corge grault"])
    post.instructions = "\n".join(["garply waldo", "", "fred plugh", "", "xyzzy thud"])
    post.brief = None

    brief = Post.resolve_brief(post, "info")

    for actual, expected in zip(
        brief,
        [
            {"type": "heading", "value": "Brand Background"},
            {"type": "paragraph", "value": "foo bar"},
            {"type": "paragraph", "value": "baz qux"},
            {"type": "paragraph", "value": "corge grault"},
            {"type": "heading", "value": "Instructions"},
            {"type": "paragraph", "value": "garply waldo"},
            {"type": "paragraph", "value": "fred plugh"},
            {"type": "paragraph", "value": "xyzzy thud"},
        ],
    ):
        assert expected == actual
