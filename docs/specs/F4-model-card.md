# F4 — Model Card (Otomatik Model Dokümantasyonu) (P2)

## 1. Amaç & Kullanıcı Hikâyeleri

Her kayıtlı model için Google Model Cards standardından uyarlanmış, otomatik doldurulan ve versiyonlanan dokümantasyon: veri, feature'lar, metrikler, sınırlamalar, lineage, kullanım amacı.

- **Yeni ekip üyesi olarak**, bir modelin ne verisiyle, hangi feature'larla, hangi performansla eğitildiğini tek sayfada okumak istiyorum.
- **Governance sorumlusu olarak**, üretimdeki her modelin güncel bir model card'ının PDF olarak dışa aktarılabilmesini istiyorum.
- **DS olarak**, otomatik doldurulamayan alanları (kullanım amacı, etik notlar) elle düzenleyip kaydetmek istiyorum.
- **Kabul:** Model kaydı sonrası card otomatik üretilir; F1/F2/F3 sonuçları geldikçe ilgili bölümler güncellenir; her güncelleme yeni versiyon oluşturur; PDF export çalışır.

## 2. Backend Tasarımı

### Agent / Servis
- Yeni dosya: `ml_agents/model_card_agent.py` — sınıf `ModelCardAgent`: MLflow run + registry + artifact metadata'sından yapısal bölümleri toplar; LLM yalnız "özet/sınırlamalar taslağı" bölümlerinde kullanılır (kaynak verilerle grounded, `draft: true` işaretli).
- Yeni servis: `platform_api/services/model_card_service.py` — `generate_card(model_id)`, `update_card_section(model_id, section, content)`, `render_pdf(model_id, version)` (WeasyPrint ile HTML→PDF).

### Node Tipi & I/O Sözleşmesi
- Node tipi: `model.card_generate` (retrain pipeline'ının son adımına eklenebilir).

```json
{
  "input": {"model_id": "uuid", "include_sections": ["data", "features", "metrics", "fairness", "limitations", "lineage"]},
  "output": {
    "card_id": "uuid", "version": 3,
    "sections": {
      "overview": {"name": "churn_xgb", "version": "v3", "owner": "erhan", "created_at": "..."},
      "data": {"dataset": "churn_2026q2", "rows": 48211, "train_test_split": "80/20", "date_range": "..."},
      "features": [{"name": "tenure", "type": "numeric", "importance": 0.21}],
      "metrics": {"auc": 0.861, "f1": 0.64, "calibration_ece": 0.042},
      "fairness": {"source_artifact": "uuid", "summary": "..."},
      "limitations": {"draft": true, "text": "..."},
      "lineage": {"source_run_id": "uuid", "upstream_datasets": ["uuid"]}
    }
  }
}
```

### API Endpoint'leri (`routes/modelops.py`)
- `POST /modelops/models/{model_id}/card` — üret/yeniden üret.
- `GET /modelops/models/{model_id}/card?version=n` — oku (default: son versiyon).
- `PATCH /modelops/models/{model_id}/card/sections/{section}` — manuel düzenleme (yeni versiyon açar).
- `GET /modelops/models/{model_id}/card/pdf` — PDF export.

### Veri Modeli / Migration
- Yeni tablo `model_cards`: `id, workspace_id, model_id, version INT, sections_json, edited_sections JSON, created_by, created_at` (model_id+version unique). Alembic migration `add_model_cards`.

### Hata Durumları
- Model bulunamadı → 404. MLflow run erişilemiyor → card yine üretilir, eksik bölümler `unavailable: true` + neden.
- F3 fairness artifact'ı yoksa → bölüm "Audit yapılmadı" placeholder'ı.
- PDF render hatası → 500 `PDF_RENDER_FAILED`, JSON card etkilenmez.
- Eşzamanlı PATCH çakışması → optimistic lock (version kontrolü) → 409.

## 3. UI Tasarımı

- Konum: K2 model detayının **"Genel Bakış"** sekmesi = model card görünümü.
- Bileşenler: bölüm kartları (accordion); feature tablosu `DataTable` (importance bar'lı); metrik `MetricCard` grid'i; lineage mini grafiği (J12'ye "tam grafiği aç" linki); LLM taslak bölümlerinde "AI taslağı — gözden geçir" sarı rozeti ve inline düzenleme (K3 şeffaflık standardı); sağ üstte versiyon seçici + "PDF indir" butonu.
- Akış: sekme açılır → son card yüklenir; "Yeniden üret" → progress; bölüm düzenle → kaydet → yeni versiyon toast'ı.
- Durumlar: loading = bölüm skeleton'ları; empty = "Card üretilmedi" + "Şimdi üret" CTA; error = bölüm bazlı hata (bir bölüm hata verirse diğerleri render edilir).

## 4. Bağımlılıklar

- Spec: F1 (kalibrasyon/segment metrikleri), F2 (karşılaştırma geçmişi bölümü), F3 (fairness bölümü), J12 (lineage), G5 (stage bilgisi), K2/K3.
- Kütüphaneler: `mlflow` (run/param/metric okuma), `weasyprint` (PDF), `jinja2` (HTML şablonu).
- Kod: `services/modelops_service.py::_persisted_registry_entry` (card'ın overview kaynağı), `ml_agents/model_evaluation_agent.py` çıktı artifact'ları.

## 5. Kapsam Dışı

- Dış paylaşım/public card hosting.
- Çok dilli card üretimi (yalnız Türkçe/İngilizce alan içerikleri, çeviri yok).
- Dataset card'ları (ayrı bir I2/B1 genişletmesi).

## 6. Test & Definition of Done

- Birim: bölüm toplayıcıların eksik kaynakta `unavailable` üretmesi; versiyon artışı ve optimistic lock; PDF render smoke test.
- Entegrasyon: model kaydı → otomatik card; F3 audit sonrası fairness bölümünün güncellenmesi (yeni versiyon).
- E2E: UI'da card görüntüle → bölüm düzenle → versiyon değişimi → PDF indir (Playwright + dosya varlığı).
- DoD: card üretimi registry'ye kayıtla tetikleniyor, 4 endpoint çalışıyor, PDF çıktısı tüm dolu bölümleri içeriyor, PLATFORM_SPEC F4 ✍️.
