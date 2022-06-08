def test_getting_queue_stats(tiger, task):
    stats = tiger.get_queue_stats()
    assert stats[tiger.default_queue] == {"active": 0, "error": 0, "queued": 0, "scheduled": 0}

    task.delay()

    stats = tiger.get_queue_stats()
    assert stats[tiger.default_queue] == {"active": 0, "error": 0, "queued": 1, "scheduled": 0}


def test_getting_tasks(tiger, task):
    tasks = tiger.get_tasks(state="queued")
    assert len(tasks) == 0

    for _ in range(3):
        task.delay()

    tasks = tiger.get_tasks(state="queued")
    assert len(tasks) == 3


def test_cleanup_stale_references_removes_references(redis, tiger, task):
    test_task_count = 100
    for _ in range(test_task_count):
        task.delay()

    tasks = tiger.get_tasks(queue=tiger.default_queue, state="queued", limit=100)

    assert len(tasks) == test_task_count

    # Remove half of the tasks
    to_remove = redis.keys("t:task:*")[: int(test_task_count / 2)]
    for key in to_remove:
        redis.delete(key)

    tiger.cleanup_stale_references(queue=tiger.default_queue, state="queued", limit=5)

    tasks = tiger.get_tasks(queue=tiger.default_queue, state="queued", limit=100)

    assert len(tasks) == int(test_task_count / 2)


def test_cleanup_stale_references_removes_queues_if_emptied(redis, tiger, old_tiger, old_task):
    assert redis.smembers("t:queued") == set()
    assert tiger.get_queue_stats().keys() == [tiger.default_queue]

    for _ in range(10):
        old_task.delay()

    assert redis.smembers("t:queued") == {old_tiger.default_queue}
    assert sorted(tiger.get_queue_stats().keys()) == sorted(
        [tiger.default_queue, old_tiger.default_queue]
    )

    for key in redis.keys("t:task:*"):
        redis.delete(key)

    tiger.cleanup_stale_references(queue=old_tiger.default_queue, state="queued")

    assert redis.smembers("t:queued") == set()
    assert tiger.get_queue_stats().keys() == [tiger.default_queue]
