# E2 — Hyperparameter Optimization (Optuna HPO)

> Öncelik: **P0** · Faz: 1 · E1 multi-engine sözleşmesinin üstüne kurulur.

## 1. Amaç & Kullanıcı Hikâyeleri

E1 ile gelen engine'lerin (`sklearn|xgboost|lightgbm|dl`) hiperparametrelerini Optuna ile otomatik optimize etmek: arama uzayı önerisi, budget (trial sayısı/süre), pruning ve her trial'ın MLflow'a loglanması.

- **US-1:** Data scientist olarak, train node'una "HPO aç" deyip trial bütçesi vererek en iyi konfigürasyonun otomatik bulunmasını istiyorum.
- **US-2:** Arama uzayını elle yazmak istemiyorum; engine + dataset boyutuna göre makul bir uzayın önerilmesini istiyorum, gerekirse düzenlerim.
- **US-3:** I3 Experiments ekranında trial'ları paralel-koordinat grafiğiyle inceleyip "en iyi konfigürasyonla node oluştur" demek istiyorum.
- **Kabul:** `engine=lightgbm`, 50 trial, MedianPruner ile çalışan bir study; en iyi trial parametreleri final modele uygulanır ve E1 çıktı şemasıyla döner.

## 2. Backend Tasarımı

### Agent sınıfı
- **Yeni dosya:** `ai_data_science_team/ml_agents/hpo_agent.py` → `HPOAgent`
- Sorumluluklar: (1) LLM ile arama uzayı önerisi (`suggest_search_space(engine, task_type, data_profile)` → JSON uzay), (2) Optuna study yürütme (`optuna.create_study(direction=..., pruner=MedianPruner())`), (3) objective içinde E1 `EngineAdapter.fit` + CV skoru, (4) `mlflow` nested run olarak her trial'ı loglama (`mlflow.start_run(nested=True)`), (5) en iyi parametrelerle final fit'i `MultiEngineMLAgent`'a devretme.
- Study storage: `optuna.storages.RDBStorage` — platform veritabanı URL'i (SQLite/Postgres), study adı `wf_{workflow_id}_node_{node_id}`.

### Node tipi + I/O sözleşmesi
Ayrı node yerine `model.train` config'ine `hpo` bloğu eklenir (E1 sözleşmesinin uzantısı):

```json
{
  "type": "model.train",
  "config": {
    "engine": "lightgbm",
    "task_type": "classification",
    "target_column": "churn",
    "metric": "roc_auc",
    "hpo": {
      "enabled": true,
      "n_trials": 50,
      "timeout_s": 1800,
      "sampler": "tpe",
      "pruner": "median",
      "search_space": {
        "num_leaves": {"type": "int", "low": 16, "high": 256, "log": true},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.3, "log": true},
        "feature_fraction": {"type": "float", "low": 0.5, "high": 1.0}
      }
    }
  }
}
```

Çıktı = E1 çıktı şeması **+**:

```json
{
  "hpo_result": {
    "study_name": "wf_12_node_train1",
    "best_trial": {"number": 37, "value": 0.923, "params": {"num_leaves": 84, "learning_rate": 0.041}},
    "n_trials_completed": 50, "n_trials_pruned": 18,
    "optimization_history": [{"trial": 0, "value": 0.88}, {"trial": 1, "value": 0.9}],
    "param_importances": {"learning_rate": 0.52, "num_leaves": 0.3}
  }
}
```

### API endpoint'leri
- `POST /api/ml/hpo/suggest-space` — `{engine, task_type, data_profile}` → önerilen `search_space` JSON'u (LLM + engine başına kural tabanlı fallback).
- `GET /api/ml/hpo/studies/{study_name}` — trial listesi, optimizasyon geçmişi, param importances (I3 HPO görünümü besler; koşarken polling ile canlı).
- `GET /api/ml/hpo/studies/{study_name}/trials?status=running` — canlı izleme.
- `POST /api/ml/hpo/studies/{study_name}/stop` — study'yi graceful durdur (o ana kadarki best ile devam).

