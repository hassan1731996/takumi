from takumi.gql import arguments
from takumi.models.campaign import RewardModels


class RewardModel(arguments.Enum):
    assets = RewardModels.assets
    engagement = RewardModels.engagement
    reach = RewardModels.reach
    impressions = RewardModels.impressions
