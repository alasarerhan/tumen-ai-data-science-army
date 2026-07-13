# J6 — Responsible AI Dashboard

## 1. Amaç & Kullanıcı Hikâyeleri

**Amaç:** F3 fairness denetimi, explainability (global/lokal SHAP) ve hata analizi (segment bazlı hata dilimleri) çıktılarının tek model-detay ekranında birleştirilmesi; "bu model kimin için kötü çalışıyor ve neden" sorusuna tek bakışta cevap.

**Kullanıcı hikâyeleri:**
- Bir DS olarak, korumalı gruplar (cinsiyet, yaş bandı) bazında demographic parity / equalized odds farklarını görmek istiyorum.
- Bir DS olarak, en yüksek hata oranlı veri dilimlerini (ör. `tenure < 3 AND region = 'X'`) otomatik keşfetmek istiyorum.
- Bir risk sorumlusu olarak, adalet eşiği ihlallerini rozet olarak registry'de görmek ve J7 governance checklist'ine kanıt olarak eklemek istiyorum.

**Kabul:** Bir sınıflandırma modeli için dashboard 30 sn içinde fairness metrikleri + global SHAP + en kötü 10 dilimi gösterir; ihlal varsa uyarı banner'ı ve azaltma önerileri listelenir.

## 2. Backend Tasarımı

**Servis/Agent:**
- `apps/platform-api-app/platform_api/services/responsible_ai_service.py` — analiz job orkestrasyonu, sonuç artifact'larının okunması/önbelleklenmesi.
- `ai_data_science_team/agents/responsible_ai_agent.py` — üç analizör: fairness (F3 motorunu çağırır), explainability (SHAP TreeExplainer/KernelExplainer), error slicing (karar ağacı tabanlı dilim keşfi + dilim başına metrik).

**Node tipi:** `model.responsible_audit` — pipeline'da değerlendirme sonrası opsiyonel kapı.

```json
{
  "type": "model.responsible_audit",
  "inputs": {"model": "artifact://model_7", "eval_dataset": "artifact://ds_test"},
  "params": {
    "protected_attributes": ["gender", "age_band"],
    "fairness_metrics": ["demographic_parity", "equalized_odds"],
    "fairness_threshold": 0.1,
    "explainability": {"method": "shap", "sample_size": 2000},
    "error_slicing": {"max_depth": 3, "min_slice_size": 50}
  },
  "outputs": {"audit_report": "artifact://rai_report_v1", "passed": true}
}
```

**API endpoint'leri:**
- `POST /api/models/{model_id}/responsible-ai/analyze` — job başlat (async)
- `GET /api/models/{model_id}/responsible-ai` — son rapor (fairness/explainability/slices bölümleri)
- `GET /api/models/{model_id}/responsible-ai/explain/local?row_id=...` — tekil tahmin SHAP katkıları
- `GET /api/models/{model_id}/responsible-ai/history` — rapor versiyonları (trend)

**Veri modeli:** `rai_reports` (id, model_id, model_version, report_artifact_id, fairness_status enum[pass|warn|fail], created_at). Rapor gövdesi artifact olarak `artifact_storage_service.py` üzerinde JSON.

**Hata durumları:** korumalı kolon dataset'te yok → 422 + kolon önerisi; SHAP desteklemeyen model tipi → explainability bölümü `unsupported` işaretli, diğer bölümler üretilir; örneklem çok küçük (<200) → `warn` + güven notu; job timeout → kısmi rapor kaydedilir.

## 3. UI Tasarımı

**Bileşenler:** Model detayında **"Responsible AI" sekmesi** (K2 sekme çubuğuna eklenir):
- `FairnessPanel.tsx` — grup bazlı bar grafikleri (metrik başına gruplar yan yana, eşik çizgisi kesikli), ihlalde kırmızı StatusBadge + azaltma önerisi kartları (reweighing, threshold per group).
- `ExplainabilityPanel.tsx` — global SHAP özet grafiği (beeswarm/bar toggle), feature seç → dependence plot; "satır seç → lokal açıklama" waterfall grafiği.
- `ErrorSlicesTable.tsx` — DataTable: dilim tanımı (okunur koşul), boyut, hata oranı, baseline'a göre delta; satır tıkla → dilimin örnek satırları popover.

**Akış:** Sekme açılır → rapor varsa göster + "Yeniden analiz et"; yoksa CTA'lı empty state → job progress stepper (fairness → SHAP → slicing) → sonuç. Fairness `fail` ise sekme başlığında kırmızı nokta, registry satırında rozet.

**Durumlar:** loading: panel skeleton'ları; empty: "Analiz henüz çalıştırılmadı" + Analiz Et CTA; error: hangi analizörün düştüğü + kısmi sonuç gösterimi.

**Entegrasyon:** K2 model detay sekmesi; F4 model card'a fairness özeti bölümü; J7 checklist'i `fairness_status`'u kanıt olarak okur.

## 4. Bağımlılıklar

- F3 (fairness metrik motoru — bu spec onu ekrana taşır), F4, J7, K2, K3 (ChartContainer/DataTable/StatusBadge).
- Kütüphaneler: `shap`, `fairlearn` (adaylar); ECharts.
- Kod noktaları: `services/artifact_service.py`, model registry servisleri.

## 5. Kapsam Dışı

- LLM/GenAI model denetimi, counterfactual üretimi, otomatik bias azaltma uygulaması (yalnız öneri), regresyon modelleri için fairness (ilk sürüm sınıflandırma), gerçek zamanlı üretim trafiği analizi (G1'in alanı).

## 6. Test & Definition of Done

- Birim: fairness metrik hesapları bilinen sentetik veride doğrulanır; slice keşfi min_slice_size'ı ihlal etmez; SHAP unsupported fallback.
- E2E: model eğit → audit node çalıştır → sekmede üç panel dolu; eşik ihlali senaryosunda `fail` rozeti + K2 registry sinyali.
- DoD: rapor versiyonlanıyor (history), lokal açıklama < 3 sn dönüyor, tüm grafikler renk-körü güvenli palette (K3).
