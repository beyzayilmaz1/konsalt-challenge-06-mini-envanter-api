"""
Uçtan uca test: ekle → listele → güncelle → sil → 404 doğrula.
Önce API'yi başlatın: python -m uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import sys
import uuid

import requests

BASE_URL = "http://127.0.0.1:8000"
HEADERS = {"X-API-Key": "konsalt-dev-key"}
NAME = f"test-srv-{uuid.uuid4().hex[:8]}"


def assert_status(response: requests.Response, expected: int, step: str) -> None:
    if response.status_code != expected:
        raise AssertionError(
            f"[{step}] Beklenen {expected}, gelen {response.status_code}: {response.text}"
        )


def main() -> None:
    # 0) Health (API key gerekmez)
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    assert_status(r, 200, "health")
    assert r.json()["status"] == "ok"

    # 0b) API key yoksa 401
    r = requests.get(f"{BASE_URL}/servers", timeout=5)
    assert_status(r, 401, "api-key-yok")

    payload = {
        "name": NAME,
        "ip": "10.0.0.42",
        "os": "ubuntu",
        "ram_gb": 16,
        "status": "running",
    }

    # 1) Ekle
    r = requests.post(f"{BASE_URL}/servers", json=payload, headers=HEADERS, timeout=5)
    assert_status(r, 201, "create")
    assert r.json()["name"] == NAME

    # 1b) Aynı isim → 409
    r = requests.post(f"{BASE_URL}/servers", json=payload, headers=HEADERS, timeout=5)
    assert_status(r, 409, "conflict")
    assert "error" in r.json()

    # 1c) Geçersiz ram → 422
    bad = {**payload, "name": f"{NAME}-bad", "ram_gb": -5}
    r = requests.post(f"{BASE_URL}/servers", json=bad, headers=HEADERS, timeout=5)
    assert_status(r, 422, "validation")
    body = r.json()
    assert "error" in body and "details" in body

    # 2) Listele (+ filtre)
    r = requests.get(
        f"{BASE_URL}/servers",
        params={"status": "running", "os": "ubuntu"},
        headers=HEADERS,
        timeout=5,
    )
    assert_status(r, 200, "list")
    names = [item["name"] for item in r.json()["items"]]
    assert NAME in names, f"Liste içinde {NAME} yok"

    # 3) Tek kayıt
    r = requests.get(f"{BASE_URL}/servers/{NAME}", headers=HEADERS, timeout=5)
    assert_status(r, 200, "get")
    assert r.json()["ip"] == "10.0.0.42"

    # 4) Güncelle
    updated = {
        "ip": "10.0.0.99",
        "os": "ubuntu",
        "ram_gb": 32,
        "status": "maintenance",
    }
    r = requests.put(
        f"{BASE_URL}/servers/{NAME}",
        json=updated,
        headers=HEADERS,
        timeout=5,
    )
    assert_status(r, 200, "update")
    assert r.json()["ram_gb"] == 32
    assert r.json()["status"] == "maintenance"

    # 5) Stats
    r = requests.get(f"{BASE_URL}/stats", headers=HEADERS, timeout=5)
    assert_status(r, 200, "stats")
    assert r.json()["total_servers"] >= 1

    # 6) Sil
    r = requests.delete(f"{BASE_URL}/servers/{NAME}", headers=HEADERS, timeout=5)
    assert_status(r, 204, "delete")

    # 7) Silindikten sonra 404
    r = requests.get(f"{BASE_URL}/servers/{NAME}", headers=HEADERS, timeout=5)
    assert_status(r, 404, "get-after-delete")
    assert "error" in r.json()

    print("TÜM TESTLER GEÇTİ")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print(
            "HATA: API'ye bağlanılamadı. Önce şunu çalıştırın:\n"
            "  python -m uvicorn main:app --reload --port 8000",
            file=sys.stderr,
        )
        sys.exit(1)
    except AssertionError as exc:
        print(f"TEST BAŞARISIZ: {exc}", file=sys.stderr)
        sys.exit(1)
