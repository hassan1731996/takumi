from takumi.utils.instagram import parse_shortcode_from_url


def test_parse_shortcode_from_url_with_instagram_post_url():
    assert parse_shortcode_from_url("https://www.instagram.com/p/BQQNoZSAGGJ") == "BQQNoZSAGGJ"
    assert (
        parse_shortcode_from_url("https://www.instagram.com/p/BQQNoZSAGGJ/?taken-by=absalontakumi")
        == "BQQNoZSAGGJ"
    )
    assert (
        parse_shortcode_from_url("https://www.instagram.com/p/BQQNoZSAGGJ?taken-by=absalontakumi")
        == "BQQNoZSAGGJ"
    )
    assert (
        parse_shortcode_from_url("instagram.com/p/BQQNoZSAGGJ?taken-by=absalontakumi")
        == "BQQNoZSAGGJ"
    )


def test_parse_shortcode_from_url_with_no_match():
    assert parse_shortcode_from_url("http://takumi.com") is None
    assert parse_shortcode_from_url("https://www.instagram.com/takumihq") is None
    assert parse_shortcode_from_url("https://www.instagram.com/p/") is None
