# encoding=utf-8
import datetime as dt

from takumi.models import Influencer


def test_influencer_has_w9_info_false_if_this_year_not_submitted(influencer: Influencer):
    influencer.w9_tax_years_submitted = []

    assert not influencer.has_w9_info()


def test_influencer_has_w9_info_true_if_this_year_submitted(influencer: Influencer):
    influencer.w9_tax_years_submitted = [dt.datetime.now().year]

    assert influencer.has_w9_info()