### Veri modeli
- Optuna kendi tablolarını RDBStorage'da yaratır (migration Optuna'ya ait). Ek olarak `workflow_node_executions.outputs.hpo_result` yazılır. `param_importances` `optuna.importance.get_param_importances` ile hesaplanır.

### Hata durumları
- Geçersiz search_space (low>high, bilinmeyen param) → çalıştırma öncesi pydantic validasyonu, alan bazlı hata mesajı.
- Tüm trial'lar fail → node fail + ilk 3 trial exception özeti.
- `timeout_s` aşımı → study durur, tamamlanan trial'larla en iyi konfig kullanılır, `logs`'a uyarı.
- Worker restart'ı: study RDB'de olduğundan `load_if_exists=True` ile kaldığı yerden devam.

## 3. UI Tasarımı

- **Train node config panelinde "HPO" akordeonu:** enable toggle → n_trials/timeout input'ları, sampler/pruner dropdown, "Uzay öner" butonu (suggest-space, loading skeleton) → düzenlenebilir search_space tablosu (param, tip, min, max, log ölçek).
- **I3 Experiments içinde HPO görünümü:** study seçici → (1) optimizasyon eğrisi (trial vs best-so-far, ChartContainer), (2) paralel-koordinat grafiği (parametreler + metrik ekseni, brush ile filtre), (3) param importance bar chart, (4) trial tablosu (durum rozeti: complete/pruned/failed).
- **Aksiyonlar:** "En iyi konfigürasyonla node oluştur" → best params'ı `engine_params` olarak yazılmış yeni `model.train` node'unu Designer'a ekler; koşan study'de "Durdur" (confirm dialog).
- **Durumlar:** loading = canlı trial sayacı + progress bar (n_trials'a göre); empty = "Bu workflow'da HPO study yok" CTA; error = fail nedeni + "uzayı düzenle" linki.

## 4. Bağımlılıklar
- **Spec'ler:** **E1 (zorunlu ön koşul — EngineAdapter ve çıktı şeması), E3 (`engine=dl` uzayları), I3 (görselleştirme yüzeyi), .**
- **Kütüphaneler:** `optuna>=3.6`, `mlflow` (mevcut), `plotly` benzeri grafikler frontend'de (recharts/visx), E1 engine paketleri.
- **Kod entegrasyon noktaları:**
  - `ai_data_science_team/ml_agents/hpo_agent.py` (yeni), `multi_engine_ml_agent.py` (final fit devri)
  - `apps/platform-api-app/platform_api/services/workflow_node_executor_service.py::_execute_model_train` (`config.hpo.enabled` dallanması)
  - `apps/platform-api-app/platform_api/workers/workflow_worker.py` (uzun koşan study için heartbeat/progress raporu)
  - `frontend/src/app/screens/` Experiments ekranı + `WorkflowDesigner.tsx` config paneli
## 5. Kapsam Dışı

- Dağıtık/paralel trial yürütme (tek worker, sıralı), multi-objective optimizasyon, NAS, H2O engine'i için HPO (H2O kendi AutoML'ini kullanır), hiperband dışı gelişmiş pruner konfigürasyonları.

## 6. Test & Definition of Done

- **Birim:** search_space validasyonu (geçerli/geçersiz örnekler); suggest-space fallback'inin her engine için çalışması; objective'in pruning sinyalini (`trial.report` + `should_prune`) doğru kullanması; timeout davranışı.
- **Entegrasyon:** 5-trial mini study uçtan uca (sentetik veri, lightgbm) → best params final modele uygulanır, MLflow'da 1 parent + 5 nested run; stop endpoint'i koşan study'yi durdurur.
- **E2E:** UI'dan HPO aç → çalıştır → I3'te eğri ve tablo görünür → "en iyi konfigürasyonla node oluştur" yeni node üretir.
- **DoD:** E1 şemasıyla tam uyumlu çıktı; study restart-güvenli; dokümante search_space DSL'i; testler yeşil; durum tablosunda E2 ✍️.
