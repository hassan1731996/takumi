from graphene import Enum, ObjectType

from takumi.gql import fields
from takumi.timeline import Step


class TimelineItemState(fields.Enum):
    inactive = "inactive"
    active = "active"
    incomplete = "incomplete"
    complete = "complete"


class DateTimeRange(ObjectType):
    start = fields.DateTime()
    end = fields.DateTime()


class TimelineItem(ObjectType):
    title = fields.String()
    state = TimelineItemState()
    description = fields.String()
    dates = fields.Field(DateTimeRange)


PostStep = Enum("PostStep", {step.name: step.name for step in Step})


class Timeline(ObjectType):
    timeline_items = fields.List(TimelineItem)
    post_step = PostStep()
