# flake8: noqa


class ServiceException(Exception):
    def __init__(self, message, error_code=None, errors=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.errors = errors


# fmt: off
class AdvertiserNotLinkedToFacebookAccountException(ServiceException): pass
class AdvertiserDomainBadFormat(ServiceException): pass
class AlreadyRequestedException(ServiceException): pass
class ApplyFirstException(ServiceException): pass
class ArchivePostException(ServiceException): pass
class BrandArchivedException(ServiceException): pass
class CampaignCompleteException(ServiceException): pass
class CampaignFullyReservedException(ServiceException): pass
class CampaignLaunchException(ServiceException): pass
class CampaignNotFound(ServiceException): pass
class CampaignNotLaunchedException(ServiceException): pass
class CampaignPreviewException(ServiceException): pass
class CampaignPromotionException(ServiceException): pass
class CampaignRequiresRequestForParticipation(ServiceException): pass
class CampaignStashException(ServiceException): pass
class CreateInstagramPostException(ServiceException): pass
class CreatePostException(ServiceException): pass
class DeletingInfluencerSoonerThanScheduledException(ServiceException): pass
class DirtySubjectInitializationException(ServiceException): pass
class EmailNotFoundException(ServiceException): pass
class EnrollException(ServiceException): pass
class FacebookException(ServiceException): pass
class FetchingAudienceInsightsFailed(ServiceException): pass
class FacebookPageNotFoundException(ServiceException): pass
class FacebookNotLinkedException(ServiceException): pass
class FailedPaymentMethodException(ServiceException): pass
class FailedPaymentPermissionException(ServiceException): pass
class ForbiddenException(ServiceException): pass
class GigAlreadyReportedException(ServiceException): pass
class GigAlreadyReviewedException(ServiceException): pass
class GigAlreadySubmittedException(ServiceException): pass
class GigInvalidCaptionException(ServiceException): pass
class GigInvalidStateException(ServiceException): pass
class GigNotFoundException(ServiceException): pass
class GigReportException(ServiceException): pass
class GigResubmissionException(ServiceException): pass
class GigSkipException(ServiceException): pass
class GigUpdateCaptionException(ServiceException): pass
class InfluencerAlreadyExistsException(ServiceException): pass
class InfluencerHairColorNotFound(ServiceException): pass
class InfluencerHairTypeNotFound(ServiceException): pass
class InfluencerEyeColourNotFound(ServiceException): pass
class InfluencerAlreadyScheduledForDeletionException(ServiceException): pass
class InfluencerCannotBeDeletedException(ServiceException): pass
class InfluencerNotEligibleException(ServiceException): pass
class InfluencerNotFound(ServiceException): pass
class InfluencerNotScheduledForDeletionException(ServiceException): pass
class InfluencerOnCooldownForAdvertiserException(ServiceException): pass
class InstagramPostNotFoundException(ServiceException): pass
class InstagramAccountNotFound(ServiceException): pass
class InvalidCampaignStateException(ServiceException): pass
class InvalidConditionsException(ServiceException): pass
class InvalidLoginCodeException(ServiceException): pass
class InvalidMediaDictException(Exception): pass
class InvalidMediaException(ServiceException): pass
class InvalidOfferIdException(ServiceException): pass
class InvalidOfferStateException(ServiceException): pass
class InvalidPasswordException(ServiceException): pass
class InvalidPromptsException(ServiceException): pass
class InvalidRoleException(ServiceException): pass
class InvalidAnswersException(ServiceException): pass
class LocalSessionException(ServiceException): pass
class MediaNotFoundException(ServiceException): pass
class MissingGigImagesException(ServiceException): pass
class NegativePriceException(ServiceException): pass
class NotAStoryPostException(ServiceException): pass
class OfferAlreadyClaimed(ServiceException): pass
class OfferAlreadyExistsException(ServiceException): pass
class OfferAlreadyPaidException(ServiceException): pass
class OfferNotAcceptedException(ServiceException): pass
class OfferNotClaimableException(ServiceException): pass
class OfferNotDispatchableException(ServiceException): pass
class OfferNotFoundException(ServiceException): pass
class OfferNotRejectableException(ServiceException): pass
class OfferNotReservableException(ServiceException): pass
class OfferPushNotificationException(ServiceException): pass
class OfferRewardChangedException(ServiceException): pass
class OrderHasUpdatedException(ServiceException): pass
class PasswordTooShortException(ServiceException): pass
class PaymentAuthorizationSlugNotFoundException(ServiceException): pass
class PaymentRequestFailedException(ServiceException): pass
class PendingPaymentExistsException(ServiceException): pass
class PostNotFoundException(ServiceException): pass
class SendInfluencerMessageError(ServiceException): pass
class SetClaimableException(ServiceException): pass
class StoryFrameAlreadyPartOfAnotherInstagramStoryException(ServiceException): pass
class StoryFrameNotFoundException(ServiceException): pass
class StoryFrameNotMarkedAsPartOfCampaignException(ServiceException): pass
class UnknownMediaFormatException(ServiceException): pass
class UnlinkGigException(ServiceException): pass
class UpdateMediaThumbnailException(ServiceException): pass
class UpdateMediaUrlException(ServiceException): pass
class UpdatePostScheduleException(ServiceException): pass
class UserAlreadyExists(ServiceException): pass
class UserInactiveException(ServiceException): pass
class UserNotFoundException(ServiceException): pass
class UserNotInAdvertiserException(ServiceException): pass
class ValidPaymentAuthorizationAlreadyExists(ServiceException): pass
class IncompleteSignupException(ServiceException): pass
class SignupNotFoundException(ServiceException): pass
class EmailAlreadyExistsException(ServiceException): pass
class ExpiredLoginException(ServiceException): pass
class InvalidLoginException(ServiceException): pass
class BadDataException(ServiceException): pass
class InvalidOTPException(ServiceException): pass
# fmt: on
