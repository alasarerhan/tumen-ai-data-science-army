# E3 — Deep Learning (Tabular / Time Series)

> Öncelik: **P1** · Faz: 2 · E1 `engine=dl` dispatch'inin implementasyonu.

## 1. Amaç & Kullanıcı Hikâyeleri

PyTorch tabanlı MLP/TabNet (tabular) ve LSTM/TFT (time series) modellerini E1 `model.train` sözleşmesi altında sunmak; early stopping, epoch bazlı canlı eğitim eğrisi ve GPU/MPS farkındalığı ile.

- **US-1:** Data scientist olarak, tabular veride `engine=dl, architecture=mlp` seçip gradient boosting'e alternatif bir baseline eğitmek istiyorum.
- **US-2:** Forecasting probleminde LSTM seçip lookback penceresi ve horizon tanımlamak istiyorum.
- **US-3:** Eğitim sürerken epoch başına loss/metric eğrisini UI'da canlı görmek ve erken durdurmanın ne zaman tetiklendiğini bilmek istiyorum.
- **Kabul:** MLP classification eğitimi early stopping ile tamamlanır, E1 ortak çıktı şemasını döner, eğitim eğrisi artifact olarak kaydedilir; CUDA/MPS varsa otomatik kullanılır, yoksa CPU'ya düşer ve loglanır.

## 2. Backend Tasarımı

### Agent sınıfı
- **Yeni dosya:** `ai_data_science_team/ml_agents/deep_learning_agent.py` → `DeepLearningAgent`
- Mimariler: `mlp` (kendi `nn.Module`), `tabnet` (`pytorch-tabnet`), `lstm`, `tft` (`pytorch-forecasting`, opsiyonel extra). Ortak `TorchTrainer`: DataLoader, AdamW, `ReduceLROnPlateau`, early stopping (patience), en iyi checkpoint'i saklama.
- Device seçimi: `cuda` → `mps` → `cpu` sırası; `torch.cuda.is_available()` / `torch.backends.mps.is_available()`.
- Preprocessing deterministik: sayısal `StandardScaler`, kategorik embedding (kardinaliteye göre boyut); scaler + encoder'lar model bundle'ına dahil edilir (`model.pt` + `preprocess.joblib` + `meta.json` tek dizin).
- MLflow: `mlflow.pytorch.log_model` + epoch metrikleri `mlflow.log_metric(step=epoch)`.
- Progress callback: her epoch sonunda `ctx.report_progress({"epoch": e, "train_loss": ..., "val_loss": ..., "val_metric": ...})` → worker üzerinden run loguna/DB'ye yazılır (UI canlı eğri bunu okur).

### Node tipi + I/O sözleşmesi
`model.train` + `engine: "dl"` (E1 dispatch). `engine_params`:

```json
{
  "type": "model.train",
  "config": {
    "engine": "dl",
    "task_type": "classification",
    "target_column": "churn",
    "engine_params": {
      "architecture": "mlp",
      "hidden_layers": [256, 128, 64], "dropout": 0.2,
      "epochs": 100, "batch_size": 512, "lr": 0.001,
      "early_stopping": {"patience": 10, "min_delta": 0.001, "monitor": "val_loss"},
      "device": "auto",
      "ts": {"lookback": 28, "horizon": 7, "group_column": null, "time_column": "date"}
    }
  }
}
```

Çıktı = E1 ortak şeması **+**:

```json
{
  "dl_result": {
    "architecture": "mlp", "device_used": "mps",
    "epochs_run": 43, "stopped_early": true, "best_epoch": 33,
    "history": [{"epoch": 1, "train_loss": 0.61, "val_loss": 0.58, "val_metric": 0.71}],
    "model_bundle_path": "artifacts/models/run_123/dl_bundle/",
    "n_parameters": 84353
  }
}
```

### API endpoint'leri
- `GET /api/ml/dl/capabilities` — `{torch_version, cuda: bool, mps: bool, architectures: [...]}`; UI form ve engine seçici disabled durumları için.
- `GET /api/workflows/runs/{run_id}/nodes/{node_id}/training-progress` — history dizisini döner (polling, canlı eğri).
- Engine listesi E1 `GET /api/ml/engines` içinde `dl` olarak görünür.

