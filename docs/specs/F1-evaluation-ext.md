# F1 — Evaluation Genişletmesi (Kalibrasyon, Maliyet-Tabanlı Threshold, Segment Performansı)

## 1. Amaç & Kullanıcı Hikâyeleri

Mevcut `ml_agents/model_evaluation_agent.py` temel metrikleri üretiyor; bu spec üç kritik eksikliği kapatır: (a) olasılık kalibrasyonu, (b) iş maliyet matrisiyle threshold optimizasyonu, (c) segment bazlı performans.

- **DS olarak**, modelimin tahmin olasılıklarının kalibre olup olmadığını (reliability diagram, Brier score, ECE) görmek istiyorum ki risk skorlarına güvenebileyim.
- **İş analisti olarak**, FP/FN maliyetlerini girip beklenen maliyeti minimize eden karar eşiğini bulmak istiyorum.
- **ML mühendisi olarak**, modelin hangi müşteri segmentinde (kategorik kolon kırılımında) zayıf olduğunu tabloda görmek istiyorum.
- **Kabul:** Eğitilmiş bir sınıflandırma modeli için tek node çalıştırmasıyla kalibrasyon grafiği, optimal threshold ve segment tablosu artifact olarak üretilir; UI'da model detayında görüntülenir.

## 2. Backend Tasarımı

### Agent
- Dosya: `ml_agents/model_evaluation_agent.py` — mevcut `ModelEvaluationAgent` genişletilir (yeni sınıf yok):
  - `evaluate_calibration(y_true, y_prob)` → `sklearn.calibration.calibration_curve`, Brier score, ECE (10 bin); isteğe bağlı `CalibratedClassifierCV` (isotonic/sigmoid) önerisi.
  - `optimize_threshold(y_true, y_prob, cost_matrix)` → threshold taraması (0.01 adım), beklenen maliyet eğrisi, argmin threshold.
  - `evaluate_segments(df, y_true, y_pred, segment_cols)` → segment başına metrik seti + destek (n).

### Node Tipi & I/O Sözleşmesi
- Node tipi: `model.evaluate_extended` (`services/workflow_node_executor_service.py`'ye executor kaydı; `workers/workflow_worker.py` değişmeden çalışır).

```json
{
  "input": {
    "model_artifact_id": "uuid",
    "dataset_artifact_id": "uuid",
    "target_column": "churn",
    "cost_matrix": {"fp": 5.0, "fn": 50.0, "tp": 0.0, "tn": 0.0},
    "segment_columns": ["region", "plan_type"],
    "calibration_bins": 10
  },
  "output": {
    "calibration": {"brier": 0.089, "ece": 0.042, "curve": [{"mean_pred": 0.1, "frac_pos": 0.08}]},
    "threshold": {"optimal": 0.31, "expected_cost": 1240.5, "cost_curve": [{"t": 0.1, "cost": 2100.0}]},
    "segments": [{"segment": "region=EU", "n": 1200, "auc": 0.81, "f1": 0.62}],
    "artifact_id": "uuid"
  }
}
```

### API Endpoint'leri (routes/modelops.py'ye ek)
- `POST /modelops/models/{model_id}/evaluations/extended` — değerlendirmeyi senkron/asenkron başlatır (büyük veri → workflow run).
- `GET /modelops/models/{model_id}/evaluations/extended/latest` — son sonuç.

### Veri Modeli / Migration
- Yeni tablo yok; sonuç `Artifact` (kind=`evaluation_extended`, JSON metadata) olarak saklanır ve `record_monitor_snapshot()` ile `performance` tipinde snapshot'a bağlanır. Migration gerekmez.

### Hata Durumları
- Model olasılık üretemiyorsa (`predict_proba` yok) → 422 `MODEL_NOT_PROBABILISTIC`.
- Segment kolonu dataset'te yoksa → 422 `SEGMENT_COLUMN_MISSING` (kolon adı listesiyle).
- Segment kardinalitesi > 50 → uyarıyla ilk 50 segment; `warnings[]` alanında raporlanır.
- Maliyet matrisi negatif/eksik → 400 doğrulama hatası.

## 3. UI Tasarımı

- Konum: `ModelOps.tsx` model detayının **Değerlendirme** sekmesi (K2 sekme yapısına uyumlu).
- Bileşenler (K3 kitaplığı): `ChartContainer` içinde reliability diagram (ideal 45° çizgi + model eğrisi); **Maliyet Matrisi Editörü** — 2x2 sayısal grid (`MetricCard` düzeni) + threshold slider'ı; slider hareketi maliyet eğrisi üzerindeki noktayı ve confusion matrix'i canlı günceller; **Segment tablosu** — `DataTable`, metriğe göre sıralanabilir, genel ortalamanın %10 altındaki hücreler kırmızı vurgulu.
- Akış: sekme açılır → son değerlendirme yüklenir → "Yeniden değerlendir" butonu node'u tetikler → toast + polling.
- Durumlar: loading = skeleton grafik; empty = "Henüz genişletilmiş değerlendirme yok" + "Şimdi çalıştır" CTA; error = hata kodu Türkçe mesaja çevrilmiş banner + "tekrar dene".

## 4. Bağımlılıklar

- Spec: F2 (aynı metrik hesaplayıcıları paylaşır), J4 (sonuçlar evaluation store'a akar), K2/K3 (UI yüzeyi).
- Kütüphaneler: `scikit-learn` (calibration_curve, CalibratedClassifierCV, metrics), `numpy`, mevcut `mlflow` loglama.
- Kod entegrasyonu: `ml_agents/model_evaluation_agent.py`, `services/workflow_node_executor_service.py`, `services/modelops_service.py::record_monitor_snapshot`.

## 5. Kapsam Dışı

- Regresyon kalibrasyonu (conformal prediction) — F5/ileri faz.
- Fairness metrikleri (F3'te), istatistiksel model karşılaştırma (F2'de).
- Otomatik yeniden kalibrasyon (recalibrate-and-save) — yalnız öneri metni üretilir.

## 6. Test & Definition of Done

- Birim: sentetik kalibre/kalibresiz veriyle ECE ayrımı; cost_matrix ile bilinen optimum threshold'un bulunması; eksik segment kolonu → doğru hata kodu.
- E2E: eğitim → `model.evaluate_extended` node'u → artifact üretimi → API'den okuma → UI render (Playwright).
- DoD: üç analiz tek node'da çalışır, sonuç artifact + snapshot yazılır, UI sekmesi üç durumda (loading/empty/error) doğru davranır, PLATFORM_SPEC durum tablosu ✍️ yapılır.
