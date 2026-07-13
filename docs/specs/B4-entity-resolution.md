# B4 — Deduplication & Entity Resolution

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** Müşteri/tedarikçi ana verisiyle çalışan data engineer; CRM verisi birleştiren analyst.

**Neden:** Aynı gerçek varlık farklı yazımlarla ("Ahmet Yılmaz" / "A. Yilmaz", "İstanbul Cad. 5" / "Istanbul Caddesi No:5") mükerrer kayıt üretiyor; model eğitimi ve KPI'lar şişiyor. Fuzzy matching + blocking ile ölçeklenebilir tespit ve güvenli birleştirme gerekiyor.

**Kabul senaryoları:**
1. Kullanıcı 1M satırlık müşteri tablosunda dedup çalıştırır; blocking sayesinde makul sürede (<15 dk) tamamlanır ve eşleşme çiftleri skorla listelenir.
2. Skor ≥ otomatik eşik (varsayılan 0.95) çiftler otomatik birleştirilir; gri bölge (0.6–0.95) HITL inceleme kuyruğuna düşer.
3. İnceleyici yan yana kayıt karşılaştırmasında "birleştir / ayrı tut" kararı verir; karar etiketli örnek olarak saklanır ve model yeniden eğitilebilir.
4. Çıktıda her birleşik kayıt `entity_id` ve `merged_from` lineage'ı taşır; birleştirme geri alınabilir.

## 2. Backend Tasarımı

**Agent:** `ai_data_science_team/agents/entity_resolution_agent.py` — `EntityResolutionAgent`. Motor: `splink` (DuckDB backend, Fellegi-Sunter probabilistik model) varsayılan; küçük veri (<50k) için `recordlinkage` basit mod. LLM yalnız blocking/karşılaştırma kolonu önerisi ve karar gerekçesi anlatısı için.

**Node tipi:** `data.dedupe`.

I/O sözleşmesi:
```json
{
  "type": "data.dedupe",
  "inputs": {"dataset_ref": "artifact://run/45/customers.parquet"},
  "config": {
    "match_columns": [{"col": "name", "comparator": "jaro_winkler"}, {"col": "email", "comparator": "exact"}, {"col": "address", "comparator": "levenshtein"}],
    "blocking_rules": ["l.postcode = r.postcode", "substr(l.name,1,3) = substr(r.name,1,3)"],
    "auto_merge_threshold": 0.95, "review_threshold": 0.6,
    "merge_strategy": "most_complete", "on_review": "hitl"
  },
  "outputs": {
    "deduped_dataset_ref": "artifact://run/45/customers_deduped.parquet",
    "match_report": {"total_rows": 1000000, "auto_merged_pairs": 4210, "review_pairs": 380, "clusters": 4100},
    "review_queue_id": "erq_9f2c"
  }
}
```

**API endpoint'leri** (`routes/entity_resolution.py`):
- `POST /api/dedupe/jobs` — job başlat (dataset + config); worker'da async çalışır
- `GET /api/dedupe/jobs/{id}` — durum + özet metrikler
- `GET /api/dedupe/jobs/{id}/pairs?status=review` — inceleme çiftleri (sayfalı)
- `POST /api/dedupe/pairs/{pair_id}/decision` — `{decision: "merge"|"keep_separate", note}`
- `POST /api/dedupe/jobs/{id}/apply` — kararlar sonrası final birleştirme; `POST .../rollback`

**Veri modeli:** `dedupe_jobs` (id, tenant_id, dataset_ref, config_json, status, metrics_json), `dedupe_pairs` (job_id, left_key, right_key, score, features_json, decision, decided_by, decided_at). Kararlar splink modeli için etiketli eğitim verisi olarak saklanır.

**Hata durumları:** blocking kuralı hiç aday üretmiyor → `BLOCKING_TOO_STRICT` uyarısı + LLM'den gevşetme önerisi; aday çift sayısı > limit (`max_candidate_pairs`, varsayılan 10M) → `BLOCKING_TOO_LOOSE` fail; bellek taşması → DuckDB spill-to-disk; HITL zaman aşımı → run `awaiting_approval` durumunda bekler.

