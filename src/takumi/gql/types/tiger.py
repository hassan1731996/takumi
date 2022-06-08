from graphene import ObjectType

from takumi.gql import arguments, fields
from takumi.gql.relay import Connection, Node


class TaskState(arguments.Enum):
    active = "active"
    error = "error"
    queued = "queued"
    scheduled = "scheduled"


class Task(ObjectType):
    class Meta:
        interfaces = (Node,)

    func = fields.String(description="The task function name")
    args = fields.List(fields.String, description="The task positional arguments")
    kwargs = fields.GenericScalar(description="The task keyword arguments")

    unique = fields.Boolean(
        description=(
            "Whether a task is unique in the queue. Tasks with the same "
            "arguments can't be queued multiple times"
        )
    )
    state = fields.String(description="The current state of the task")
    queue = fields.String(description="The queue the task is in")
    hard_timeout = fields.Int(description="How many seconds a task can run before being terminated")
    retry_method = fields.String(description="The method used for the retry logic")

    execution_date = fields.DateTime(
        source="ts", description="The datetime when the task will be executed"
    )

    executions = fields.List(fields.GenericScalar, description="The list of executions")

    def resolve_func(task, info):
        return task.data["func"]

    def resolve_retry_method(task, info):
        func, args = task.retry_method
        args = ", ".join(str(i) for i in args)
        return f"{func}({args})"


class Queue(ObjectType):
    name = fields.String(description="The queue name")
    active = fields.Int(description="Number of tasks being processed")
    error = fields.Int(description="Number of tasks that errored after potential retries")
    queued = fields.Int(description="Number of tasks waiting to be processed")
    scheduled = fields.Int(description="Number of tasks scheduled for future processing")


class TaskConnection(Connection):
    class Meta:
        node = Task
