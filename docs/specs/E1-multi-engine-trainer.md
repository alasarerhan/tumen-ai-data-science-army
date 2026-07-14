# E1 — Sklearn/XGBoost/LightGBM Trainer (Multi-Engine Trainer)

> Öncelik: **P0** · Faz: 1 · H2O monopolünü kırar; `model.train` node'una `engine` parametresi ekler. E2 (HPO) ve E3 (DL) bu sözleşmenin üstüne kurulur.

## 1. Amaç & Kullanıcı Hikâyeleri

Bugün `model.train` node'u yalnızca `H2OMLAgent`'a bağlıdır (`workflow_node_executor_service.py` → `_execute_model_train`). Bu spec, tek bir `engine` parametresiyle H2O, sklearn, XGBoost, LightGBM ve (E3 ile) deep learning motorlarını aynı node sözleşmesi altında toplar.

- **US-1:** Data scientist olarak, train node'unda `engine=xgboost` seçip H2O kurulumu gerektirmeden gradient boosting modeli eğitmek istiyorum.
- **US-2:** ML engineer olarak, aynı veri üzerinde farklı engine'lerle eğitilen modellerin MLflow'da aynı şemayla loglanmasını istiyorum ki F2 Champion–Challenger karşılaştırabilsin.
- **US-3:** Analist olarak, problem tipini (classification/regression) seçtiğimde engine'in bana uygun model adaylarını ve CV stratejisini önermesini istiyorum.
- **Kabul:** `engine=sklearn` ile logistic regression + random forest adayları CV ile eğitilir, en iyisi MLflow'a loglanır, `model_path` + `metrics` artifact'ı üretilir; H2O davranışı (`engine=h2o`, varsayılan) birebir korunur.

## 2. Backend Tasarımı

### Agent sınıfı
- **Yeni dosya:** `ai_data_science_team/ml_agents/multi_engine_ml_agent.py` → `MultiEngineMLAgent`
- Mevcut `H2OMLAgent` arayüz kalıbını izler: `invoke_agent(data_raw, user_instructions, target_variable, ...)`, `get_leaderboard()`, `get_best_model_id()`, `get_model_path()`, `get_recommended_ml_steps()`, `get_log_summary()`.
- İç mimari: `EngineAdapter` protokolü (`fit(X, y, params) -> TrainResult`); adapterlar: `SklearnAdapter`, `XGBoostAdapter`, `LightGBMAdapter`. LLM yalnızca aday model listesi + preprocessing önerisi üretir; eğitim kodu deterministik sklearn `Pipeline`'dır (codegen değil).
- Çıktı her zaman pickle'lanabilir bir sklearn `Pipeline` (preprocess + model) olarak `joblib` ile kaydedilir ve `mlflow.sklearn.log_model` ile loglanır.

### Node tipi + I/O sözleşmesi
`model.train` node'u genişletilir (yeni node tipi YOK). Katalog girdisi (`workflow_node_catalog_service.py`) `config` listesine eklenir:

```json
{
  "type": "model.train",
  "config": {
    "task_type": "classification",
    "target_column": "churn",
    "engine": "xgboost",
    "engine_params": {
      "n_estimators": 500, "max_depth": 6, "learning_rate": 0.05,
      "early_stopping_rounds": 50, "class_weight": null
    },
    "cv": {"strategy": "stratified_kfold", "n_splits": 5, "shuffle": true, "random_state": 42},
    "candidates": ["xgboost"],
    "metric": "roc_auc",
    "test_size": 0.2,
    "mlflow": {"experiment_name": "wf_{workflow_id}", "register_as": null}
  }
}
```

