# G4 — Batch Scoring + `model.predict` Node (P0)

## 1. Amaç & Kullanıcı Hikâyeleri

Bugün platformda pipeline içinde **tahmin node'u hiç yok**: model eğitiliyor, registry'ye kaydediliyor ama kayıtlı bir modelle yeni veri üzerinde toplu skor üretmenin görsel yolu bulunmuyor (`agents/model_serving_agent.py` yalnız in-process `run_inference` sunar, workflow'a bağlı değildir). Bu spec kapalı döngünün kritik boşluğunu kapatır.

- **DS olarak**, Designer'da `model.predict` node'unu sürükleyip kayıtlı bir model versiyonu seçerek gelen dataset'i skorlamak istiyorum ki her gece churn skorları otomatik üretilsin.
- **ML engineer olarak**, çıktıyı hem artifact (parquet) hem hedef tabloya yazabilmek istiyorum ki downstream sistemler tüketebilsin.
- **Kabul senaryosu 1:** `data.load → model.predict → data.write` pipeline'ı cron ile çalışır, skor kolonu eklenmiş dataset artifact'ı üretir.
- **Kabul senaryosu 2:** Model şeması ile gelen dataset şeması uyuşmazsa node, eksik/fazla kolon listesiyle anlaşılır hata verir; run FAILED olur.
- **Kabul senaryosu 3:** UI'da sonuç önizleme tablosunda ilk 20 satır + tahmin kolonu görünür.

## 2. Backend Tasarımı

### Agent / sınıf
- **Yeni:** `ai_data_science_team/agents/batch_scoring_agent.py` — `BatchScoringAgent`. Mevcut `ModelServingAgent.load_model/run_inference`'ı yeniden kullanır; chunk'lı skorlama (`chunk_size` param, default 50k satır) ekler.
- `modelops_service.py` üzerinden model versiyonu çözümü (`get_model_version(model_id, version|stage)`).

### Node tipi + I/O sözleşmesi
Node tipi: `model.predict` (runtime_engine node registry'sine eklenir).

```json
{
  "type": "model.predict",
  "config": {
    "model_id": "churn_xgb",
    "version": "3",            
    "stage": null,              
    "feature_columns": "auto",  
    "prediction_column": "prediction",
    "include_probabilities": true,
    "output": { "target": "artifact", "format": "parquet", "table": null },
    "chunk_size": 50000
  },
  "inputs":  { "dataset": "<upstream_node_output_ref>" },
  "outputs": {
    "scored_dataset": { "type": "dataframe_artifact", "schema": "input + prediction[+proba_*]" },
    "scoring_report": { "rows_scored": 120000, "duration_s": 14.2, "model_uri": "models:/churn_xgb/3" }
  }
}
```

`version` ve `stage` birbirini dışlar; `stage` verilirse (örn. `Production`) G5 promotion durumundan çözülür.

### API endpoint'leri
- `GET  /api/models/{model_id}/versions` — versiyon picker için (mevcut modelops route'larına eklenir/genişletilir).
- `POST /api/predict/batch` — ad-hoc skorlama (body: model_id, version, dataset_id, output). Pipeline dışı "hemen skorla" akışı da aynı agent'ı kullanır.
- `GET  /api/predict/batch/{job_id}` — durum + önizleme (ilk 20 satır).

### Veri modeli / migration
- `scoring_jobs` tablosu: `id, model_id, model_version, dataset_ref, output_ref, rows_scored, status(queued|running|succeeded|failed), error, started_at, finished_at, workflow_run_id (nullable)`.
- Artifact store'a `scored_dataset` tipi eklenir.

### Hata durumları
- `MODEL_NOT_FOUND` (404), `VERSION_NOT_FOUND` (404), `SCHEMA_MISMATCH` (422; payload: `missing_columns`, `unexpected_columns`, `dtype_conflicts`), `MODEL_LOAD_ERROR` (500, model dosyası bozuk), `OUTPUT_WRITE_ERROR` (hedef tabloya yazılamadı — çıktı artifact olarak yine saklanır, uyarı ile). Tüm hatalar `scoring_report`'a işlenir; quota_service üzerinden compute maliyeti kaydedilir.

## 3. UI Tasarımı

### Bileşenler
- **Designer paleti:** "Model" grubuna `Predict` node'u (K1 zengin node kartı standardında).
- **Node config paneli (sağ drawer):**
  - Model seçici: model listesi → versiyon picker (versiyon no + stage rozeti + kayıt tarihi + ana metrik); "en son Production" kısayolu.
  - Çıktı hedefi: `Artifact (parquet/csv)` veya `Tabloya yaz` (kayıtlı data source + tablo adı + append/overwrite).
  - Gelişmiş: prediction kolon adı, probability dahil et, chunk size.
- **Sonuç önizleme:** run detayında node çıktısı sekmesi — ilk 20 satır DataTable (K3), tahmin kolonu vurgulu; `rows_scored`, süre, model URI metrik kartları.

### Akış
Sürükle → model seç → versiyon seç → çıktı hedefi → inline validasyon (K1) upstream dataset şemasını model imzasıyla karşılaştırıp uyarı rozetini node üstünde gösterir → çalıştır.

### Loading / empty / error
- Loading: versiyon listesi yüklenirken skeleton; skorlama sırasında node kartında progress (chunk x/y).
- Empty: hiç kayıtlı model yoksa "Önce bir model eğitin" CTA'sı (Designer'a train node ekleme linki).
- Error: `SCHEMA_MISMATCH` node üzerinde kırmızı rozet + panelde eksik kolon listesi ve "B3 eşleme sihirbazını aç" önerisi.

### Mevcut ekran entegrasyonu
`ModelOps.tsx` model detayına "Batch skorla" aksiyonu (ad-hoc `POST /api/predict/batch` formu). Run history mevcut run detay ekranını kullanır.

## 4. Bağımlılıklar
- Mevcut kod: `agents/model_serving_agent.py`, `modelops_service.py`, runtime_engine node registry, artifact store, `services/quota_service.py`.
- Spec'ler: G5 (stage çözümü — opsiyonel, `version` ile bağımsız çalışır), /(UI standartları), B3 (şema eşleme önerisi — sadece link).
- Kütüphaneler: pandas, pyarrow (parquet), mlflow (model URI çözümü varsa).
## 5. Kapsam Dışı
- Online/realtime serving (G3), shadow/canary (J11), tahmin sonrası drift hesabı (G1 tüketir ama burada hesaplanmaz), streaming skorlama, GPU batch inference.

## 6. Test & Definition of Done
- **Birim:** şema doğrulama (eksik/fazla kolon, dtype), version vs stage çözümü, chunk'lı skorlamada satır sayısı korunumu, çıktı format (parquet/csv) yazımı.
- **Entegrasyon:** sklearn pickle + XGBoost model ile uçtan uca `data.load → model.predict` run'ı; hedef tabloya yazma (sqlite ile).
- **E2E (UI):** Designer'da node ekle-konfigüre et-çalıştır; önizleme tablosunda tahmin kolonu görünür; SCHEMA_MISMATCH senaryosunda hata paneli.
- **DoD:** `model.predict` node registry'de; ad-hoc API çalışıyor; scoring_jobs migration uygulanmış; tüm hata kodları testli; PLATFORM_SPEC durum tablosu ✍️.
