from tasktiger.exceptions import TaskNotFound

from takumi.extensions import tiger
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.types.tiger import TaskState
from takumi.roles import permissions


class RetryTaskState(arguments.Enum):
    error = "error"
    scheduled = "scheduled"


class CancelTask(Mutation):
    class Arguments:
        task_id = arguments.String(required=True, description="The ID of the task")
        queue = arguments.String(required=True, description="The queue the task is in")
        state = TaskState(required=True, description="The state the task is in")

    @permissions.developer.require()
    def mutate(root, info, task_id, queue, state):
        task = tiger.get_task(task_id, queue=queue, state=state, executions=0)
        if task is None:
            raise MutationException("Task not found")

        try:
            task._move(from_state=state)
        except TaskNotFound:
            raise MutationException("Task not found")

        return CancelTask(ok=True)


class CancelAllTasks(Mutation):
    """Cancel all tasks in a queue state

    There's a hard limit of 1000 tasks that are cancelled in a single request
    """

    class Arguments:
        queue = arguments.String(required=True, description="The queue the tasks are in")
        state = TaskState(required=True, description="The state the to retry all tasks in")

    cancelled_task_count = fields.Int()

    @permissions.developer.require()
    def mutate(root, info, queue, state):
        count, tasks = tiger.get_tasks(queue=queue, state=state, limit=1000, executions=0)
        for task in tasks:
            try:
                task._move(from_state=state)
            except TaskNotFound:
                pass

        return CancelAllTasks(cancelled_task_count=len(tasks), ok=True)


class RetryTask(Mutation):
    class Arguments:
        task_id = arguments.String(required=True, description="The ID of the task")
        queue = arguments.String(required=True, description="The queue the task is in")
        state = RetryTaskState(required=True, description="The state the task is in")

    task = fields.Field("Task")

    @permissions.developer.require()
    def mutate(root, info, task_id: str, queue: str, state: str) -> "RetryTask":
        task = tiger.get_task(task_id, queue=queue, state=state, executions=0)
        if task is None:
            raise MutationException("Task not found")

        try:
            task._move(from_state=state, to_state="queued")
        except TaskNotFound:
            raise MutationException("Task not found")

        return RetryTask(task=task, ok=True)


class RetryAllTasks(Mutation):
    """Retry all tasks in a queue state

    There's a hard limit of 1000 tasks that are retried in a single request
    """

    class Arguments:
        queue = arguments.String(required=True, description="The queue the tasks are in")
        state = RetryTaskState(required=True, description="The state the to retry all tasks in")
        limit = arguments.Int(
            description="How many tasks try retry at once. The max is 1000", default_value=100
        )

    retried_task_count = fields.Int()
    total_task_count = fields.Int()

    @permissions.developer.require()
    def mutate(root, info, queue: str, state: str, limit: int) -> "RetryAllTasks":
        limit = max(limit, 1000)

        count, tasks = tiger.get_tasks(queue=queue, state=state, limit=limit, executions=0)
        for task in tasks:
            try:
                task._move(from_state=state, to_state="queued")
            except TaskNotFound:
                pass

        return RetryAllTasks(retried_task_count=len(tasks), total_task_count=count, ok=True)


class TigerMutation:
    cancel_all_tasks = CancelAllTasks.Field()
    cancel_task = CancelTask.Field()
    retry_all_tasks = RetryAllTasks.Field()
    retry_task = RetryTask.Field()