Node çıktısı (tüm engine'ler için ortak — G4 `model.predict` bu şemaya bağımlıdır):

```json
{
  "outputs": {
    "model_path": "artifacts/models/run_123/model.joblib",
    "engine": "xgboost",
    "best_model_id": "xgboost__0",
    "leaderboard": [{"model_id": "xgboost__0", "roc_auc": 0.91, "f1": 0.78, "fit_time_s": 12.4}],
    "metrics": {"roc_auc": 0.91, "f1": 0.78, "precision": 0.8, "recall": 0.76},
    "feature_importance": [{"feature": "tenure", "importance": 0.31}],
    "mlflow_run_id": "abcd1234",
    "input_schema": {"columns": [{"name": "tenure", "dtype": "float64"}], "target": "churn"}
  }
}
```

- `engine` enum: `h2o | sklearn | xgboost | lightgbm | dl`. Varsayılan `h2o` (geriye uyumluluk). `dl` seçilirse dispatch E3'ün `DeepLearningAgent`'ına gider.
- Executor değişikliği: `_execute_model_train` içinde `engine = config.get("engine", "h2o")` dallanması; `h2o` → mevcut yol aynen, diğerleri → `MultiEngineMLAgent`.

### API endpoint'leri
- `GET /api/workflows/node-catalog` — mevcut endpoint; genişletilmiş `model.train` config şemasını döner.
- `GET /api/ml/engines` — yeni; her engine için `{name, available, version, supported_tasks, default_params}` (import denemesiyle `available` tespiti).
- `POST /api/ml/engines/{engine}/suggest-params` — yeni; dataset özeti + task_type alır, LLM destekli varsayılan `engine_params` önerir (UI form ön-doldurma).

### Veri modeli
- Migration gerekmez; node config JSON kolonunda saklanır. `workflow_node_executions.outputs`'a yukarıdaki şema yazılır.

### Hata durumları
- `EngineNotInstalledError` (ör. lightgbm import hatası) → node `failed`, mesaj: hangi paket, kurulum komutu; UI'da eyleme dönük hata.
- Hedef kolon yok / tek sınıf / tüm-NaN hedef → eğitim öncesi validasyon hatası (`ValueError`, satır örnekleriyle).
- `task_type` ↔ hedef dtype uyumsuzluğu (regression + kategorik hedef) → uyarı + otomatik öneri.
- CV sırasında tek fold başarısızsa fold atlanır ve loglanır; tümü başarısızsa node fail.

## 3. UI Tasarımı

- **Engine seçici:** `WorkflowDesigner.tsx` node config panelinde (sağ drawer) `model.train` seçiliyken segmented control: H2O · Sklearn · XGBoost · LightGBM · Deep Learning. Kurulu olmayan engine disabled + tooltip ("lightgbm kurulu değil").
- **Engine'e özel parametre formu:** seçime göre dinamik form (`engine_params`); "Önerilen değerleri getir" butonu → `suggest-params` endpoint'i, loading spinner ile.
- **CV bölümü:** strateji dropdown + fold sayısı; `task_type=forecasting` iken `TimeSeriesSplit` zorunlu.
- **Sonuç metrik kartı:** run detayında MetricCard grid'i (K3 bileşeni) — metrikler, engine rozeti, leaderboard tablosu, feature importance bar chart.
- **Durumlar:** loading = eğitim progress stepper'ı (veri hazırlama → CV → final fit → MLflow log); empty = "henüz çalıştırılmadı" CTA'sı; error = hata sınıfına göre mesaj + "parametreleri düzelt" aksiyonu.
- **Entegrasyon:** I3 Experiments leaderboard'u `engine` rozetini bu çıktıdan okur; F2 karşılaştırma ekranı `metrics` şemasını kullanır.

## 4. Bağımlılıklar
- **Spec'ler:** G4 (model.predict bu `model_path`+`input_schema`'yı tüketir), E2 (HPO `engine_params` uzayını optimize eder), E3 (`engine=dl` dispatch'i), F2, I3, /.
- **Kütüphaneler:** `scikit-learn`, `xgboost`, `lightgbm`, `joblib`, `mlflow` (mevcut), `shap` (feature importance fallback — opsiyonel).
- **Kod entegrasyon noktaları:**
  - `apps/platform-api-app/platform_api/services/workflow_node_executor_service.py::_execute_model_train`
  - `apps/platform-api-app/platform_api/services/workflow_node_catalog_service.py` (`model.train` config şeması)
  - `ai_data_science_team/ml_agents/multi_engine_ml_agent.py` (yeni)
  - `frontend/src/app/screens/WorkflowDesigner.tsx` (node config paneli)
## 5. Kapsam Dışı

- Optuna araması (E2), deep learning implementasyonu (E3 — burada yalnızca dispatch), model serving (G3), ensemble/stacking (J10), AutoML tarzı otomatik engine seçimi, GPU eğitim.

## 6. Test & Definition of Done

- **Birim:** her adapter için sentetik veri ile fit/predict/serialize round-trip; `engine=h2o` regresyon testi (mevcut çıktı şeması değişmedi); engine yokken `EngineNotInstalledError`; hedef validasyon hataları.
- **Entegrasyon:** `model.train(engine=xgboost)` → `model.evaluate` zinciri worker üzerinden uçtan uca; MLflow run'ında params+metrics+model artifact doğrulaması; çıktı JSON şemasının pydantic ile validasyonu.
- **E2E (frontend):** Designer'da engine seçimi → parametre formu render → run → metrik kartı görünür.
- **DoD:** 4 engine (h2o dahil) aynı workflow'da değiştirilerek çalışır; ortak çıktı şeması dokümante ve validate; PLATFORM_SPEC durum tablosunda E1 ✍️; testler CI'da yeşil.
