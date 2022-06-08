import datetime as dt

from .period import DateTimePeriod, WorkingTimePeriod


class MissingPostDeadlineException(Exception):
    pass


class Periods:
    def __init__(self, locale, brand_safety, extended_review):
        self.submission_period = DateTimePeriod(days=4)
        self.shipping_period = DateTimePeriod(hours=48)
        self.internal_review_period = WorkingTimePeriod(locale=locale, days=1)
        self.post_to_instagram_period = DateTimePeriod(hours=48)

        if brand_safety:
            if extended_review:
                self.min_external_review_period = WorkingTimePeriod(locale=locale, days=5)
            else:
                self.min_external_review_period = WorkingTimePeriod(locale=locale, days=2)
        else:
            self.min_external_review_period = DateTimePeriod(hours=0)


class NoReviewPeriod:
    """
    If the post doesn't require review the influencer
    can submit right up until the deadline.
    """

    def __init__(self):
        self.submission_period = DateTimePeriod(hours=0)
        self.shipping_period = DateTimePeriod(hours=0)
        self.internal_review_period = DateTimePeriod(hours=0)
        self.min_external_review_period = DateTimePeriod(hours=0)
        self.post_to_instagram_period = DateTimePeriod(hours=0)


class PostSchedule:
    def __init__(self, post):
        if not post.deadline:
            raise MissingPostDeadlineException(
                "Can't create a PostSchedule for a post without a deadline"
            )

        self._start = post.campaign.started or dt.datetime.now(dt.timezone.utc)
        self._deadline = post.deadline
        self._shipping_required = post.campaign.shipping_required
        self._submission_deadline = post.submission_deadline

        if post.requires_review_before_posting:
            self.periods = Periods(
                locale=post.campaign.market.default_locale,
                brand_safety=post.campaign.brand_safety,
                extended_review=post.campaign.extended_review,
            )
        else:
            self.periods = NoReviewPeriod()

    @property
    def submission_deadline(self):
        if self._submission_deadline:
            return self._submission_deadline

        return self.suggested_latest_submission_deadline

    @property
    def internal_review_deadline(self):
        return self.periods.internal_review_period.after(self.submission_deadline)

    @property
    def external_review_deadline(self):
        return self.periods.post_to_instagram_period.before(self.post_deadline)

    @property
    def post_deadline(self):
        return self._deadline

    @property
    def suggested_earliest_submission_deadline(self):
        start = self._start

        if self._shipping_required:
            start = self.periods.shipping_period.after(self._start)

        return self.periods.submission_period.after(start)

    @property
    def suggested_latest_submission_deadline(self):
        return self.periods.internal_review_period.before(
            self.periods.min_external_review_period.before(
                self.periods.post_to_instagram_period.before(self.post_deadline)
            )
        )
