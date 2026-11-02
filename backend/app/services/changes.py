import asyncio
import time

# Long enough to save requests, short enough to finish before proxies give up.
WAIT_SECONDS = 20
CHECK_SECONDS = 0.5

# ponytail: one counter for everyone, kept in this process. Every write wakes
# every open tab, which then refetches only its own screens. Count per group or
# friend pair if that load ever matters, and move to Postgres LISTEN/NOTIFY if
# the API runs as more than one instance.
_version = 0


def bump() -> None:
    global _version
    _version += 1


async def wait_for_change(seen: int | None) -> int:
    """Return the version once it differs from `seen`, or after WAIT_SECONDS."""
    deadline = time.monotonic() + WAIT_SECONDS
    while seen == _version and time.monotonic() < deadline:
        await asyncio.sleep(CHECK_SECONDS)
    return _version
