from pathlib import Path

from homefinder import jobs
from homefinder.models import Job, Listing, Photo, WorkerStatus


def test_claim_complete_fail_heartbeat(db, app_client, worker_headers):
    a = jobs.enqueue(db, "enrich_listing", {"listing_id": 1}); b = jobs.enqueue(db, "enrich_listing", {"listing_id": 2}); db.commit()
    got = app_client.post("/worker/claim", json={"types": ["enrich_listing"], "n": 1}, headers=worker_headers).json()
    assert [g["id"] for g in got] == [a] and got[0]["payload"] == {"listing_id": 1}
    assert app_client.post(f"/worker/complete/{a}", json={"result": {"x": 1}}, headers=worker_headers).json() == {"ok": True}
    app_client.post("/worker/claim", json={"types": ["enrich_listing"], "n": 1}, headers=worker_headers)
    assert app_client.post(f"/worker/fail/{b}", json={"error": "boom"}, headers=worker_headers).json() == {"status": "pending"}
    assert app_client.post("/worker/heartbeat", json={"hostname": "mac", "version": "0.1.0", "current_job_id": None},
                           headers=worker_headers).status_code == 204
    db.expire_all()
    assert db.get(WorkerStatus, 1).hostname == "mac"


def test_photo_upload_writes_file_and_row(db, app_client, worker_headers, tmp_path):
    l = Listing(); db.add(l); db.commit()
    r = app_client.post("/worker/photos", headers=worker_headers,
                        data={"listing_id": l.id, "position": 0, "phash": "abcd", "source_url": "https://x"},
                        files={"file": ("0.webp", b"RIFFxxxxWEBP", "image/webp")})
    assert r.status_code == 204
    assert (tmp_path / str(l.id) / "0.webp").read_bytes() == b"RIFFxxxxWEBP"
    assert db.query(Photo).one().path == f"{l.id}/0.webp"


def test_photo_upload_rejects_path_tricks(db, app_client, worker_headers):
    r = app_client.post("/worker/photos", headers=worker_headers,
                        data={"listing_id": "../../etc", "position": 0, "phash": "", "source_url": ""},
                        files={"file": ("x", b"x", "image/webp")})
    assert r.status_code == 422
