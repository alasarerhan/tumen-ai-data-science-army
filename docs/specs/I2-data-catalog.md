# I2 — Data Catalog & Semantik Katman

> Öncelik: P1 · Faz 2. Kaynaklardan şema/istatistik toplayan katalog + iş terimi↔kolon semantik eşlemesi; I1 planner'ın "churn verisi hangi tabloda?" sorusunun cevap katmanı.

## 1. Amaç & Kullanıcı Hikâyeleri

**Sorun:** Kayıtlı veri kaynaklarının şeması/istatistiği merkezi olarak tutulmuyor; planner ve kullanıcı her seferinde kaynağı yeniden keşfetmek zorunda. İş terimleri ("ciro", "müşteri kaybı") ile fiziksel kolonlar arasında eşleme yok.

**Kullanıcı hikâyeleri:**
- **US-1 (DS):** Katalogda "churn" ararım; ilgili tablo/kolonlar güven skoruyla listelenir, kolon istatistik kartını görürüm.
- **US-2 (Planner/I1):** LLM planner "satış verisi" ifadesini katalog araması ile `src_sales.orders.revenue` kolonuna çözer.
- **US-3 (Veri sahibi):** Bir kolona iş terimi ve açıklama eklerim; PII rozetini görürüm (B5 tespitinden).
- **US-4 (ML Eng):** Bir tabloyu hangi pipeline'ların kullandığını görürüm (temel lineage).

**Kabul senaryoları:**
1. Yeni kaynak kaydında otomatik tarama şema + temel istatistikleri ≤2 dk'da katalize eder.
2. Semantik arama ("müşteri kaybı") eşanlamlı/embedding üzerinden doğru kolonu ilk 3 sonuçta getirir.
3. I1 planner `resolve_data(term)` çağrısıyla katalogdan kaynak+kolon alır.

## 2. Backend Tasarımı

### 2.1 Servis / Agent

| Bileşen | Dosya | Sorumluluk |
|---|---|---|
| `DataCatalogService` | `apps/platform-api-app/platform_api/services/data_catalog_service.py` (yeni) | tarama orkestrasyonu, CRUD, arama |
| `CatalogScannerAgent` | `ai_data_science_team/agents/catalog_scanner_agent.py` (yeni) | kaynaktan şema/istatistik çıkarımı (örnekleme ile), kolon açıklaması + iş terimi önerisi (LLM) |
| `SemanticIndex` | servis içinde | terim↔kolon eşlemesi: embedding (yerel) + eşanlamlı sözlüğü; `search(term) -> [ColumnMatch]` |

### 2.2 Node tipi + I/O sözleşmesi

Yeni node `catalog.scan` (zamanlanabilir; J3 tetikleyicisi olabilir):

```json
{
  "type": "catalog.scan",
  "params": {"source_id": "src_sales", "sample_rows": 10000, "profile_level": "basic"},
  "output": {
    "artifact_type": "catalog_snapshot",
    "tables_scanned": 12,
    "columns": [
      {"table": "orders", "name": "revenue", "dtype": "float64",
       "stats": {"null_pct": 0.4, "min": 0, "max": 98000, "distinct": 51234},
       "pii": false, "business_terms": ["ciro", "gelir"], "confidence": 0.92}
    ],
    "schema_changes": [{"table": "orders", "change": "column_added", "column": "channel"}]
  }
}
```

`schema_changes` çıktısı J3 "dataset değişti" olayını besler.

### 2.3 API endpoint'leri

| Method | Path | Açıklama |
|---|---|---|
| `POST` | `/api/catalog/scan` | `{source_id}` → tarama job'ı başlatır (async, job_id döner) |
| `GET` | `/api/catalog/tree` | kaynak→şema→tablo→kolon ağacı |
| `GET` | `/api/catalog/search?q=` | semantik + tam metin arama |
| `GET` | `/api/catalog/columns/{id}` | istatistik kartı + kullanan pipeline'lar |
| `PUT` | `/api/catalog/columns/{id}` | iş terimi/açıklama/etiket düzenleme |

