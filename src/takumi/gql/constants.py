from takumi.gql import arguments

campaign_filters = dict(
    archived=arguments.Boolean(),
    brand_safety=arguments.Boolean(),
    brand_match=arguments.Boolean(),
    has_nda=arguments.Boolean(),
    industry=arguments.String(),
    reward_model=arguments.String(),
    shipping_required=arguments.Boolean(),
    state=arguments.String(),
    advertiser_industries_ids=arguments.List(arguments.UUID),
)