## 3. UI Tasarımı

**Ekran/bileşenler:** Yeni **DedupeReview** ekranı (HITL altyapısı üstünde, `HITLApproval` deseniyle): üstte job özeti (küme sayısı, otomatik/incelenecek), altta çift kartları kuyruğu — iki kayıt yan yana, farklı alanlar sarı vurgulu, benzerlik skoru ve alan-bazlı katkı çubukları.

**Etkileşim akışı:**
1. Designer'da `data.dedupe` node config: kolon+comparator seçimi, blocking kural builder'ı ("öner" butonu LLM'den kural getirir), eşik slider'ları.
2. Run sonrası node kartında "380 çift inceleme bekliyor" rozeti → DedupeReview'a link.
3. İnceleyici klavye kısayoluyla (M=birleştir, K=ayrı tut, S=atla) kuyruğu tüketir; ilerleme çubuğu ve kalan sayaç.
4. Kuyruk bitince "Uygula" → final dataset üretilir; "Geri al" 7 gün aktif.

**Durumlar:** loading — job durumu polling'li progress (blocking→scoring→clustering adımları); empty — "İncelenecek çift yok, tümü otomatik çözüldü"; error — aşama bazlı hata mesajı + config'e dön aksiyonu.

**Entegrasyon:** run detay sayfasında match_report artifact görünümü; I2 katalogda dataset'e "dedup uygulandı" rozeti.

## 4. Bağımlılıklar

- **Spec:** B1 (kolon profilleri comparator önerisi için), B3 (normalize edilmiş kolonlar eşleşme kalitesini artırır), J7 (birleştirme kararlarının denetim izi).
- **Kütüphaneler:** `splink>=4`, `duckdb`, `recordlinkage`, `jellyfish`/`rapidfuzz`.
- **Kod entegrasyonu:** `apps/platform-api-app/platform_api/services/workflow_node_executor_service.py`, `workflow_node_catalog_service.py`, `services/hitl_service.py` + `routes/hitl.py` (inceleme kuyruğu), `workers/workflow_worker.py` (uzun süren job), `services/artifact_service.py`.

## 5. Kapsam Dışı

- Gerçek zamanlı/streaming dedup (yalnız batch).
- Çapraz-tenant / harici referans veriyle zenginleştirme.
- Görüntü/doküman benzerliği — yalnız yapısal tablo alanları.
- Master Data Management ürün özellikleri (golden record yönetim ekranı, survivorship kural motoru — basit `most_complete/most_recent` stratejileriyle sınırlı).

## 6. Test & Definition of Done

**Senaryolar:**
- Birim: comparator'lar (jaro_winkler, exact, levenshtein) beklenen skorları üretir; Türkçe karakter normalizasyonu (İ/i, ı) eşleşmeyi bozmaz.
- Birim: `BLOCKING_TOO_LOOSE` limiti tetiklenir ve anlaşılır hata döner.
- Entegrasyon: 100k satırlık sentetik fikstürde bilinen 500 mükerrerin ≥ %90'ı review+auto kümelerinde yakalanır, false-merge oranı otomatik eşikte ≤ %1.
- E2E: dedupe node → HITL karar → apply → deduped artifact + lineage (`merged_from`) doğrulanır; rollback eski dataset'i geri getirir.

**DoD checklist:**
- [ ] `data.dedupe` katalog + validator kuralları
- [ ] Job/pair endpoint'leri, tenant izolasyonu ve sayfalama testleri
- [ ] `dedupe_jobs`/`dedupe_pairs` migration'ları
- [ ] DedupeReview ekranı klavye kısayolları + üç durum (loading/empty/error)
- [ ] Kararların etiketli veri olarak saklandığı doğrulandı
- [ ] 1M satır benchmark'ı worker'da bellek limiti aşılmadan tamamlanıyor
