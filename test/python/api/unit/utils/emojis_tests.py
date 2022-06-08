from takumi.utils.emojis import find_emojis, remove_emojis


def test_find_emojis_with_basic_emojis():
    text = "A turtle playing a saxaphone: 🎷🐢"
    emojis = find_emojis(text)

    assert emojis == ["🎷", "🐢"]


def test_find_emojis_multiple():
    text = "A group of 🐑 is called a flock 🐑🐑 baah 🐑"
    emojis = find_emojis(text)

    assert emojis == ["🐑", "🐑", "🐑", "🐑"]


def test_find_emojis_complex():
    text = "When a 👨 and 👩 have a family they become 👨‍👩‍👧"
    emojis = find_emojis(text)

    assert emojis == ["👨", "👩", "👨‍👩‍👧"]


def test_find_emojis_fitzpatrick():
    text = "Merry christmas! 🎅🏻🎅🏼🎅🏽🎅🏾🎅🏿"
    emojis = find_emojis(text)

    assert emojis == [
        "🎅🏻",
        "🎅🏼",
        "🎅🏽",
        "🎅🏾",
        "🎅🏿",
    ]


def test_find_emojis_flags():
    text = "In 🇮🇸 there are a total of 13 🎅🏻"
    emojis = find_emojis(text)

    assert emojis == ["🇮🇸", "🎅🏻"]


def test_remove_emojis_with_basic_emojis():
    text = "A turtle playing a saxaphone: 🎷🐢"
    out = remove_emojis(text)

    assert out == "A turtle playing a saxaphone: "


def test_remove_emojis_multiple():
    text = "A group of 🐑 is called a flock 🐑🐑 baah 🐑"
    out = remove_emojis(text)

    assert out == "A group of  is called a flock  baah "


def test_remove_emojis_complex():
    text = "When a 👨 and 👩 have a family they become 👨‍👩‍👧"
    out = remove_emojis(text)

    assert out == "When a  and  have a family they become "


def test_remove_emojis_fitzpatrick():
    text = "Merry christmas! 🎅🏻🎅🏼🎅🏽🎅🏾🎅🏿"
    out = remove_emojis(text)

    assert out == "Merry christmas! "


def test_remove_emojis_flags():
    text = "In 🇮🇸 there are a total of 13 🎅🏻"
    out = remove_emojis(text)

    assert out == "In  there are a total of 13 "