### 2.4 Veri modeli / migration

Tablolar: `catalog_tables` (`id, source_id, schema_name, name, row_estimate, last_scanned_at`), `catalog_columns` (`id, table_id, name, dtype, stats_json, pii_flag, description, embedding BLOB`), `business_terms` (`id, term, column_id, confidence, source: llm|user`), `catalog_usage` (`column_id/table_id, workflow_id, node_id`) — workflow spec'lerinden çıkarılır.

### 2.5 Hata durumları

- Kaynağa bağlanılamıyor → tarama job'ı `failed`, son başarılı snapshot korunur, UI'da "bayat veri" rozeti + son tarama zamanı.
- Çok büyük tablo → örnekleme (LIMIT/ TABLESAMPLE); istatistikler `approximate: true` işaretli.
- LLM terim önerisi başarısız → katalog istatistiklerle yine oluşur, terimler boş kalır (degrade).
- Şema çakışması (kolon silinmiş) → kolon `deprecated` işaretlenir, kullanan pipeline'lar uyarı alır.

## 3. UI Tasarımı

**Ekran:** yeni `frontend/src/app/components/catalog/DataCatalog.tsx` — sol nav'a "Katalog" girişi.

- **Sol:** kaynak→şema→tablo→kolon ağacı (K3 `SchemaTree`), üstte arama kutusu (semantik sonuçlar güven skoru rozeti ile).
- **Sağ:** seçili kolon için **istatistik kartı** — dtype, null %, distinct, min/max, mini dağılım grafiği (B1 ile aynı bileşen), **PII rozeti** (B5), iş terimi chip'leri (düzenlenebilir), "hangi pipeline'lar kullanıyor" listesi (tıkla → Designer'da aç).
- **Tablo görünümü:** kolon grid'i + "yeniden tara" butonu + son tarama zamanı.
- **Chat entegrasyonu:** I1'deki kaynak/kolon picker aynı ağaç bileşenini kullanır.

**Durumlar:** Loading — ağaç skeleton'u; Empty — "Henüz kaynak taranmadı" + "İlk taramayı başlat" CTA; Error — tarama hatası banner'ı + "tekrar dene"; bayat snapshot uyarısı.

## 4. Bağımlılıklar

- **Spec'ler:** B1 (profil kartı bileşeni), B5 (PII rozeti), I1 (planner tüketicisi), J3 (schema_changes olayı), J12 (usage → lineage temeli), H1–H7 (taranacak konektörler).
- **Mevcut kod:** data source kayıt servisi, `apps/platform-api-app` route yapısı, `runtime_engine.py` (tarama job'larında retry).
- **Kütüphaneler:** sentence-transformers veya mevcut LLM embedding endpoint'i; SQLAlchemy/Alembic.

## 5. Kapsam Dışı

- Tam lineage grafı (J12), veri kalite kuralları (B2), erişim yetkilendirme/governance (J7), dbt/harici katalog (DataHub vb.) senkronu, gerçek zamanlı CDC tabanlı şema izleme.

## 6. Test & Definition of Done

**Birim:** scanner CSV/Postgres kaynakta doğru dtype+istatistik çıkarır; `SemanticIndex.search("ciro")` revenue kolonunu döner; şema değişikliği diff'i doğru üretilir; kaynak hatasında snapshot korunur.

**E2E:**
1. Kaynak kaydet → tara → ağaçta tablolar/kolonlar görünür, istatistik kartı dolu.
2. Kolona "müşteri kaybı" terimi ekle → chat'te I1 planner bu terimi ilgili kolona çözer.
3. Kolon silinmiş kaynağı yeniden tara → `deprecated` rozeti + kullanan workflow'da uyarı.

**DoD:** tarama p50 < 2 dk (10 tablo/10k örnek); arama < 500 ms; I1 `resolve_data` entegrasyonu çalışır; K3 durum standartları uygulanmış; migration'lar geri alınabilir.
