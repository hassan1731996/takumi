from graphene.relay.connection import PageInfo
from graphql_relay.utils import base64, unbase64

from takumi.extensions import tiger
from takumi.gql import arguments, fields
from takumi.gql.exceptions import GraphQLException
from takumi.gql.types.tiger import TaskState
from takumi.roles import permissions


class TigerConnectionField(fields.ConnectionField):
    _prefix = "tiger_connection"

    def _offset_to_cursor(self, offset):
        return base64(f"{self._prefix}:{offset}")

    def _cursor_to_offset(self, cursor):
        try:
            return int(unbase64(cursor).split(":")[1])
        except Exception:
            return None

    def connection_resolver(self, resolver, connection, root, info, **args):
        """A custom connection resolver for tiger tasks, to handle pagination"""
        if "last" in args or "before" in args:
            raise GraphQLException("TigerConnection doesn't support 'last' and 'before'")

        limit = min(args.get("first", self._max_first), self._max_first)
        skip = 0
        if "after" in args:
            # If we want after idx X, we skip X + 1
            # After 2nd element, skip 3 (0, 1 and 2)
            after_offset = self._cursor_to_offset(args["after"])
            if after_offset:
                skip = after_offset + 1

        resolver_args = {
            key: args[key] for key in args if key not in ["first", "last", "before", "after"]
        }

        count, tasks = resolver(root, info, limit=limit, skip=skip, **resolver_args)

        edges = [
            connection.Edge(node=node, cursor=self._offset_to_cursor(skip + i))
            for i, node in enumerate(tasks)
        ]

        page_info = PageInfo(
            start_cursor=edges[0].cursor if edges else None,
            end_cursor=edges[-1].cursor if edges else None,
            has_previous_page=skip > 0,
            has_next_page=skip + limit < count,
        )

        return connection(edges=edges, count=count, page_info=page_info)


class TigerQuery:
    queue_stats = fields.List("Queue", description="The stats of all active queues")
    tasks_for_queue = TigerConnectionField(
        "TaskConnection", queue=arguments.String(required=True), state=TaskState(required=True)
    )

    @permissions.developer.require()
    def resolve_queue_stats(root, info):
        queue_stats = tiger.get_queue_stats()
        return [
            {
                "name": queue,
                "active": states["active"],
                "error": states["error"],
                "queued": states["queued"],
                "scheduled": states["scheduled"],
            }
            for queue, states in queue_stats.items()
        ]

    @permissions.developer.require()
    def resolve_tasks_for_queue(root, info, queue, state, limit=100, skip=0):
        return tiger.get_tasks(queue=queue, state=state, skip=skip, limit=limit)
