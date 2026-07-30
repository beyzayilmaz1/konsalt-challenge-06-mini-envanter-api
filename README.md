# Mini Envanter API

**KONSALT Staj Programı 2026 — Challenge 6**  
Seviye: Orta · Stack: FastAPI · Python 3

BT varlıklarının (sunucuların) kaydedildiği, listelendiği ve güncellendiği minik bir REST envanter servisi. Konsalt CMDB mimarisinin basitleştirilmiş bir ön çalışmasıdır; Challenge 10 (Observability) ve Challenge 11 (Mini-CMDB) bu temel üzerine inşa edilecektir.

---

## Yönetici özeti

| Madde | Açıklama |
|--------|----------|
| Amaç | CMDB benzeri sunucu envanteri için REST API |
| Kapsam | CRUD, doğrulama, kalıcılık, uçtan uca test, API dokümantasyonu |
| Bonus | Sayfalama, API anahtarı, istatistik endpoint’i |
| Kod kalitesi | Type hint, response model, Swagger metadata, yapılandırılmış logging |
| Kalıcılık | `envanter.json` (Challenge 11’de SQLite’a taşınacak) |
| Doğrulama | Swagger UI + `test_api.py` otomatik senaryo |

**Teslim paketi**

| Dosya | Rol |
|--------|-----|
| `main.py` | API uygulaması |
| `test_api.py` | Uçtan uca test scripti |
| `requirements.txt` | Bağımlılıklar |
| `README.md` | Kurulum, çalıştırma ve API kullanım kılavuzu |

---

## Hızlı başlangıç

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

| Adres | Açıklama |
|--------|----------|
| http://localhost:8000 | API kökü |
| http://localhost:8000/docs | Swagger / OpenAPI arayüzü |
| http://localhost:8000/health | Sağlık kontrolü |

**Kimlik doğrulama:** `/health` ve `/docs` dışında tüm isteklerde `X-API-Key` zorunludur.

| Ortam | Değer |
|--------|--------|
| Varsayılan anahtar | `konsalt-dev-key` |
| Özelleştirme | `API_KEY=benim-anahtar` |

---

## Challenge kapsamı

| Görev | İçerik | Durum |
|--------|--------|--------|
| 1 | `GET /health` → `{"status": "ok"}` | Tamamlandı |
| 2 | Pydantic `Server` modeli (status Enum, IP doğrulama, `ram_gb` kuralları) | Tamamlandı |
| 3 | CRUD endpoint’leri, filtreler, tutarlı hata gövdeleri | Tamamlandı |
| 4 | `envanter.json` ile kalıcılık | Tamamlandı |
| 5 | `test_api.py` uçtan uca test | Tamamlandı |
| Bonus | Sayfalama, API-Key, `GET /stats` | Tamamlandı |
| Ek iyileştirmeler | Type hint, response model, Swagger metadata, logging | Tamamlandı |

---

## Ek iyileştirmeler (challenge ötesi)

Challenge isterlerinin üzerine, üretim kalitesine yakın dokunuşlar eklendi:

| Özellik | Açıklama |
|---------|----------|
| **Type hint** | Tüm endpoint fonksiyonlarında dönüş tipi belirtildi (`-> Server`, `-> ServerListResponse` vb.) |
| **Response model** | `HealthResponse`, `ServerListResponse`, `StatsResponse` — Swagger'da yanıt şeması otomatik görünür |
| **Swagger metadata** | Her endpoint'te `summary`, `description` ve `tags` (`Sistem`, `Sunucular`, `İstatistik`) |
| **Query açıklamaları** | `status`, `os`, `limit`, `offset` parametreleri `/docs` içinde açıklamalı |
| **Logging** | `logging` modülü ile başlangıç ve CRUD işlemleri kayıt altına alınır |

Örnek log çıktısı:

```text
INFO Envanter yüklendi: 3 sunucu
INFO Server created: web-01
INFO Server updated: web-01
INFO Server deleted: web-01
```

---

## Mimari kararlar

- **FastAPI + Pydantic:** İstek gövdesi kapıda doğrulanır; geçersiz veri (ör. `ram_gb=-5`) otomatik **422** döner.
- **Bellek + JSON dosyası:** Çalışma anında `dict[str, Server]`; her yazma işleminde `envanter.json` güncellenir, açılışta yüklenir.
- **HTTP semantiği:** `201` oluşturma, `204` silme, `404` bulunamadı, `409` çakışma, `401` yetkisiz.
- **Hata formatı:** Tüm hatalar `{"error": "açıklama"}` döner; doğrulama (422) ek olarak `details` listesi içerir.
- **Dokümantasyon:** OpenAPI şeması `/docs` üzerinden otomatik üretilir; endpoint'ler `summary`, `tags` ve `response_model` ile gruplanmıştır.
- **Logging:** CRUD işlemleri ve başlangıçta `logging` modülü ile kayıt altına alınır (Challenge 10 observability için temel).

