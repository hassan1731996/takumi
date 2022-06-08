import json
from os import path

import mock
import pytest

from takumi.models import AudienceInsight, AudienceSection, Media
from takumi.ocr import Analysis, analyse_audience_insight, analyse_post_insight
from takumi.ocr.block import Block
from takumi.ocr.documents.audience import (
    AgesMenDocument,
    AgesWomenDocument,
    GenderDocument,
    MissingAgeValues,
    TopLocationsDocument,
)
from takumi.ocr.documents.post import PostDocument
from takumi.ocr.utils import run_ocr


def _get_fixture(name):
    with open(f"{path.dirname(path.realpath(__file__))}/fixtures/{name}.json", "r") as f:
        return json.load(f)


def test_ocr_document_returns_blocks(app, mock_textract, mock_redis_connection):
    mock_textract.detect_document_text.return_value = _get_fixture("german1")
    mock_redis_connection.get.return_value = None

    document = PostDocument(run_ocr("path/to/a/document.png"))

    assert len(document.blocks) == 40  # The german1 fixture
    assert all(isinstance(block, Block) for block in document.blocks)


def test_parse_blocks_finds_reach_correctly(app, mock_textract, mock_redis_connection):
    mock_textract.detect_document_text.return_value = _get_fixture("english-reach-red-green-1")
    mock_redis_connection.get.return_value = None

    document = PostDocument(run_ocr("path/to/a/document.png"))

    parsed = list(document.parse_blocks())

    assert len(parsed) == 12

    assert parsed == [
        ("profile_visits", 19, 99.91044616699219),
        ("follows", 0, 84.05021667480469),
        ("reach", 1646, 99.9513931274414),
        ("impressions", 2314, 99.9544677734375),
        ("from_home_impressions", 1689, 99.94401550292969),
        ("from_hashtags_impressions", 9, 59.71379089355469),
        ("from_other_impressions", 616, 99.88487243652344),
        ("non_followers_reach", 25, 99.83855438232422),
        ("likes", 480, 99.97845458984375),
        ("comments", 13, 99.97089385986328),
        ("shares", 0, 94.39846801757812),
        ("bookmarks", 22, 99.97091674804688),
    ]


def test_parse_blocks_finds_blocks_from_ocr_result_german1(
    app, mock_textract, mock_redis_connection
):
    mock_textract.detect_document_text.return_value = _get_fixture("german1")
    mock_redis_connection.get.return_value = None

    document = PostDocument(run_ocr("path/to/a/document.png"))

    parsed = list(document.parse_blocks())

    assert len(parsed) == 15

    assert parsed == [
        ("profile_visits", 130, 99.97373962402344),
        ("website_clicks", 2, 99.95164489746094),
        ("replies", 5, 99.95914459228516),
        ("follows", 3, 99.79197692871094),
        ("reach", 6070, 99.93186950683594),
        ("impressions", 11363, 99.94482421875),
        ("from_home_impressions", 10176, 98.33045959472656),
        ("from_location_impressions", 98, 99.8531723022461),
        ("from_hashtags_impressions", 100, 99.322998046875),
        ("from_other_impressions", 989, 99.84413146972656),
        ("non_followers_reach", 8, 99.24092102050781),
        ("likes", 1300, 96.81959533691406),
        ("comments", 11, 99.88328552246094),
        ("shares", 3, 99.7276382446289),
        ("bookmarks", 15, 98.62598419189453),
    ]


def test_parse_blocks_finds_blocks_from_ocr_result_english1(
    app, mock_textract, mock_redis_connection
):
    mock_textract.detect_document_text.return_value = _get_fixture("english1")
    mock_redis_connection.get.return_value = None

    document = PostDocument(run_ocr("path/to/a/document.png"))

    parsed = list(document.parse_blocks())

    assert len(parsed) == 14

    assert parsed == [
        ("profile_visits", 402, 99.93370056152344),
        ("emails", 1, 59.92806625366211),
        ("follows", 2, 99.96620178222656),
        ("reach", 13442, 99.89280700683594),
        ("impressions", 19500, 99.94515991210938),
        ("from_explore_impressions", 15, 99.95789337158203),
        ("from_home_impressions", 17463, 99.9088134765625),
        ("from_profile_impressions", 79, 99.91825103759766),
        ("from_other_impressions", 1943, 98.57780456542969),
        ("non_followers_reach", 9, 89.73188781738281),
        ("likes", 2000, 99.6458740234375),
        ("comments", 184, 99.85750579833984),
        ("shares", 76, 99.95767974853516),
        ("bookmarks", 85, 99.89645385742188),
    ]


