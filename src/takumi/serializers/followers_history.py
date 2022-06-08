from core.common.utils import pairwise

DEFAULT_FOLLOWERS_STATS_SIZE = 3


class InstagramAccountFollowersHistorySerializer:
    __slots__ = ("_events", "_additional_properties")

    def __init__(self, events, additional_properties=[]):
        self._events = events
        self._additional_properties = additional_properties

    @classmethod
    def _get_larger_followers_difference(
        self, prev_followers, min_current_followers, max_current_followers
    ):
        followers_diff_1 = min_current_followers - prev_followers
        followers_diff_2 = max_current_followers - prev_followers
        if abs(followers_diff_1) > abs(followers_diff_2):
            return min_current_followers, followers_diff_1
        else:
            return max_current_followers, followers_diff_2

    def serialize(self):
        """Parse list of post events with followers count.
        Calculates the biggest difference of number of followers, either positive or negative, from the day before.
        """
        followers_stats_list = []
        for previous, current in pairwise(self._events):
            """
            Previous and current have the following structure:
            date: current[0]
            min: current[1]
            max: current[2]
            additional: current[x], any additional keys that are added to the map
            """
            if followers_stats_list:
                prev_followers = followers_stats_list[-1]["followers"]
            else:
                prev_followers = previous[1]

            curr_followers, larger_followers_difference = self._get_larger_followers_difference(
                prev_followers, current[1], current[2]
            )

            avg_followers_diff = larger_followers_difference / (current[0] - previous[0]).days
            followers_stats_item = {
                "followers": curr_followers,
                "prev_followers": prev_followers,
                "followers_diff": larger_followers_difference,
                "avg_followers_diff": avg_followers_diff,
                "perc": float(avg_followers_diff) / (1 if prev_followers == 0 else prev_followers),
                "date": current[0].strftime("%d/%m/%Y"),
                "short_date": current[0].strftime("%d/%m"),
            }
            for index, item in enumerate(self._additional_properties):
                followers_stats_item[item] = current[index + DEFAULT_FOLLOWERS_STATS_SIZE]

            followers_stats_list.append(followers_stats_item)

        return followers_stats_list
