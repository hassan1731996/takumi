from takumi.constants import MILLE


class Fund:
    def __init__(self, campaign):
        self.campaign = campaign

    def get_progress(self):
        raise NotImplementedError()

    def is_reservable(self):
        raise NotImplementedError()

    def is_fulfilled(self):
        raise NotImplementedError()

    @property
    def reserved_offer_count(self):
        return len(self.campaign.reserved_offers)

    @property
    def min_followers(self):
        raise NotImplementedError()

    @property
    def unit_mille(self):
        raise NotImplementedError()

    def get_reward(self, followers):
        campaign = self.campaign

        reward = campaign.custom_reward_units
        if reward is None:
            total_reward = campaign.list_price * (1 - campaign.market.margins.reach)
            reward = total_reward / float(self.unit_mille)

        return reward * followers / MILLE

    def get_offer_units(self, offer):
        raise NotImplementedError()

    def get_remaining_reach(self):
        raise NotImplementedError()