def test_gender_document_parse_blocks(app, mock_textract, mock_redis_connection):
    mock_textract.detect_document_text.return_value = _get_fixture("english-female_age-gender-1")
    mock_redis_connection.get.return_value = None

    document = GenderDocument(run_ocr("path/to/a/document.png"))

    parsed = list(document.parse_blocks())

    assert len(parsed) == 2

    assert parsed == [("Men", 58, 95.65625762939453), ("Women", 42, 99.56991577148438)]


def test_ages_women_document_parse_blocks(app, mock_textract, mock_redis_connection):
    mock_textract.detect_document_text.return_value = _get_fixture("english-female_age-gender-1")
    mock_redis_connection.get.return_value = None

    document = AgesWomenDocument(run_ocr("path/to/a/document.png"), blue_blocks=mock.Mock())

    with mock.patch.object(AgesWomenDocument, "verify_gender_selected"):
        parsed = list(document.parse_blocks())

    assert len(parsed) == 7

    assert parsed == [
        ("13-17", 0, 92.62252044677734),
        ("18-24", 7, 90.00012969970703),
        ("25-34", 79, 99.81494140625),
        ("35-44", 8, 97.13630676269531),
        ("45-54", 4, 84.66156768798828),
        ("55-64", 1, 87.19963073730469),
        ("65+", 1, 87.40565490722656),
    ]


def test_top_locations_document_parse_blocks(app, mock_textract, mock_redis_connection):
    mock_textract.detect_document_text.return_value = _get_fixture("english-top-location-1")
    mock_redis_connection.get.return_value = None

    document = TopLocationsDocument(run_ocr("path/to/a/document.png"), blue_blocks=mock.Mock())

    with mock.patch.object(TopLocationsDocument, "verify_countries_selected"):
        parsed = list(document.parse_blocks())

    assert parsed == [
        ("Iceland", 57, 99.75390625),
        ("United Kingdom", 9, 92.23200988769531),
        ("United States", 8, 91.94840240478516),
        ("Germany", 4, 87.68328857421875),
        ("Sweden", 3, 92.5203628540039),
    ]


FULL_AUDIENCE_DATA = {
    "english-0": {
        "width": 1080,
        "top_locations": {
            "United States": 24,
            "United Kingdom": 11,
            "Czech Republic": 5,
            "India": 5,
            "Italy": 4,
        },
        "ages_men": {
            "13-17": 4,
            "18-24": 32,
            "25-34": 43,
            "35-44": 14,
            "45-54": 5,
            "55-64": 1,
            "65+": 1,
        },
        "ages_women": {
            "13-17": 2,
            "18-24": 29,
            "25-34": 46,
            "35-44": 16,
            "45-54": 5,
            "55-64": 1,
            "65+": 1,
        },
        "gender": {"Women": 47, "Men": 53},
    },
    "english-1": {
        "width": 828,
        "top_locations": {
            "United Kingdom": 36,
            "United States": 11,
            "Spain": 4,
            "Italy": 4,
            "Brazil": 4,
        },
        "ages_men": {
            "13-17": 1,
            "18-24": 19,
            "25-34": 45,
            "35-44": 25,
            "45-54": 7,
            "55-64": 2,
            "65+": 1,
        },
        "ages_women": {
            "13-17": 2,
            "18-24": 18,
            "25-34": 43,
            "35-44": 25,
            "45-54": 8,
            "55-64": 3,
            "65+": 1,
        },
        "gender": {"Women": 15, "Men": 85},
    },
    "english-2": {
        "width": 750,
        "top_locations": {
            "United Kingdom": 51,
            "United States": 16,
            "Nigeria": 5,
            "Canada": 2,
            "Germany": 1,
        },
        "ages_men": {
            "13-17": 1,
            "18-24": 16,
            "25-34": 51,
            "35-44": 18,
            "45-54": 8,
            "55-64": 2,
            "65+": 4,
        },
        "ages_women": {
            "13-17": 1,
            "18-24": 22,
            "25-34": 55,
            "35-44": 16,
            "45-54": 4,
            "55-64": 1,
            "65+": 1,
        },
        "gender": {"Women": 90, "Men": 10},
    },
    "english-3": {
        "width": 750,
        "top_locations": {
            "United Kingdom": 51,
            "United States": 16,
            "Nigeria": 5,
            "Canada": 2,
            "Germany": 1,
        },
        "ages_men": {
            "13-17": 1,
            "18-24": 16,
            "25-34": 51,
            "35-44": 18,
            "45-54": 8,
            "55-64": 2,
            "65+": 4,
        },
        "ages_women": {
            "13-17": 1,
            "18-24": 22,
            "25-34": 55,
            "35-44": 16,
            "45-54": 4,
            "55-64": 1,
            "65+": 1,
        },
        "gender": {"Women": 90, "Men": 10},
    },
}


