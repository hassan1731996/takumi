import random
import time

from takumi.extensions import tiger
from takumi.tasks import TaskException


@tiger.task(retry=True, unique=True)
def wait(min_wait=1, max_wait=2):
    """A test task that simply waits

    This dummy test task is useful when testing out the task queues
    """
    if min_wait > max_wait:
        max_wait = min_wait

    sleep_time = random.randint(min_wait, max_wait)
    print(f"Sleeping for {sleep_time} seconds")  # noqa
    time.sleep(sleep_time)


@tiger.task(retry=False)
def error(chance=0.5):
    """A test task that will error randomly, based on chance of raising

    chance == 0.7 means 70% chance it will raise

    Useful for testing retry logic or just retries in general
    """
    chance = max(min(1.0, chance), 0.0)  # Clamp between 0.0 and 1.0
    chance = int(chance * 100)

    random_number = random.randint(1, 100)

    class TestTaskException(TaskException):
        pass

    if chance > random_number:
        raise TestTaskException(f"Failed with {chance}% chance")


@tiger.task(debounce=5000)
def debounced():
    """A test task that will be debounced"""
    print("Running")