---

## API referansı

### Endpoint’ler

| Metod | Yol | Auth | Açıklama |
|--------|-----|------|----------|
| `GET` | `/health` | Hayır | Servis ayakta mı |
| `POST` | `/servers` | Evet | Yeni sunucu ekle (aynı isim → **409**) |
| `GET` | `/servers` | Evet | Listele; `status`, `os`, `limit`, `offset` |
| `GET` | `/servers/{name}` | Evet | Tek kayıt (yoksa **404**) |
| `PUT` | `/servers/{name}` | Evet | Güncelle (yoksa **404**) |
| `DELETE` | `/servers/{name}` | Evet | Sil → **204 No Content** |
| `GET` | `/stats` | Evet | Toplam sunucu, OS dağılımı, toplam RAM |

### Veri modeli

```json
{
  "name": "web-01",
  "ip": "192.168.1.10",
  "os": "ubuntu",
  "ram_gb": 8,
  "status": "running"
}
```

| Alan | Kural |
|------|--------|
| `name` | 3–50 karakter |
| `ip` | Geçerli IPv4 veya IPv6 |
| `os` | Serbest metin (filtrelerde büyük/küçük harf duyarsız) |
| `ram_gb` | 1–4096 (tam sayı) |
| `status` | `running` \| `stopped` \| `maintenance` |

### Liste yanıtı (sayfalama)

```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "items": [ /* Server[] */ ]
}
```

### Hata gövdesi

```json
{ "error": "açıklama" }
```

Doğrulama hatası (**422**):

```json
{
  "error": "Doğrulama başarısız",
  "details": [ /* Pydantic hata listesi */ ]
}
```

---

## Örnek istekler

Aşağıdaki `curl` komutları **Windows CMD** içinde kopyala-yapıştır ile çalışır. PowerShell kullanıyorsanız önce `cmd` yazıp Enter'a basarak CMD'ye geçin.

```bash
# Sağlık kontrolü
curl http://localhost:8000/health

# Sunucu ekle
curl -X POST http://localhost:8000/servers -H "Content-Type: application/json" -H "X-API-Key: konsalt-dev-key" -d "{\"name\":\"web-01\",\"ip\":\"192.168.1.10\",\"os\":\"ubuntu\",\"ram_gb\":8,\"status\":\"running\"}"

# Listele (filtre + sayfalama)
curl "http://localhost:8000/servers?status=running&os=ubuntu&limit=10&offset=0" -H "X-API-Key: konsalt-dev-key"

# Tek kayıt
curl http://localhost:8000/servers/web-01 -H "X-API-Key: konsalt-dev-key"

# Güncelle
curl -X PUT http://localhost:8000/servers/web-01 -H "Content-Type: application/json" -H "X-API-Key: konsalt-dev-key" -d "{\"ip\":\"192.168.1.11\",\"os\":\"ubuntu\",\"ram_gb\":16,\"status\":\"maintenance\"}"

# İstatistikler
curl http://localhost:8000/stats -H "X-API-Key: konsalt-dev-key"

# Sil
curl -X DELETE http://localhost:8000/servers/web-01 -H "X-API-Key: konsalt-dev-key"
```

---

## Test

API çalışırken:

```bash
python test_api.py
```

Başarılı çıktı:

```text
TÜM TESTLER GEÇTİ
```

Senaryo özeti: health → API-key kontrolü → ekle → 409 → 422 → listele → getir → güncelle → stats → sil → 404.

---

## Bağımlılıklar

| Paket | Kullanım |
|--------|----------|
| `fastapi` | REST framework |
| `uvicorn` | ASGI sunucu |
| `pydantic` | Veri doğrulama |
| `requests` | Uçtan uca test istemcisi |

```bash
pip install -r requirements.txt
```

---

## Sonraki adımlar (program bağlamı)

- **Challenge 10:** Metrik, log ve sağlık gözlemlenebilirliği
- **Challenge 11:** JSON kalıcılığının SQLite / gerçek CMDB modeline taşınması