### Veri modeli
- `workflow_node_executions` tablosuna `progress` JSON kolonu (migration: `add_node_progress_column`) — epoch history burada güncellenir; final çıktı yine `outputs`'a.

### Hata durumları
- `torch` kurulu değil → `EngineNotInstalledError` (E1 sınıfı), kurulum komutuyla.
- OOM (CUDA/MPS) → batch_size yarıya indirilerek 2 kez retry, sonra CPU fallback; her adım loglanır.
- TS konfig eksikliği (`task_type=forecasting` ama `ts.time_column` yok) → ön-validasyon hatası.
- NaN loss (patlayan gradient) → eğitim durur, "lr'yi düşürün" önerili hata; son sağlıklı checkpoint varsa onunla kısmi sonuç.

## 3. UI Tasarımı

- **Config formu (Designer sağ drawer, engine=dl seçince):** mimari kartları (MLP/TabNet/LSTM/TFT — desteklenmeyenler task_type'a göre gizli), katman/dropout/epoch/batch/lr alanları, early stopping alt formu, device rozeti ("GPU: MPS bulundu").
- **Canlı eğitim eğrisi:** run detayında ChartContainer — train/val loss iki çizgi + val metric ikinci eksen; 2 sn polling; erken durdurma tetiklenince dikey işaret çizgisi + "epoch 33'te en iyi, 43'te durdu" rozeti.
- **Durumlar:** loading = epoch progress bar (`epochs_run/epochs`) + tahmini kalan süre; empty = "eğitim başlamadı"; error = hata sınıfına göre mesaj (OOM → "batch size küçültüldü/CPU'ya düşüldü" timeline'ı).
- **Entegrasyon:** metrik kartı ve leaderboard E1 bileşenleriyle aynı; I3'te engine rozeti `dl`; E2 HPO açıksa search_space önerisi dl parametrelerini (lr, dropout, hidden size) kapsar.

## 4. Bağımlılıklar

- **Spec'ler:** **E1 (zorunlu — dispatch + ortak şema)**, E2 (dl arama uzayı), G4 (bundle'dan predict), I3, K1/K3.
- **Kütüphaneler:** `torch>=2.2`, `pytorch-tabnet` (opsiyonel), `pytorch-forecasting` + `lightning` (opsiyonel, TFT), `mlflow`, `joblib`.
- **Kod entegrasyon noktaları:**
  - `ai_data_science_team/ml_agents/deep_learning_agent.py` (yeni)
  - `apps/platform-api-app/platform_api/services/workflow_node_executor_service.py` (E1 dispatch içinden çağrı + progress callback)
  - `apps/platform-api-app/platform_api/workers/workflow_worker.py` (progress persist)
  - `frontend/src/app/screens/WorkflowDesigner.tsx` + run detay ekranı (canlı eğri)

## 5. Kapsam Dışı

- NLP/CV mimarileri (E4/E5), dağıtık/multi-GPU eğitim, ONNX/TorchScript export (G3'e), transfer learning, otomatik mimari seçimi (NAS), TabNet/TFT'nin attention görselleştirmesi.

## 6. Test & Definition of Done

- **Birim:** TorchTrainer early stopping mantığı (patience/min_delta), device fallback zinciri (mock), preprocessing round-trip (fit→save→load→predict aynı sonuç), NaN loss yakalama.
- **Entegrasyon:** küçük sentetik veriyle MLP (5 epoch) uçtan uca node çalıştırma → E1 şema validasyonu + `dl_result.history` dolu; forecasting LSTM'in `ts` penceresi doğru şekillendiriyor (shape testleri); MLflow'da step'li metrikler.
- **E2E:** UI'dan dl seçimi → eğitim → canlı eğri güncellenir → erken durdurma rozeti görünür.
- **DoD:** CPU-only ortamda tüm testler geçer (GPU testleri işaretli/atlanabilir); bundle G4 predict ile tüketilebilir; durum tablosunda E3 ✍️.
