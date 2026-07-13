# A6 — Uplift Modeling

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** Marketing analisti, CRM kampanyası yöneticisi; "kime teklif gönderirsem gerçekten etkileşim artar?" sorusunu cevaplayan kişi.

**Neden:** Ortalama tedavi etkisi (ATE) herkese teklif göndermenin iyi bir fikir olduğunu söyler ama kimlerin gerçekten ikna olacağını söylemez. Uplift modeling "ilaca yanıt veren hasta" mantığıyla — sadece tedaviden pozitif etkilenen bireyleri hedefler.

Kabul senaryoları:
1. Analist müşteri özellikleri + tedavi/kontrol etiketi + dönüşüm sonucu olan dataset verir; ajan uplift skorlarını (T-learner, X-learner, uplift tree/R-learner) tahmin eder.
2. Çıktıda "persuadable" (sadece tedavi grubuna gidince dönüşen), "sure thing" (zaten dönüşecek), "lost cause" (etkilenmez), "sleeping dog" (tedavi zarar verir) segmentleri ayrı kartlarla gösterilir.
3. Uplift eğrisi: en yüksek uplift'ten başlayarak sıralı seçildiğinde kümülatif etki grafiği (Qini curve).
4. ROI optimizasyonu: kampanya bütçesi ve tedavi maliyeti verildiğinde en kârlı eşik (threshold) otomatik hesaplanır.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/uplift_agent.py` — sklearn + `scikit-uplift`/`causalml` araçları; deterministic çekirdek `ai_data_science_team/tools/uplift.py`.

**Node tipi:** `experiment.uplift`:
```json
{
  "type": "experiment.uplift",
  "config": {
    "treatment_col": "exposed",
    "outcome_col": "converted",
    "features": ["age","tenure","recency","freq"],
    "method": "t_learner|x_learner|r_learner|catboost_uplift",
    "treatment_cost": 5.0
  }
}
```

**API endpoint'leri** (`platform_api/routes/uplift.py`):
- `POST /uplift/train` — body config + dataset_ref → `{model_ref, qini_score, uplift_at_k}`.
- `POST /uplift/score` — model_ref + dataset → kolon bazlı uplift tahmini + segment atamaları.
- `GET /uplift/segments/{run_id}` — 4 segment kartı (persuadable/sure_thing/lost_cause/sleeping_dog) + büyüklükleri.

**Veri modeli:** `uplift_models` (`id, dataset_id, method, model_artifact_ref, qini_score, created_at`) + `uplift_segment_assignments` (müşteri_id, segment, score).

**Hata durumları:** treatment/imbalance > 0.95 (uyarı: dengeleme öner) · tedavi grubu < 1000 gözlem (uyarı) · Qini < 0 (model kötü, yeniden eğit öner).

## 3. UI Tasarımı

**Konum:** `Experiments.tsx` ekranının "Uplift" sekmesi veya yeni `Uplift.tsx`.

Akış:
1. Dataset + tedavi/outcome/feature kolon seçici.
2. Method seçimi + cost/input form.
3. **Sonuç ekranı (4 panel):**
   - Panel 1: Qini eğrisi (kümülatif uplift, x = seçilen popülasyon yüzdesi).
   - Panel 2: Segment kartları (4 sınıf, her biri büyüklük + ortalama uplift + iş tanımı).
   - Panel 3: Feature importance (uplift bazlı).
   - Panel 4: ROI slider'ı — bütçe değişince threshold otomatik günceller.
4. "Modeli kaydet" → registry'de featured uplifter olarak depolanır.

**Durumlar:** loading — eğitim sırasında Qini eğrisi animation; empty — segment verisi yoksa CTA; error — IMBALANCE uyarısı inline banner.

**Entegrasyon:** `QiniCurve`, `SegmentCards`, `ROIOptimizer` (K3); `frontend/src/app/screens/Uplift.tsx`.

## 4. Bağımlılıklar

- A1 (AB Testing): random assignment'ın doğruluğunu varsayarız.
- A5 (Causal): "persuadable" tanımı A5'teki ATT ile aynı temelden geliyor.
- B1 (Data Profiling): feature kalite kontrolü.
- C3 (KPI): ROI hesabı için maliyet/bütçe verisi.
- E2 (HPO): model tuning için trial sistemi.
- F2 (Champion-Challenger): uplifter karşılaştırması.
- Backend: `scikit-uplift`, `causalml`, `econml`.

## 5. Kapsam Dışı

- Çoklu tedavi (multi-arm uplift) — v1 yalnız ikili tedavi.
- Zamana göre değişen tedavi olasılığı (drift correction).
- Bayesian uplift — Faz 3+ A3 ile.

## 6. Test & Definition of Done

**Birim testleri:**
- Sıfır-etki veri: Qini ≈ 0, segmentasyon anlamsız (regres yapar).
- Gerçek uplift olan sentetik veri: Qini > 0, persuadable segment anlamlı.
- ROI threshold: doğru marjinal-değer eşiği.

**E2E:** Mevcut bir A/B veri seti üzerinde uplifter eğit → A1 sonucuyla cross-check.

**Definition of Done:**
- 4 method (T/X-learner, uplift tree, R-learner) hepsi çalışır.
- 4 segment kartı otomatik üretilir.
- Qini eğrisi + ROI threshold UI'da.
- Reaktif tool: `uplift_train`, `uplift_score`, `uplift_segment`.
- Spec durumu ✍️ → 🚧 → ✅.
