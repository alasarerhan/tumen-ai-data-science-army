# E5 — Computer Vision (Transfer Learning)

## 1. Amaç & Kullanıcı Hikâyeleri

Görsel sınıflandırma problemlerini (ürün kategorisi, kalite kontrol/defekt, belge tipi) transfer learning ile kod yazmadan çözmek.

- **DS olarak**, klasörlenmiş görüntü dataset'imi yükleyip timm backbone'u ile fine-tune edilmiş bir sınıflandırıcı eğitmek istiyorum ki günler süren CV boilerplate'ini atlayayım.
- **ML engineer olarak**, dataset doğrulama raporu (bozuk dosya, sınıf dengesizliği, boyut dağılımı) görmek istiyorum ki eğitim öncesi veri sorunlarını yakalayayım.
- **İş kullanıcısı olarak**, örnek görüntüler üzerinde tahmin overlay'ini görmek istiyorum ki modele güvenip güvenemeyeceğime karar vereyim.

Kabul senaryosu: `ImageFolder` yapısında zip yüklenir → doğrulama raporu → `resnet50`/`efficientnet_b0` fine-tune → accuracy/F1 + confusion matrix → örnek grid'de tahminler.

## 2. Backend Tasarımı

### Agent
- **Sınıf:** `ComputerVisionAgent` — yeni dosya `ai_data_science_team/ml_agents/computer_vision_agent.py`
- `ClusteringAgent` ile aynı desen: `BaseAgent` + `prepare_messages → react_agent → post_process`.
- Tool'lar (`ai_data_science_team/tools/vision.py`, yeni): `validate_image_dataset`, `suggest_augmentations`, `train_image_classifier` (timm + torchvision transforms), `evaluate_image_classifier`, `predict_images`.

### Node tipi: `vision.train` (katalog: `platform_api/services/workflow_node_catalog_service.py`)
```json
{
  "type": "vision.train",
  "label": "Vision Trainer",
  "category": "Modeling",
  "inputs": [{"name": "image_dataset", "artifact_type": "image_dataset", "required": true}],
  "outputs": [
    {"name": "model", "artifact_type": "model", "required": true},
    {"name": "metrics", "artifact_type": "metrics", "required": true},
    {"name": "sample_predictions", "artifact_type": "vision_preview", "required": true}
  ],
  "ui": {"icon": "image", "color": "rose", "config": [
    {"key": "backbone", "type": "select", "options": ["resnet50", "efficientnet_b0", "vit_base_patch16_224"], "required": true},
    {"key": "epochs", "type": "number", "required": false},
    {"key": "augmentation_level", "type": "select", "options": ["none", "light", "strong"], "required": false}
  ]},
  "timeout_seconds": 7200,
  "retry_policy": {"max_attempts": 1, "backoff_seconds": 60},
  "resources": {"class": "gpu_optional"}
}
```
Executor: `_execute_vision_train` → `platform_api/services/workflow_node_executor_service.py` içindeki `get_default_node_executors()` sözlüğüne eklenir.

### API endpoint'leri
- `POST /api/vision/datasets` — zip upload → doğrulama job'u başlatır.
- `GET /api/vision/datasets/{id}/validation` — doğrulama raporu (bozuk dosya listesi, sınıf dağılımı).
- `POST /api/vision/models/{model_id}/predict` — çoklu görüntü → tahmin + olasılıklar.
- `GET /api/vision/models/{model_id}/samples` — örnek grid verisi (görüntü URI + tahmin + gerçek etiket).

### Veri modeli
- Yeni artifact tipleri: `image_dataset`, `vision_preview`. Alembic migration: `vision_datasets` tablosu (`id, name, storage_uri, class_map JSON, validation_report JSON, created_at`).

### Hata durumları
- Bozuk/desteklenmeyen dosya oranı > %5 → node `failed`, raporda dosya listesi.
- Sınıf başına < 20 örnek → uyarı (warning artifact), eğitim devam eder.
- GPU yoksa → CPU fallback + log uyarısı; `vit_*` backbone'ları CPU'da reddedilir (açıklayıcı hata).
- OOM → batch size otomatik yarıya indirilerek 1 retry.

## 3. UI Tasarımı

### Bileşenler
- `VisionDatasetUpload` — zip drop alanı + klasör yapısı şeması gösterimi.
- `DatasetValidationCard` — sınıf dağılım bar chart'ı (ECharts), bozuk dosya listesi, boyut histogramı.
- `SamplePredictionGrid` — 4xN görüntü grid'i; her hücrede tahmin etiketi + güven rozeti; yanlış tahminler kırmızı çerçeve; tıkla → büyüt + top-5 olasılık barı.
- `ConfusionMatrixHeatmap` — ECharts heatmap.

### Akış
1. Designer paletinden `vision.train` sürüklenir → config panelinde dataset seçici + backbone/epoch formu.
2. Run sırasında epoch bazlı loss/accuracy canlı grafiği (K3 streaming standardı).
3. Run detayında sekmeler: Doğrulama · Metrikler · Örnek Tahminler.

### Durumlar
- **Loading:** grid'de skeleton kutucuklar; eğitimde epoch progress bar.
- **Empty:** "Henüz görüntü dataset'i yok — zip yükleyin" CTA'sı.
- **Error:** doğrulama hatasında bozuk dosyaların indirilebilir listesi + "sorunluları hariç tutarak devam et" aksiyonu.

### Entegrasyon
- `frontend/src/app/screens/WorkflowDesigner.tsx` paletine yeni node; ModelOps registry'de `vision` engine rozeti; model detayına `SamplePredictionGrid` sekmesi.

## 4. Bağımlılıklar

- **Spec:** E1 (engine seçici deseni), G4 (predict altyapısı), K3 (UI standartları), I3 (metrik loglama/MLflow).
- **Kütüphaneler:** `timm`, `torch`, `torchvision`, `Pillow`; opsiyonel `albumentations`.
- **Kod:** `workflow_node_catalog_service.py`, `workflow_node_executor_service.py`, `BaseAgent` şablonu, artifact yazma helper'ları (`_write_json_artifact` vb.).

## 5. Kapsam Dışı

- Object detection, segmentation, OCR (yalnız sınıflandırma).
- Video ve çok-etiketli (multi-label) görüntüler.
- Dataset etiketleme UI'ı (J5'in işi), dağıtık/çoklu-GPU eğitim, model distilasyonu.

## 6. Test & Definition of Done

- **Birim:** `validate_image_dataset` bozuk PNG'yi işaretler; `train_image_classifier` 2 sınıflı mini dataset'te (CPU, 1 epoch) accuracy > 0.5 döner; class_map artifact'ı doğru üretilir.
- **E2E:** zip upload → doğrulama → `vision.train` node'lu workflow run → metrics + sample_predictions artifact'ları oluşur; UI grid'i render eder.
- **Hata testi:** GPU'suz ortamda ViT seçimi anlaşılır hata döner; %10 bozuk dosyalı dataset fail eder.
- **DoD:** katalogda node görünür, Designer'dan sürüklenip çalıştırılabilir, model MLflow'a loglanır, örnek grid UI'da yanlış tahminleri işaretler, tüm testler CI'da yeşil.
