# J5 — Data Labeling

## 1. Amaç & Kullanıcı Hikâyeleri

**Amaç:** Denetimli öğrenme için etiketli veri üretimini platform içinde çözmek: etiketleme görevi tanımlama, LLM ile ön-etiketleme, aktif öğrenme ile "en değerli örnek önce" sıralaması ve insan doğrulaması (mevcut HITL altyapısı üzerinden).

**Kullanıcı hikâyeleri:**
- Bir DS olarak, dataset artifact'ından etiketleme görevi oluşturup sınıf listesini tanımlamak istiyorum ki ekibim örnekleri hızla etiketleyebilsin.
- Bir DS olarak, LLM'in ürettiği ön-etiketleri güven skoruyla görmek ve sadece düşük güvenli/anlaşmazlıklı örnekleri elle doğrulamak istiyorum.
- Bir etiketleyici olarak, klavye kısayollarıyla (1-9 sınıf, Enter onay, S atla) dakikada onlarca örnek geçebilmek istiyorum.
- Bir proje sahibi olarak, ilerleme yüzdesini, etiketleyiciler arası anlaşma (Cohen's kappa) metriğini ve sınıf dağılımını izlemek istiyorum.

**Kabul senaryoları:** Görev oluştur → LLM ön-etiket batch'i çalışır → düşük güvenli örnekler kuyruğun başına gelir → insan etiketler → çıktı yeni versiyonlu dataset artifact'ı olur ve lineage'a bağlanır (J12).

## 2. Backend Tasarımı

**Servis/Agent:**
- `apps/platform-api-app/platform_api/services/labeling_service.py` — görev CRUD, örnek kuyruğu, ilerleme/anlaşma metrikleri.
- `ai_data_science_team/agents/labeling_agent.py` — LLM ön-etiketleme (batch, sınıf tanımları + few-shot örneklerle prompt) ve aktif öğrenme skorlaması (belirsizlik: margin/entropy; model varsa onun tahmin olasılıklarıyla).
- HITL entegrasyonu: anlaşmazlık eşiği aşan örnekler `hitl/escalation_manager.py` üzerinden eskalasyon; bildirimler `notification_router.py`.

**Node tipi:** `data.label` — pipeline'da "etiketleme kapısı" olarak durur, görev tamamlanana kadar run `waiting_hitl` durumunda bekler.

```json
{
  "type": "data.label",
  "inputs": {"dataset": "artifact://ds_42"},
  "params": {
    "label_column": "sentiment",
    "classes": ["pozitif", "negatif", "nötr"],
    "prelabel": {"enabled": true, "confidence_threshold": 0.85},
    "active_learning": "entropy",
    "min_agreement": 0.8
  },
  "outputs": {"labeled_dataset": "artifact://ds_42_labeled_v1"}
}
```

**API endpoint'leri:**
- `POST /api/labeling/tasks` · `GET /api/labeling/tasks` · `GET /api/labeling/tasks/{id}`
- `GET /api/labeling/tasks/{id}/next?batch=20` — aktif öğrenme sıralı örnek batch'i
- `POST /api/labeling/tasks/{id}/labels` — `{example_id, label, duration_ms}` toplu kayıt
- `POST /api/labeling/tasks/{id}/prelabel` — LLM ön-etiket job'ı başlat
- `GET /api/labeling/tasks/{id}/stats` — ilerleme, kappa, sınıf dağılımı
- `POST /api/labeling/tasks/{id}/export` — etiketli dataset artifact'ı üret

**Veri modeli (migration):** `labeling_tasks` (id, dataset_artifact_id, classes JSON, config JSON, status, created_by), `labeling_examples` (task_id, row_index, prelabel, prelabel_confidence, al_score), `labels` (example_id, labeler_id, label, duration_ms, created_at). İndeks: `(task_id, al_score DESC)`.

**Hata durumları:** dataset artifact bulunamadı → 404; LLM ön-etiket job hatası → görev `prelabel_failed`, elle etiketleme devam eder; aynı örneğe eşzamanlı iki etiketleyici → optimistic lock, ikinci yazım anlaşma metriğine girer; export sırasında etiketsiz satırlar → seçenek: dışarıda bırak / `null` bırak.

## 3. UI Tasarımı

**Bileşenler:**
- `LabelingTasks.tsx` — görev listesi (DataTable: ad, dataset, ilerleme çubuğu, kappa StatusBadge).
- `LabelingWorkbench.tsx` — tam ekran etiketleme: solda örnek içeriği (metin/satır kartı), sağda sınıf butonları (kısayol rozetli), üstte ilerleme + tahmini kalan süre, altta ön-etiket önerisi (güven yüzdesiyle, Tab ile kabul).
- `LabelingStats.tsx` — sınıf dağılım bar grafiği (ECharts), anlaşmazlık listesi, etiketleyici hız tablosu.

**Akış:** Görev oluşturma sihirbazı (dataset seç → kolon/sınıflar → ön-etiket ayarı) → "Ön-etiketle" (progress stepper) → Workbench → Stats → Export.

**Durumlar:** loading: skeleton kart; empty: "Henüz etiketleme görevi yok — dataset'ten oluştur" CTA; error: ön-etiket hatasında banner + "elle devam et".

**Entegrasyon:** ArtifactCard'a "Etiketleme görevi başlat" aksiyonu; anlaşmazlık eskalasyonları mevcut `HITLApproval.tsx` kuyruğunda görünür; TanStack Query key'leri `['labeling', taskId]`.

## 4. Bağımlılıklar

- HITL altyapısı (`hitl/escalation_manager.py`, `services/hitl_service.py`), artifact servisi (`services/artifact_service.py`).
- J12 (lineage: etiketli dataset zinciri), K3 (DataTable/StatusBadge), opsiyonel J3 (görev bitince workflow tetikle).
- Kütüphaneler: scikit-learn (kappa), mevcut LLM client.

## 5. Kapsam Dışı

- Görüntü/ses/video etiketleme (yalnız tablo + metin), bounding box/NER span araçları, dış etiketleme servisi entegrasyonu (Label Studio vb.), crowd yönetimi/ödeme, çok aşamalı review hiyerarşisi.

## 6. Test & Definition of Done

- Birim: aktif öğrenme sıralaması (entropy skorunun doğru sıraladığı), kappa hesabı, optimistic lock çakışması.
- E2E: görev oluştur → ön-etiketle → 10 örnek etiketle (kısayollarla) → export → yeni artifact lineage'da görünür.
- DoD: `data.label` node'u pipeline'ı bekletip devam ettirebiliyor; kısayollar çalışıyor; kappa ve ilerleme canlı güncelleniyor; export edilen dataset eğitim node'una girdi olabiliyor.
