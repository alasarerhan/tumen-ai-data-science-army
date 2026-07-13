# E7 — Survival Analysis

## 1. Amaç & Kullanıcı Hikâyeleri

"Olay ne zaman gerçekleşir" sorularını (churn zamanı, ekipman arızası, üyelik iptali) sansürlü veriyle doğru modellemek: Kaplan-Meier eğrileri, Cox Proportional Hazards ve grup karşılaştırmaları.

- **DS olarak**, müşteri tenure + churn bayrağı verisiyle Kaplan-Meier eğrisi çizmek istiyorum ki kohortların hayatta kalma davranışını görebileyim.
- **Analist olarak**, segment bazlı (plan tipi, kanal) eğrileri log-rank testiyle karşılaştırmak istiyorum ki farkın anlamlı olup olmadığını bileyim.
- **DS olarak**, Cox PH ile kovaryat etkilerini (hazard ratio + CI) tablo halinde görmek istiyorum ki hangi faktörün riski artırdığını raporlayayım.

Kabul senaryosu: dataset + duration/event kolon seçimi → KM eğrisi (CI bantlı) → grup kolonu seçilirse çoklu eğri + log-rank p-değeri → Cox PH → HR tablosu + PH varsayım kontrolü → anlatı özeti.

## 2. Backend Tasarımı

### Agent
- **Sınıf:** `SurvivalAnalysisAgent` — yeni dosya `ai_data_science_team/ml_agents/survival_agent.py` (`_TimeSeriesAgentMixin` benzeri artifact helper'larıyla, `BaseAgent` üstünde ReAct).
- Tool'lar (`ai_data_science_team/tools/survival.py`): `fit_kaplan_meier`, `logrank_test_groups`, `fit_cox_ph`, `check_ph_assumptions` (`proportional_hazard_test`), `predict_survival_function`, `median_survival_summary`. Hepsi `lifelines` üzerine ince sarmalayıcı; JSON-serileştirilebilir çıktı döner.

### Node tipi: `survival.analyze`
```json
{
  "type": "survival.analyze",
  "label": "Survival Analysis",
  "category": "Modeling",
  "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": true}],
  "outputs": [
    {"name": "survival_report", "artifact_type": "survival_report", "required": true},
    {"name": "model", "artifact_type": "model", "required": false}
  ],
  "ui": {"icon": "activity", "color": "teal", "config": [
    {"key": "duration_column", "type": "string", "required": true},
    {"key": "event_column", "type": "string", "required": true},
    {"key": "group_column", "type": "string", "required": false},
    {"key": "covariates", "type": "multi_select", "required": false},
    {"key": "method", "type": "select", "options": ["kaplan_meier", "cox_ph", "both"], "required": true}
  ]},
  "timeout_seconds": 900,
  "retry_policy": {"max_attempts": 1, "backoff_seconds": 15},
  "resources": {"class": "cpu_medium"}
}
```
`survival_report` artifact şeması: `{"km_curves": [{"group": "A", "timeline": [...], "survival": [...], "ci_lower": [...], "ci_upper": [...]}], "logrank": {"statistic": .., "p_value": ..}, "cox": {"hazard_ratios": [{"covariate": "age", "hr": 1.03, "ci": [1.01, 1.05], "p": 0.002}], "concordance": 0.71, "ph_violations": ["plan_type"]}, "narrative": "..."}`

Executor: `_execute_survival_analyze` → `get_default_node_executors()`.

### API endpoint'leri
- `POST /api/survival/analyze` — ad-hoc analiz (chat/inline kullanım için, node dışı).
- `GET /api/survival/reports/{artifact_id}` — rapor artifact'ının JSON'u.
- `POST /api/survival/models/{model_id}/predict` — kovaryat satırları → bireysel survival eğrileri.

### Veri modeli
- Yeni artifact tipi: `survival_report`. Model artifact'ı: pickle `CoxPHFitter`. Migration gerekmez (artifact tabanlı).

### Hata durumları
- event kolonu 0/1 değil → tip dönüşüm denemesi, başarısızsa açıklayıcı hata.
- Negatif duration → fail + sorunlu satır sayısı.
- Cox yakınsamazsa (`ConvergenceError`) → penalizer artırılarak 1 retry; hâlâ olmazsa yüksek korelasyonlu kovaryat uyarısıyla fail.
- PH varsayımı ihlali → hata değil; raporda `ph_violations` + strata önerisi.

## 3. UI Tasarımı

### Bileşenler
- `SurvivalCurveChart` — ECharts line: basamaklı (step) KM eğrileri + CI alan bandı; grup başına renk; hover'da t anındaki S(t) ve risk altındaki sayı.
- `HazardRatioTable` — kovaryat, HR, %95 CI, p; HR forest plot mini görseli satır içinde; PH ihlali olan satırda uyarı rozeti.
- `MedianSurvivalCards` — grup başına medyan yaşam süresi kartları.
- `LogRankBanner` — p-değeri + "gruplar arasında anlamlı fark var/yok" cümlesi.

### Akış
1. Node config: dataset şemasından duration/event/group kolonları dropdown'la seçilir.
2. Run → rapor sekmesi: eğri grafiği üstte, log-rank banner'ı, altında Cox tablosu + anlatı.
3. "Rapora ekle" aksiyonu C5 rapor şablonuna kartları taşır.

### Durumlar
- **Loading:** grafik alanında skeleton + "eğriler hesaplanıyor".
- **Empty:** event oranı %0 ise "Hiç olay gözlenmemiş — sansür oranı %100" bilgilendirmesi.
- **Error:** yakınsama hatasında hangi kovaryatların şüpheli olduğu listelenir + "kovaryat çıkar ve yeniden dene" aksiyonu.

### Entegrasyon
- WorkflowDesigner paleti; ModelOps model detayında Cox modeli için "Survival" sekmesi; chat'te inline sonuç kartı (A4 danışman deseniyle).

## 4. Bağımlılıklar

- **Spec:** K3, C5 (rapor export), G4 (predict).
- **Kütüphaneler:** `lifelines` (KaplanMeierFitter, CoxPHFitter, logrank_test), `pandas`.
- **Kod:** node catalog/executor, `_load_latest_dataframe`, `_write_json_artifact`.

## 5. Kapsam Dışı

- Parametrik modeller (Weibull AFT), competing risks, time-varying covariates.
- ML tabanlı survival (random survival forest, DeepSurv).
- Gerçek zamanlı risk skorlama servisi.

## 6. Test & Definition of Done

- **Birim:** `fit_kaplan_meier` lifelines'ın Rossi dataset'inde bilinen medyan süreyle eşleşir; `logrank_test_groups` p-değeri lifelines referansıyla aynı; negatif duration hatası doğru fırlar.
- **E2E:** telco-churn fixture → `survival.analyze` (method=both) run → `survival_report` artifact'ı şemaya uyar; UI eğrileri ve HR tablosunu render eder.
- **Hata testi:** tek gruplu veri + group_column → log-rank atlanır, rapor yine üretilir.
- **DoD:** node katalogda ve çalışır, rapor şeması dokümante, CI bantlı eğri grafiği renk-körü güvenli paletle çizilir, testler yeşil.
