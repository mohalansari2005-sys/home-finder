import httpx


class WorkerClient:
    def __init__(self, base_url: str, token: str, http: httpx.Client | None = None):
        self._h = http or httpx.Client(base_url=base_url, timeout=60, headers={"Authorization": f"Bearer {token}"})

    def claim(self, types: list[str], n: int = 1) -> list[dict]:
        r = self._h.post("/worker/claim", json={"types": types, "n": n}); r.raise_for_status(); return r.json()

    def complete(self, job_id: int, result: dict | None) -> None:
        self._h.post(f"/worker/complete/{job_id}", json={"result": result}).raise_for_status()

    def fail(self, job_id: int, error: str) -> None:
        self._h.post(f"/worker/fail/{job_id}", json={"error": error[:4000]}).raise_for_status()

    def heartbeat(self, hostname: str, version: str, current_job_id: int | None) -> None:
        self._h.post("/worker/heartbeat", json={"hostname": hostname, "version": version,
                                                "current_job_id": current_job_id}).raise_for_status()

    def upload(self, listing_id: int, position: int, data: bytes, phash: str, source_url: str) -> None:
        r = self._h.post("/worker/photos", data={"listing_id": listing_id, "position": position, "phash": phash,
                                                 "source_url": source_url},
                         files={"file": (f"{position}.webp", data, "image/webp")})
        r.raise_for_status()
