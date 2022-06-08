from typing import Dict, List

import graphene

from takumi.gql import arguments, fields
from takumi.gql.utils import get_campaign_or_404
from takumi.roles import permissions


class SentimentEntry(graphene.ObjectType):
    count = fields.Int()
    comments = fields.List(fields.String)


class PostSentiment(graphene.ObjectType):
    post = fields.String()
    positive = fields.Field(SentimentEntry)
    neutral = fields.Field(SentimentEntry)
    negative = fields.Field(SentimentEntry)
    mixed = fields.Field(SentimentEntry)
    unknown = fields.Field(SentimentEntry)


class SentimentQuery:
    sentiment_for_campaign = fields.List(
        PostSentiment,
        campaign_id=arguments.UUID(required=True),
        min_confidence=arguments.Float(default_value=0.75),
    )

    @permissions.team_member.require()
    def resolve_sentiment_for_campaign(root, info, campaign_id: str, min_confidence: float):
        campaign = get_campaign_or_404(campaign_id)

        output = []

        for idx, post in enumerate(campaign.posts):
            stats: Dict[str, List[str]] = {
                "positive": [],
                "neutral": [],
                "negative": [],
                "mixed": [],
                "unknown": [],
            }

            if post.post_type not in ("standard", "video"):
                continue

            for gig in post.gigs:
                if gig.instagram_post is None:
                    continue
                for comment in gig.instagram_post.ig_comments:
                    if not comment.sentiment_checked or not comment.sentiment_positive_score:
                        continue
                    if comment.sentiment_positive_score > min_confidence:
                        stats["positive"].append(comment.text)
                    elif comment.sentiment_neutral_score > min_confidence:
                        stats["neutral"].append(comment.text)
                    elif comment.sentiment_negative_score > min_confidence:
                        stats["negative"].append(comment.text)
                    elif comment.sentiment_mixed_score > min_confidence:
                        stats["mixed"].append(comment.text)
                    else:
                        stats["unknown"].append(comment.text)

            results: Dict = {
                key: {"count": len(comments), "comments": comments}
                for key, comments in stats.items()
            }
            results["post"] = f"Post {idx+1}"
            output.append(results)

        return output
