import logging
import socket
import time
from collections.abc import Callable

import httpx

from homefinder import __version__
from homefinder.config import get_settings
from homefinder.db import session_scope
from homefinder.integrations.google import make_google
from homefinder.integrations.llm import make_llm
from homefinder.worker import scheduler
from homefinder.worker.client import WorkerClient
from homefinder.worker.handlers import HANDLERS, WorkerDeps, dispatch
from homefinder.worker.sources.aqar import AqarAdapter, make_default_transport
from homefinder.worker.sources.haraj import HarajAdapter
from homefinder.worker.sources.haraj_transport import make_haraj_transport

log = logging.getLogger("homefinder.worker")
HEARTBEAT_EVERY = 60.0
OFFLINE_BACKOFF = 30.0


def _schedule(interval_hours: float) -> None:
    with session_scope() as s:
        scheduler.maybe_schedule(s, interval_hours)


def run_loop(deps, client, *, stop: Callable[[], bool], sleep=time.sleep, poll_interval: float = 5.0,
             interval_hours: float = 4.0, hostname: str = "mac") -> None:
    last_beat = -1e9
    while not stop():
        try:
            if time.monotonic() - last_beat > HEARTBEAT_EVERY:
                client.heartbeat(hostname, __version__, None)
                last_beat = time.monotonic()
            _schedule(interval_hours)
            claimed = client.claim(list(HANDLERS), 1)
        except Exception as e:  # noqa: BLE001 — server/DB unreachable (Mac off Tailscale, server restarting)
            log.warning("server unreachable: %s", e)
            sleep(OFFLINE_BACKOFF)
            continue
        if not claimed:
            sleep(poll_interval)
            continue
        job = claimed[0]
        log.info("job %s %s", job["id"], job["type"])
        try:
            result = dispatch(deps, job["type"], job["payload"])
            client.complete(job["id"], result)
        except Exception as e:  # noqa: BLE001
            log.exception("job %s failed", job["id"])
            try:
                client.fail(job["id"], f"{type(e).__name__}: {e}")
            except Exception:  # noqa: BLE001
                log.warning("could not report failure; job will be reclaimed after 15 min")


def build_deps(client: WorkerClient) -> WorkerDeps:
    http = httpx.Client(timeout=30, headers={"user-agent": "Mozilla/5.0 (Macintosh) HomeFinder/0.1"})
    # One adapter per source for the whole process: a single Pacer and HTTP session, so the 2-3 s gap holds
    # between jobs too (transports are created lazily, so building them here costs nothing).
    aqar, haraj = AqarAdapter(make_default_transport()), HarajAdapter(make_haraj_transport())
    return WorkerDeps(session_factory=session_scope,
                      adapters={"aqar": lambda: aqar, "haraj": lambda: haraj},
                      llm=make_llm(), google=make_google(http), photo_sink=client, http=http)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    st = get_settings()
    client = WorkerClient(st.server_url, st.worker_token)
    deps = build_deps(client)
    try:
        run_loop(deps, client, stop=lambda: False, interval_hours=st.scrape_interval_hours,
                 hostname=socket.gethostname())
    finally:
        for make in deps.adapters.values():
            make().close()


if __name__ == "__main__":
    main()
