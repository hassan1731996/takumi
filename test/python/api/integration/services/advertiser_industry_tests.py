from takumi.models import AdvertiserIndustry
from takumi.services import AdvertiserIndustryService


def test_get_all_advertiser_industry_tree(db_session):
    advertiser_industries = AdvertiserIndustryService.get_industry_tree()
    titles_advertiser_industries = list(map(lambda x: x.title, advertiser_industries))

    expected_advertiser_industries = AdvertiserIndustry.query.filter(
        AdvertiserIndustry.parent_id == None
    ).all()
    titles_expected_advertiser_industries = list(
        map(lambda x: x.title, expected_advertiser_industries)
    )

    assert advertiser_industries != []
    assert titles_advertiser_industries == titles_expected_advertiser_industries


def test_get_advertiser_industries_by_advertiser_id(db_advertiser):
    advertiser_industry = AdvertiserIndustry.query.filter_by(title="Energy drinks").first()
    AdvertiserIndustryService.add_advertiser_industry_to_advertiser(
        db_advertiser.id, advertiser_industry.id
    )

    specific_advertiser_industries = (
        AdvertiserIndustryService.get_advertiser_industries_by_advertiser_id(db_advertiser.id)
    )
    assert len(specific_advertiser_industries) >= 0
    assert advertiser_industry in specific_advertiser_industries


def test_check_if_advertiser_has_advertiser_industry_true(db_session, db_advertiser):
    advertiser_industry = AdvertiserIndustry.query.filter_by(title="Personal accessories").first()
    advertiser_industry.advertisers.append(db_advertiser)
    db_session.commit()

    assert (
        AdvertiserIndustryService.check_if_advertiser_has_advertiser_industry(
            db_advertiser.id, advertiser_industry.id
        )
        is True
    )


def test_check_if_advertiser_has_advertiser_industry_false(db_advertiser):
    advertiser_industry = AdvertiserIndustry.query.filter_by(title="Personal accessories").first()

    assert (
        AdvertiserIndustryService.check_if_advertiser_has_advertiser_industry(
            db_advertiser.id, advertiser_industry.id
        )
        is False
    )


def test_add_advertiser_industry_to_advertiser(db_advertiser):
    advertiser_industry = AdvertiserIndustry.query.filter_by(title="Convenience retail").first()

    AdvertiserIndustryService.add_advertiser_industry_to_advertiser(
        db_advertiser.id, advertiser_industry.id
    )

    expected_advertiser_industry = AdvertiserIndustry.query.filter(
        AdvertiserIndustry.id == advertiser_industry.id,
        AdvertiserIndustry.advertisers.contains(db_advertiser),
    ).first()

    assert expected_advertiser_industry.id == advertiser_industry.id
    assert expected_advertiser_industry.title == advertiser_industry.title
    assert expected_advertiser_industry in db_advertiser.advertiser_industries


def test_remove_advertiser_industry_from_advertiser(db_advertiser):
    advertiser_industry = AdvertiserIndustry.query.filter_by(
        title="Radio stations, services"
    ).first()
    AdvertiserIndustryService.add_advertiser_industry_to_advertiser(
        db_advertiser.id, advertiser_industry.id
    )

    assert advertiser_industry in db_advertiser.advertiser_industries

    AdvertiserIndustryService.remove_advertiser_industry_from_advertiser(
        db_advertiser.id, advertiser_industry.id
    )

    assert (
        advertiser_industry
        not in AdvertiserIndustryService.get_advertiser_industries_by_advertiser_id(
            db_advertiser.id
        )
    )
    assert db_advertiser not in advertiser_industry.advertisers
    assert advertiser_industry not in db_advertiser.advertiser_industries
