from takumi.ocr.block import Block
from takumi.ocr.documents.post import PostDocument
from takumi.ocr.fields import HEADER_ANCHOR


def _get_test_header(likes="1.2k", comments="123", shares="5", bookmarks="0"):
    def _get_block(text, top, left):
        return Block(
            {
                "Id": "id",
                "Text": text,
                "Geometry": {
                    "BoundingBox": {"Top": top, "Left": left, "Height": 0.1, "Width": 0.1}
                },
                "Confidence": 99.5,
            }
        )

    return [
        _get_block(likes, 1, 1),
        _get_block(comments, 1, 2),
        _get_block(shares, 1, 3),
        _get_block(bookmarks, 1, 4),
        _get_block(HEADER_ANCHOR.english, 1, 1),
    ]


def test_parse_header_normal_numbers():
    document = PostDocument("path/to/doc")
    document.blocks = _get_test_header(likes="123")

    result = list(document._parse_header())
    assert result[0] == ("likes", 123, 99.5)


def test_parse_header_whole_k_numbers():
    document = PostDocument("path/to/doc")
    document.blocks = _get_test_header(likes="2k")

    result = list(document._parse_header())
    assert result[0] == ("likes", 2000, 99.5)


def test_parse_header_fraction_k_numbers():
    document = PostDocument("path/to/doc")
    document.blocks = _get_test_header(likes="2.3k")

    result = list(document._parse_header())
    assert result[0] == ("likes", 2300, 99.5)


def test_parse_header_with_space_and_comma():
    document = PostDocument("path/to/doc")
    document.blocks = _get_test_header(likes="2,3 Tsd.")

    result = list(document._parse_header())
    assert result[0] == ("likes", 2300, 99.5)
