# B3 — Schema Inference & Mapping

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** Yeni bir veri kaynağını platforma bağlayan data engineer / analyst; hedef şemaya veri taşıyan pipeline sahibi.

**Neden:** Yeni kaynaklardaki kolon tipleri (string olarak gelen tarihler, "1.234,56 TL" gibi para formatları, karışık boolean gösterimleri) elle düzeltiliyor; hedef şemaya kolon eşleme (ör. `cust_id` → `customer_id`) manuel ve hataya açık.

**Kabul senaryoları:**
1. Kullanıcı yeni bir CSV kaynağı bağladığında sistem kolon tiplerini çıkarır (`"2024-01-05"` → date, `"₺1.234,50"` → decimal + currency=TRY) ve %90+ doğrulukla öneri tablosu sunar; kullanıcı tek tıkla onaylar.
2. Kullanıcı bir hedef şema (mevcut dataset veya DDL) seçtiğinde LLM destekli kolon eşleme çalışır; her eşleme güven skoru (0-1) ile listelenir, 0.7 altındakiler "gözden geçir" olarak işaretlenir.
3. Kullanıcı bir eşlemeyi düzelttiğinde düzeltme kaydedilir ve aynı kaynak için sonraki çıkarımlarda öncelikli kural olarak kullanılır.
4. Pipeline'da `schema.infer_map` node'u çalıştığında onaylanmamış düşük güvenli eşleme varsa run HITL onayına düşer.

## 2. Backend Tasarımı

**Agent:** `ai_data_science_team/agents/schema_inference_agent.py` — `SchemaInferenceAgent`. İki aşama: (a) deterministik tip çıkarımı (pandas + dateutil + regex tabanlı para/telefon/bool sezgileri, örneklem: ilk 10k satır), (b) LLM eşleme (kaynak kolon adı+örnek değerler+istatistikler → hedef kolon adayı + güven skoru + gerekçe).

**Node tipi:** `schema.infer_map` — `workflow_node_catalog_service.py` kataloğuna eklenir; executor `workflow_node_executor_service.py` içinde `_execute_schema_infer_map`.

I/O sözleşmesi:
```json
{
  "type": "schema.infer_map",
  "inputs": {"dataset_ref": "artifact://run/123/raw.parquet", "target_schema_ref": "schema://datasets/customers/v3"},
  "config": {"sample_rows": 10000, "min_confidence_auto_apply": 0.9, "normalize": ["dates", "currency", "booleans"], "on_low_confidence": "hitl"},
  "outputs": {
    "mapped_dataset_ref": "artifact://run/123/mapped.parquet",
    "mapping_report": {
      "columns": [{"source": "cust_id", "target": "customer_id", "inferred_type": "int64", "confidence": 0.97, "transform": "cast_int", "status": "auto"}],
      "unmapped_source": ["notes_free_text"], "unfilled_target": ["segment"]
    }
  }
}
```

**API endpoint'leri** (`routes/schema_inference.py`):
- `POST /api/schema/infer` — `{data_source_id | dataset_ref, sample_rows}` → tip çıkarım sonucu
- `POST /api/schema/map` — `{inference_id, target_schema_ref}` → eşleme önerileri
- `PUT /api/schema/mappings/{mapping_id}` — kullanıcı düzeltmesi (onay/değişiklik)
- `GET /api/schema/mappings?source_id=` — kayıtlı eşleme geçmişi

**Veri modeli (migration):** `schema_mappings` tablosu: `id, tenant_id, data_source_id, target_schema_ref, mapping_json, confidence_avg, status(draft|approved), created_by, created_at`. Kullanıcı düzeltmeleri `mapping_corrections` tablosunda (few-shot bellek olarak).

**Hata durumları:** örneklem okunamadı → `SCHEMA_SAMPLE_READ_ERROR`; LLM eşleme timeout → deterministik ad-benzerliği (rapidfuzz) fallback; hedef şema bulunamadı → 404; tip dönüşümünde satır bazlı hata → hatalı satırlar `rejects` artifact'ına ayrılır, eşik aşılırsa (config `max_reject_ratio`) node fail.

