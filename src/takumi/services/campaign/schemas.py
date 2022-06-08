from takumi.models.campaign import STATES
from takumi.services.validation import ValidationSchema, validators


class CompleteSchema(ValidationSchema):
    state = (
        validators.Equals(STATES.LAUNCHED),
        "Campaign has to be in launched state to be completed. Current state: {}",
    )
    all_claimable = (
        validators.Equals(True),
        "Campaign can not be completed since all offers are not claimable",
    )
    reserved_offers = (
        validators.Length(1, None),
        "Campaign needs at least one reserved offer to be completed",
    )


class StashSchema(ValidationSchema):
    offers = (validators.Length(0, 0), "Unable to stash campaign with offers in it")
    state = (
        validators.OneOf([STATES.DRAFT, STATES.LAUNCHED]),
        "Campaign has to be either in draft of launched state to stash it",
    )


class LaunchSchema(ValidationSchema):
    state = (
        validators.Equals(STATES.DRAFT),
        "Campaign has to be in draft state to be launched. Current state: {}",
    )
    name = validators.Required(), "Campaign needs a `name` in order to be launched"
    pictures = (
        validators.Length(1, None),
        "Campaign needs at least one `picture` in order to be launched",
    )
    posts = validators.Length(1, None), "Campaign needs at least one `post` in order to be launched"
    posts__brief = (
        validators.Length(1, None),
        "Each campaign's post needs a `brief` in order to be launched",
    )
    price = (
        validators.Range(1, None),
        "Campaign can't be launched without a price. Current budget: {}",
    )
    list_price = (
        validators.Range(1, None),
        "Campaign can't be launched without a list price. Current budget: {}",
    )
    targeting__regions = (
        validators.Length(1, None),
        "Campaign needs at least one `targeting region` in order to be launched",
    )
    posts__gallery_photo_count = (
        validators.WithEvery(validators.Range(0, 3)),
        "Campaign has to have 0 to 3 `gallery photo count` in order to be launched",
    )
    posts__deadline = (
        validators.WithEvery(validators.Required()),
        "Each campaign's post needs a `deadline` in order to be launched",
    )
    posts__opened = (
        validators.WithEvery(validators.Required()),
        "Each campaign's post needs a `submission date` in order to be launched",
    )