@pytest.mark.parametrize("fixture", ["english-0", "english-1", "english-2", "english-3"])
def test_full_audience_insight_block_parsing(
    db_session, db_influencer, mock_textract, mock_redis_connection, fixture
):
    def mock_detect(Document):
        path = Document["S3Object"]["Name"]
        return _get_fixture(path.replace(".jpg", ""))

    mock_textract.detect_document_text = mock_detect
    mock_redis_connection.get.return_value = None

    width = FULL_AUDIENCE_DATA[fixture]["width"]

    insight = AudienceInsight(
        influencer=db_influencer,
        ocr_media_path=f"{fixture}.jpg",
        top_locations=AudienceSection(
            media_path="", media_order=0, media_width=width, media_height=width
        ),
        ages_men=AudienceSection(
            media_path="", media_order=1, media_width=width, media_height=width
        ),
        ages_women=AudienceSection(
            media_path="", media_order=2, media_width=width, media_height=width
        ),
        gender=AudienceSection(media_path="", media_order=3, media_width=width, media_height=width),
    )
    db_session.add(insight)
    db_session.commit()

    result = analyse_audience_insight(insight)

    expected = FULL_AUDIENCE_DATA[fixture]

    for key, ocr_value in result["top_locations"]["values"].items():
        assert expected["top_locations"][key] == ocr_value.value

    for key, ocr_value in result["ages_men"]["values"].items():
        assert expected["ages_men"][key] == ocr_value.value

    for key, ocr_value in result["ages_women"]["values"].items():
        assert expected["ages_women"][key] == ocr_value.value

    for key, ocr_value in result["gender"]["values"].items():
        assert expected["gender"][key] == ocr_value.value


def test_analyse_post_insight_block_parsing(
    db_session, db_influencer, db_post_insight, mock_textract, mock_redis_connection
):
    mock_textract.detect_document_text.return_value = _get_fixture("spanish-post-1")
    mock_redis_connection.get.return_value = None

    db_post_insight.media = [Media(url="http://insight.jpg")]

    result = analyse_post_insight(db_post_insight)

    assert result["profile_visits"].value == 45
    assert result["reach"].value == 1900
    assert result["impressions"].value == 3605
    assert result["from_hashtags_impressions"].value == 19
    assert result["likes"].value == 1100
    assert result["comments"].value == 52
    assert result["shares"].value == 1
    assert result["bookmarks"].value == 9


def test_ages_men_raises_if_missing_values(app, mock_textract, mock_redis_connection):
    mock_textract.detect_document_text.return_value = _get_fixture("gender-men-missing-perc")
    mock_redis_connection.get.return_value = None

    dimensions = {0: (1080, 2151), 1: (1080, 2280), 2: (1080, 2137), 3: (1080, 2220)}
    blocks = Analysis._get_blocks(
        run_ocr("path/to/doc.jpg"), dimensions, mock.Mock(media_order=1, media_width=1080)
    )

    document = AgesMenDocument(blocks=blocks, blue_blocks=mock.Mock())

    with mock.patch.object(AgesMenDocument, "verify_gender_selected"):
        with pytest.raises(MissingAgeValues, match="Unable to find all seven age values"):
            document.get_values()
