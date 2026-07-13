# F3 — Fairness & Bias Audit (P2)

## 1. Amaç & Kullanıcı Hikâyeleri

Model tahminlerinin korunan gruplar (cinsiyet, yaş bandı, bölge vb.) arasında adil olup olmadığını ölçmek ve azaltma (mitigation) önerileri sunmak.

- **DS olarak**, modelimin demographic parity / equalized odds farklarını grup bazında görmek istiyorum.
- **Governance sorumlusu olarak**, üretime çıkan her modelin fairness raporunun kayıtlı olmasını istiyorum (J7 checklist girdisi).
- **ML mühendisi olarak**, adaletsizlik tespit edilirse hangi mitigation tekniğinin (reweighing, threshold ayarı) ne kadar iyileştireceğini simüle etmek istiyorum.
- **Kabul:** Hassas kolon(lar) seçilir → grup bazlı metrik tablosu + fark oranları + eşik ihlali bayrakları + öneri listesi artifact olarak üretilir ve J6 dashboard'unda görüntülenir.

## 2. Backend Tasarımı

### Agent
- Yeni dosya: `ml_agents/fairness_audit_agent.py` — sınıf `FairnessAuditAgent`:
  - `fairlearn.metrics.MetricFrame` ile grup bazlı: selection rate, TPR, FPR, precision.
  - Türetilen metrikler: `demographic_parity_difference/ratio`, `equalized_odds_difference` (fairlearn fonksiyonları).
  - İhlal kuralı: 80% kuralı (disparate impact ratio < 0.8) veya kullanıcı eşiği.
  - Mitigation simülasyonu: `fairlearn.postprocessing.ThresholdOptimizer` (equalized_odds) ile "düzeltme sonrası" metrikler; reweighing önerisi metin olarak.

### Node Tipi & I/O Sözleşmesi
- Node tipi: `model.fairness_audit`.

```json
{
  "input": {
    "model_artifact_id": "uuid", "dataset_artifact_id": "uuid",
    "target_column": "approved", "sensitive_columns": ["gender", "age_band"],
    "fairness_threshold": 0.8, "simulate_mitigation": true
  },
  "output": {
    "groups": [{"column": "gender", "group": "F", "n": 4300, "selection_rate": 0.21, "tpr": 0.68, "fpr": 0.09}],
    "disparities": [{"column": "gender", "metric": "demographic_parity_ratio", "value": 0.74, "violation": true}],
    "mitigation": {"method": "threshold_optimizer", "post_disparity_ratio": 0.91, "auc_cost": -0.008},
    "recommendations": ["gender için grup bazlı threshold öner..."],
    "artifact_id": "uuid"
  }
}
```

### API Endpoint'leri (`routes/modelops.py`)
- `POST /modelops/models/{model_id}/fairness-audits` — audit başlat.
- `GET /modelops/models/{model_id}/fairness-audits/latest` · `GET /modelops/fairness-audits/{id}`.

### Veri Modeli / Migration
- Yeni tablo yok: sonuç `Artifact` (kind=`fairness_audit`) + `record_monitor_snapshot()` ile `fairness` tipinde snapshot (mevcut snapshot şeması `monitor_type` alanını serbest metin kabul ediyor). Migration gerekmez.

### Hata Durumları
- Hassas kolon dataset'te yok → 422 `SENSITIVE_COLUMN_MISSING`.
- Bir grupta n < 30 → o grup `low_support: true` işaretlenir, disparity hesabından hariç tutulur ve uyarı üretilir.
- Regresyon modeli → 422 `UNSUPPORTED_PROBLEM_TYPE` (ilk sürüm yalnız sınıflandırma).
- Mitigation simülasyonu başarısız olursa audit sonucu yine döner, `mitigation: null` + uyarı.

## 3. UI Tasarımı

- Konum: J6 Responsible AI Dashboard sekmesi (model detayı); J6 hazır değilse `ModelOps.tsx` model detayında "Fairness" sekmesi olarak başlar.
- Bileşenler: hassas kolon seçici (multi-select, B5 PII rozetli kolonlar önerilir); grup bazlı **bar grafikleri** (`ChartContainer`: selection rate / TPR / FPR, gruplar yan yana, ihlal eşiği kesikli çizgi); disparity `DataTable` — ihlal satırları `StatusBadge: "İhlal"`; mitigation kartı: "Düzeltme uygulansa: parity 0.74 → 0.91, AUC maliyeti −0.008" karşılaştırmalı `MetricCard` çifti.
- Akış: kolon seç → "Audit çalıştır" → progress stepper (skorlama → metrikler → simülasyon) → sonuç.
- Durumlar: loading = stepper; empty = "Henüz fairness audit yok" + kolon seçim CTA; error = eyleme dönük mesaj ("hassas kolon eksik: gender").

## 4. Bağımlılıklar

- Spec: F1 (skorlanmış tahmin altyapısı), F4 (model card fairness bölümünü bu artifact'tan okur), J6/J7, B5 (PII/hassas kolon adayları), K3.
- Kütüphaneler: `fairlearn>=0.10`, `scikit-learn`, `pandas`.
- Kod: `ml_agents/model_evaluation_agent.py` (ortak skorlayıcı yardımcıları), `services/modelops_service.py`.

## 5. Kapsam Dışı

- In-processing mitigation (adversarial debiasing, ExponentiatedGradient ile yeniden eğitim) — yalnız post-processing simülasyonu.
- Kesişimsel (intersectional) grup analizi (gender×age) — ilk sürüm tek kolon bazlı.
- Bireysel adalet (counterfactual fairness) metrikleri.

## 6. Test & Definition of Done

- Birim: bilinen sentetik yanlı veri setinde disparate impact < 0.8 tespiti; düşük destekli grup hariç tutma; fairlearn metrik değerleriyle birebir eşleşme.
- Entegrasyon: audit → artifact + fairness snapshot kaydı; F4 model card'ın alanı doldurması.
- E2E: UI'dan kolon seç → audit → bar grafikler + ihlal rozetleri render (Playwright).
- DoD: node workflow'da çalışır, API üçlüsü hazır, UI sekmesi üç durumda doğru, PLATFORM_SPEC F3 ✍️.