## 3. UI Tasarımı

**Ekran/bileşenler:** DataSources ekranına (`frontend/src/app/screens/DataSources.tsx`) "Şema Eşle" aksiyonu → **SchemaMappingTable** bileşeni: satır başına *kaynak kolon | örnek değerler (3 adet) | çıkarılan tip | hedef kolon (dropdown) | güven skoru rozeti | onayla/düzelt*.

**Etkileşim akışı:**
1. Kaynak seç → "Şema Çıkar" → örneklem analizi (progress stepper: okuma→tip çıkarımı→LLM eşleme).
2. Eşleme tablosu gelir; yüksek güvenli satırlar yeşil ön-onaylı, düşük güvenliler sarı vurgulu ve tabloda üste sıralı.
3. Kullanıcı dropdown'dan hedef değiştirir veya "eşleme yok" seçer → satır anında güncellenir.
4. "Tümünü Onayla ve Kaydet" → mapping approved; "Designer'a node olarak ekle" butonu `schema.infer_map` node'u üretir.

**Durumlar:** loading — satır iskeleti + adım stepper'ı; empty — "Bu kaynak için henüz eşleme yok" + CTA; error — hangi aşamada başarısız olduğu (örneklem/LLM) ve "deterministik modda tekrar dene" aksiyonu.

**Entegrasyon:** WorkflowDesigner node config panelinde kayıtlı mapping seçici; I2 katalog kolon kartlarında "eşlendiği hedef" bilgisi.

## 4. Bağımlılıklar

- **Spec:** B1 (profil istatistikleri girdi olarak kullanılır), I2 (hedef şema kaynağı), B7 (ingest pipeline'ında ilk adım), B2 (eşleme sonrası kalite kapısı).
- **Kütüphaneler:** `pandas`, `python-dateutil`, `rapidfuzz`, `visions` (tip çıkarımı), mevcut LLM istemcisi.
- **Kod entegrasyonu:** `apps/platform-api-app/platform_api/services/workflow_node_catalog_service.py` (katalog kaydı), `workflow_node_executor_service.py` (executor), `services/data_source_service.py` (örneklem okuma), `routes/data_sources.py` (aksiyon linki), `services/artifact_service.py` (rapor artifact'ı).

## 5. Kapsam Dışı

- Yapısal olmayan veri (serbest metin, JSON blob şema keşfi) — yalnız tablo verisi.
- Şema evrimi/drift takibi (J13 Data Diff kapsamı).
- Çok kaynaklı join eşlemesi (yalnız tek kaynak → tek hedef).
- Otomatik DDL üretimi/hedef tablo yaratma (B7 kapsamı).

## 6. Test & Definition of Done

**Senaryolar:**
- Birim: TR/EN tarih formatları, `1.234,56` ve `1,234.56` para formatları, `evet/hayır/1/0/true` boolean varyantları doğru çıkarılır.
- Birim: LLM yanıtı bozuksa rapidfuzz fallback devreye girer, node fail olmaz.
- E2E: CSV kaynak → infer → map → düzelt → onayla → `schema.infer_map` node'lu workflow çalışır, `mapped_dataset_ref` artifact'ı hedef şemaya uygun tiplerle üretilir.
- E2E: güven < 0.7 eşleme onaysızken run HITL kuyruğuna düşer.

**DoD checklist:**
- [ ] `schema.infer_map` katalogda ve `workflow_chain_validator` kurallarında
- [ ] 4 API endpoint + auth/tenant izolasyonu testleri
- [ ] `schema_mappings` migration'ı (alembic) uygulanmış
- [ ] SchemaMappingTable loading/empty/error durumlarıyla
- [ ] Düzeltme belleği: aynı kaynakta ikinci çıkarımda önceki düzeltme uygulanıyor
- [ ] Tip çıkarım doğruluğu test fikstüründe ≥ %90
