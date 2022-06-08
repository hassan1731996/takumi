from takumi.sentiment import SentimentAnalyser


def test_sentiment_analyser_clean_up_text():
    analyser = SentimentAnalyser()

    assert analyser.clean_up_text("hello") == "hello"
    assert analyser.clean_up_text("hello there #ad #follow #me #PLEASE") == "hello there"
    assert analyser.clean_up_text("❤️❤️❤️") == ""
    assert analyser.clean_up_text("hey @djamm I love IT ❤️❤️") == "hey I love IT"
