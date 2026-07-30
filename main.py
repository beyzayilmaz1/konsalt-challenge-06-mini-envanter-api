"""
KONSALT Challenge 6 — Mini Envanter API
Bellekte tutulan, JSON'a kalıcı yazılan sunucu envanteri.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import time
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent / "envanter.json"
API_KEY = os.getenv("API_KEY", "konsalt-dev-key")
# Challenge 8 bonus: kasıtlı latency enjeksiyonu (varsayılan 0 = gecikme yok)
HEALTH_DELAY_SECONDS = float(os.getenv("HEALTH_DELAY_SECONDS", "0"))

app = FastAPI(
    title="Konsalt Mini Envanter API",
    description="CMDB'nin minik versiyonu — sunucu envanteri (Challenge 6)",
    version="1.0.0",
)


class ServerStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    maintenance = "maintenance"


class Server(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    ip: str
    os: str
    ram_gb: int = Field(gt=0, le=4096)
    status: ServerStatus = ServerStatus.running

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("Geçerli bir IPv4 veya IPv6 adresi olmalı") from exc
        return value


class ServerUpdate(BaseModel):
    """PUT için gövde; name yol parametresinden gelir."""

    ip: str
    os: str
    ram_gb: int = Field(gt=0, le=4096)
    status: ServerStatus = ServerStatus.running

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("Geçerli bir IPv4 veya IPv6 adresi olmalı") from exc
        return value


class HealthResponse(BaseModel):
    status: str


class ServerListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[Server]


class StatsResponse(BaseModel):
    total_servers: int
    os_distribution: dict[str, int]
    total_ram_gb: int
    status_distribution: dict[str, int]


inventory: dict[str, Server] = {}


def load_inventory() -> None:
    global inventory
    if not DATA_FILE.exists():
        inventory = {}
        return
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    inventory = {name: Server(**data) for name, data in raw.items()}


def save_inventory() -> None:
    payload = {name: server.model_dump(mode="json") for name, server in inventory.items()}
    DATA_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@app.on_event("startup")
def on_startup() -> None:
    load_inventory()
    logger.info("Envanter yüklendi: %d sunucu", len(inventory))


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    else:
        body = {"error": detail if isinstance(detail, str) else str(detail)}
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "Doğrulama başarısız", "details": exc.errors()},
    )


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Sağlık kontrolü",
    description=(
        "Servisin ayakta olup olmadığını döner. Kimlik doğrulama gerekmez. "
        "HEALTH_DELAY_SECONDS env ile kasıtlı gecikme eklenebilir (Challenge 8 YAVAS testi)."
    ),
    tags=["Sistem"],
)
def health() -> HealthResponse:
    if HEALTH_DELAY_SECONDS > 0:
        time.sleep(HEALTH_DELAY_SECONDS)
    return HealthResponse(status="ok")


@app.post(
    "/servers",
    status_code=201,
    response_model=Server,
    summary="Sunucu ekle",
    description="Yeni sunucu kaydı oluşturur. Aynı isim varsa 409 Conflict döner.",
    tags=["Sunucular"],
    dependencies=[Depends(require_api_key)],
)
def create_server(server: Server) -> Server:
    if server.name in inventory:
        raise HTTPException(status_code=409, detail=f"'{server.name}' zaten kayıtlı")
    inventory[server.name] = server
    save_inventory()
    logger.info("Server created: %s", server.name)
    return server


@app.get(
    "/servers",
    response_model=ServerListResponse,
    summary="Sunucuları listele",
    description="Envanterdeki sunucuları döner. `status`, `os` ile filtreleme ve `limit`/`offset` ile sayfalama desteklenir.",
    tags=["Sunucular"],
    dependencies=[Depends(require_api_key)],
)
def list_servers(
    status: Optional[ServerStatus] = Query(default=None, description="Duruma göre filtrele"),
    os: Optional[str] = Query(default=None, description="İşletim sistemine göre filtrele (büyük/küçük harf duyarsız)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Sayfa başına kayıt sayısı"),
    offset: int = Query(default=0, ge=0, description="Atlanacak kayıt sayısı"),
) -> ServerListResponse:
    servers = list(inventory.values())
    if status is not None:
        servers = [s for s in servers if s.status == status]
    if os is not None:
        servers = [s for s in servers if s.os.lower() == os.lower()]
    total = len(servers)
    page = servers[offset : offset + limit]
    return ServerListResponse(total=total, limit=limit, offset=offset, items=page)


@app.get(
    "/servers/{name}",
    response_model=Server,
    summary="Sunucu detayı",
    description="Belirtilen isimdeki sunucuyu döner. Kayıt yoksa 404.",
    tags=["Sunucular"],
    dependencies=[Depends(require_api_key)],
)
def get_server(name: str) -> Server:
    server = inventory.get(name)
    if server is None:
        raise HTTPException(status_code=404, detail=f"'{name}' bulunamadı")
    return server


@app.put(
    "/servers/{name}",
    response_model=Server,
    summary="Sunucu güncelle",
    description="Mevcut sunucu kaydını günceller. Kayıt yoksa 404.",
    tags=["Sunucular"],
    dependencies=[Depends(require_api_key)],
)
def update_server(name: str, body: ServerUpdate) -> Server:
    if name not in inventory:
        raise HTTPException(status_code=404, detail=f"'{name}' bulunamadı")
    updated = Server(name=name, **body.model_dump())
    inventory[name] = updated
    save_inventory()
    logger.info("Server updated: %s", name)
    return updated


@app.delete(
    "/servers/{name}",
    status_code=204,
    summary="Sunucu sil",
    description="Sunucu kaydını siler. Başarıda 204 No Content döner.",
    tags=["Sunucular"],
    dependencies=[Depends(require_api_key)],
)
def delete_server(name: str) -> Response:
    if name not in inventory:
        raise HTTPException(status_code=404, detail=f"'{name}' bulunamadı")
    del inventory[name]
    save_inventory()
    logger.info("Server deleted: %s", name)
    return Response(status_code=204)


@app.get(
    "/stats",
    response_model=StatsResponse,
    summary="Envanter istatistikleri",
    description="Toplam sunucu sayısı, OS dağılımı, toplam RAM ve durum dağılımını döner.",
    tags=["İstatistik"],
    dependencies=[Depends(require_api_key)],
)
def stats() -> StatsResponse:
    servers = list(inventory.values())
    os_dist = dict(Counter(s.os.lower() for s in servers))
    return StatsResponse(
        total_servers=len(servers),
        os_distribution=os_dist,
        total_ram_gb=sum(s.ram_gb for s in servers),
        status_distribution=dict(Counter(s.status.value for s in servers)),
    )
