from takumi.utils import translations


def test_check_for_missing_translations(app, monkeypatch):
    languages = translations.get_available_translations()
    missing_translations = translations.get_missing_translations()

    missing_str = ""

    if missing_translations != {lang: [] for lang in languages}:
        for lang, messages in missing_translations.items():
            for message in messages:
                missing_str += lang.upper() + ": " + repr(message)
                missing_str += "\n"
            missing_str += "\n"

    assert missing_str == ""
