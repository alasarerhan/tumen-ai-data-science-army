# F2 — Champion–Challenger Karşılaştırması (P0)

## 1. Amaç & Kullanıcı Hikâyeleri

İki (veya daha fazla) modeli **aynı test protokolünde** karşılaştırıp istatistiksel anlamlılıkla promotion kararı üretmek. G2 kapalı döngüsünün "değerlendirme" halkasıdır.

- **ML mühendisi olarak**, retrain edilen challenger'ın champion'dan gerçekten iyi olup olmadığını (şans eseri değil) McNemar/DeLong testleriyle görmek istiyorum.
- **Takım lideri olarak**, promotion kararını tek ekranda verip HITL onayına düşürmek istiyorum.
- **G2 policy motoru olarak**, retrain sonrası otomatik karşılaştırma çağırıp `recommendation` alanına göre HITL açmak istiyorum.
- **Kabul:** Aynı test seti üzerinde iki model → yan yana metrikler, p-değerleri, segment farkları, öneri (`promote|reject|wait`); Promote → HITL onay kaydı → onaylanınca champion işareti güncellenir.

## 2. Backend Tasarımı

### Agent
- Yeni dosya: `ml_agents/champion_challenger_agent.py` — sınıf `ChampionChallengerAgent`:
  - Her iki modeli aynı `dataset_artifact_id` üzerinde skorlar (deterministik, aynı satır sırası).
  - **McNemar** (`statsmodels.stats.contingency_tables.mcnemar`, exact=False, correction=True) — sınıflandırma doğruluk farkı.
  - **DeLong** — AUC farkı; `scipy` tabanlı yerel implementasyon (`_delong_roc_variance`, Sun & Xu 2014 hızlı algoritması) `ml_agents/stats/delong.py` altında.
  - Regresyon fallback: eşleştirilmiş hata farkına Wilcoxon signed-rank (`scipy.stats.wilcoxon`).
  - Karar kuralı: `promote` eğer birincil metrik farkı > `min_effect` VE p < `alpha`; `wait` eğer fark pozitif ama anlamsız; aksi halde `reject`.

### Node Tipi & I/O Sözleşmesi
- Node tipi: `model.compare` (executor: `workflow_node_executor_service.py`).

```json
{
  "input": {
    "champion_model_id": "uuid", "challenger_model_id": "uuid",
    "dataset_artifact_id": "uuid", "target_column": "churn",
    "primary_metric": "auc", "alpha": 0.05, "min_effect": 0.005,
    "segment_columns": ["region"]
  },
  "output": {
    "metrics": {"champion": {"auc": 0.842, "f1": 0.61}, "challenger": {"auc": 0.861, "f1": 0.64}},
    "tests": {
      "delong": {"auc_diff": 0.019, "ci95": [0.004, 0.034], "p_value": 0.012},
      "mcnemar": {"statistic": 8.41, "p_value": 0.004, "b": 130, "c": 82}
    },
    "segments": [{"segment": "region=EU", "auc_diff": 0.031, "p_value": 0.02}],
    "roc_curves": {"champion": [[0,0]], "challenger": [[0,0]]},
    "recommendation": "promote", "rationale": "AUC +0.019 (p=0.012), tüm segmentlerde tutarlı.",
    "comparison_id": "uuid"
  }
}
```

### API Endpoint'leri (`routes/modelops.py`)
- `POST /modelops/comparisons` — karşılaştırma başlat (workflow run olarak; async).
- `GET /modelops/comparisons/{id}` · `GET /modelops/models/{model_id}/comparisons` — sonuç/geçmiş.
- `POST /modelops/comparisons/{id}/decision` — body `{"decision": "promote|reject|wait", "note": "..."}`; `promote` → `hitl_service` üzerinden onay kaydı (`kind="model_promotion"`) açar, onaylanınca `ModelRegistryEntry.is_champion` güncellenir ve `record_deployment()` çağrılır.

### Veri Modeli / Migration
- Yeni tablo `model_comparisons`: `id, workspace_id, champion_model_id, challenger_model_id, dataset_artifact_id, result_json, recommendation, decision, hitl_request_id, created_at`.
- `model_registry_entries` tablosuna `is_champion BOOLEAN DEFAULT FALSE` kolonu. (Alembic migration `add_model_comparisons`.)

### Hata Durumları
- Modeller farklı problem tipi/target → 422 `INCOMPATIBLE_MODELS`.
- Test seti < 200 satır → sonuç `warnings[]`'e "düşük güç" notu; < 30 satır → 422.
- Bir modelin skorlaması hata verirse → run `failed`, kısmi sonuç saklanmaz.
- Bekleyen HITL varken ikinci `promote` kararı → 409 `DECISION_PENDING`.

## 3. UI Tasarımı

- Konum: K2 ModelOps Kontrol Merkezi'nde **Champion–Challenger** ekranı (`ModelOps.tsx` altında route `/modelops/comparisons/:id`).
- Bileşenler: yan yana `MetricCard` kolonları (anlamlı farkta ✚/− rozeti ve p-değeri tooltip'i); üst üste ROC/PR eğrileri (`ChartContainer`, renk-körü güvenli iki renk); segment farkları `DataTable` (anlamlı satırlar vurgulu); rationale metin kutusu.
- **Karar barı** (ekran altına sabit): üç buton — **Promote (HITL'e düşer)** birincil/yeşil, **Reddet** ikincil/kırmızı, **Bekle** nötr. Promote → confirm dialog → HITL isteği oluşur, barda `StatusBadge: "Onay bekliyor"` + HITLApproval ekranına link. Öneri butonu hafif vurgulanır ama otomatik seçilmez.
- Durumlar: loading = iki kolonlu skeleton; empty (karşılaştırma yok) = "Challenger seç ve karşılaştır" sihirbaz CTA'sı; error = başarısız run logu linkiyle banner. Karar verilmiş karşılaştırmalar salt-okunur (bar yerine karar timeline'ı).

## 4. Bağımlılıklar

- Spec: F1 (metrik hesaplayıcılar paylaşılır), G2 (bu node'u orkestrasyonda çağırır), G5 (stage promotion), K2/K3, HITL sistemi (`platform_api/hitl/`, `services/hitl_service.py`).
- Kütüphaneler: `statsmodels`, `scipy`, `scikit-learn`, `mlflow` (karşılaştırma run'ı loglanır).
- Kod: `services/modelops_service.py` (register/record_deployment), `workers/workflow_worker.py` (async çalıştırma).

## 5. Kapsam Dışı

- Canlı trafik karşılaştırması (shadow/canary → J11).
- 3+ model turnuvası (ilk sürüm ikili; çoklu için J10 leaderboard).
- Otomatik promotion (HITL onayı her zaman zorunlu — G2 dahi bunu atlayamaz).

## 6. Test & Definition of Done

- Birim: DeLong implementasyonu R `pROC::roc.test` referans değerlerine ±1e-3 doğruluk; McNemar b/c tablosu; karar kuralı sınır durumları (p=alpha, effect=min_effect); küçük örneklem uyarısı.
- Entegrasyon: karşılaştırma → promote → HITL onay → `is_champion` devri tek transaction zincirinde; reddedilen HITL'de registry değişmez.
- E2E: iki eğitilmiş model → UI'dan karşılaştır → karar barı → HITLApproval'da onayla → registry rozet değişimi (Playwright).
- DoD: `model.compare` node'u workflow'da çalışır, G2'nin çağırabileceği programatik API hazır, migration uygulanmış, PLATFORM_SPEC F2 ✍️.
