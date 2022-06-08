# flake8: noqa
from abc import ABCMeta, abstractproperty
from typing import Optional, Type, TypeVar

from takumi.events import Log
from takumi.extensions import db
from takumi.services.exceptions import DirtySubjectInitializationException, ServiceException

T = TypeVar("T", bound="Service")


class Service(metaclass=ABCMeta):
    LOG: Optional[Type[Log]] = None

    @abstractproperty
    def SUBJECT(self):
        """The type of the instance"""
        pass

    def __init__(self, subject):
        if subject is None:
            raise ServiceException("Can't instanciate a service with empty subject")
        elif not isinstance(subject, self.SUBJECT):
            raise ServiceException(
                'Expected instance of type "{}", but got type "{}"'.format(
                    self.SUBJECT.__name__, subject.__class__.__name__
                )
            )
        elif subject in db.session.dirty:
            raise DirtySubjectInitializationException(
                '"{}" has already been modified. Service initialization needs to contain a non-dirty object'.format(
                    subject
                )
            )

        self._subject = subject
        self._log = self.LOG(subject) if self.LOG else None

    @property
    def subject(self):
        return self._subject

    @property
    def log(self):
        return self._log

    def __enter__(self: T) -> T:
        return self

    def __exit__(self, exc_type, _exc_value, _traceback):
        if exc_type is not None:
            return False
        db.session.add(self.subject)
        db.session.commit()


from .advertiser import AdvertiserService
from .advertiser_config import AdvertiserConfigService
from .advertiser_industry import AdvertiserIndustryService
from .audience_insight import AudienceInsightService
from .audit import AuditService
from .campaign import CampaignService
from .device import DeviceService
from .facebook import FacebookService
from .gig import GigService
from .influencer import InfluencerService
from .insight import InsightService
from .instagram_account import InstagramAccountService
from .instagram_post import InstagramPostService
from .instagram_post_comment import InstagramPostCommentService
from .instagram_reel import InstagramReelService
from .instagram_story import InstagramStoryService
from .media import MediaService
from .offer import OfferService
from .payment import PaymentService
from .payment_authorization import PaymentAuthorizationService
from .post import PostService
from .region import RegionService
from .targeting import TargetingService
from .tax_form import FormNumber, TaxFormService
from .tiktok_account import TikTokAccountService
from .tiktok_post import TiktokPostService
from .user import UserService
