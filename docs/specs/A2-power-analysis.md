# A2 — Power Analysis & Deney Tasarımı

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** Deney tasarlayan analist / data scientist; deney süresini planlayan ürün yöneticisi.
**Neden:** Deneye başlamadan önce "kaç kullanıcı, kaç gün, hangi MDE" sorusunu doğru cevaplamak; underpowered deneyleri baştan engellemek; randomizasyon/stratifikasyon önerisi almak.

Kabul senaryoları:
1. Analist baseline dönüşüm oranı %4, MDE %10 (relative), güç 0.8, alfa 0.05 girer; sistem grup başına gerekli örneklemi ve günlük trafik verisiyle tahmini süreyi döner.
2. MDE slider'ı oynatıldığında örneklem/süre grafiği canlı güncellenir (backend'e gitmeden, formül client'ta da hesaplanır; kesin değer API'dan doğrulanır).
3. Geçmiş dataset seçilirse sistem baseline oranı/ortalamayı ve varyansı otomatik hesaplar, kategori kolonlarından stratifikasyon adayları önerir.
4. Tasarım "deney planı" artifact'ı olarak kaydedilir ve A1 sihirbazına ön-doldurma olarak taşınır.

## 2. Backend Tasarımı

**Agent/Servis:** hesap deterministik olduğundan ağır agent gerekmez; `ai_data_science_team/agents/experiment_design_agent.py` — LLM yalnız stratifikasyon önerisi ve sade dilli açıklama için, çekirdek hesap `statsmodels` ile saf fonksiyon (`ai_data_science_team/tools/power.py`).

**Node tipi:** `experiment.design` (opsiyonel — pipeline'da veri→tasarım zinciri için):

```json
{
  "type": "experiment.design",
  "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": false}],
  "outputs": [{"name": "design", "artifact_type": "experiment_design", "required": true}],
  "config": {
    "metric_kind": "binary",
    "baseline": 0.04,
    "mde_relative": 0.10,
    "power": 0.8,
    "alpha": 0.05,
    "n_variants": 2,
    "daily_traffic": 12000
  }
}
```

**API endpoint'leri** (`platform_api/routes/experiments.py` içine, A1 ile aynı router):
- `POST /experiments/power` — senkron hesap; body yukarıdaki config → `{n_per_group, total_n, days_estimate, mde_curve: [{mde, n}], assumptions}`.
- `POST /experiments/design/suggest` — `{dataset_ref, metric_column}` → baseline/varyans otomatik + `{stratification_candidates: [{column, reason}], randomization_unit_note}` (LLM destekli).
- `POST /experiments/designs` / `GET /experiments/designs/{id}` — tasarım kaydet/oku.

**Veri modeli:** `experiment_designs` tablosu: `id, name, config_json, result_json, dataset_ref, created_by, created_at`. A1 `experiments.design_id` FK (nullable).

**Hata durumları:** baseline ∉ (0,1) binary metrikte (422) · MDE ≤ 0 (422) · dataset'te metrik kolonu yok (400) · daily_traffic yoksa süre alanı `null` döner, hata değil · aşırı küçük MDE'de n > 10^8 ise "pratik değil" uyarı bayrağı.

## 3. UI Tasarımı

**Konum:** A1 `ExperimentWizard`'ın 0. adımı ("Deney tasarımı") + bağımsız erişim için Experiments ekranında "Yeni tasarım" butonu.

Akış:
1. Metrik tipi seç (binary/sürekli) → baseline'ı elle gir veya dataset'ten hesaplat.
2. MDE, güç, alfa, varyant sayısı girdileri; günlük trafik opsiyonel.
3. **Canlı grafik:** X ekseni MDE, Y ekseni gerekli örneklem (ikinci eksen: gün); slider hareketinde anında güncellenir; seçilen nokta vurgulanır.
4. "Stratifikasyon öner" butonu → aday kolon listesi (neden açıklamalı kartlar).
5. "Tasarımı kaydet" → A1 sihirbazına "bu tasarımla deneye başla" aksiyonu.

**Durumlar:** loading — grafik skeleton + hesap spinner'ı; empty — form varsayılanlarla dolu gelir (empty state yok denecek kadar hafif); error — form alanı bazlı inline validasyon mesajları (422 detayları alanlara eşlenir).

**Entegrasyon:** `frontend/src/app/screens/Experiments.tsx` içinde `PowerAnalysisPanel` bileşeni; MetricCard/ChartContainer (K3) yeniden kullanılır.

## 4. Bağımlılıklar
- **Spec:** A1 (aynı ekran + router), (bileşenler), I2 (dataset kolon istatistikleri — opsiyonel hızlandırıcı).
- **Python:** `statsmodels.stats.power` (NormalIndPower, TTestIndPower), `statsmodels.stats.proportion.proportion_effectsize`, `scipy.stats`, `pandas`.
- **JS:** chart kütüphanesi (canlı eğri), debounce'lu slider.
- **Kod noktaları:** `platform_api/routes/experiments.py`, `ai_data_science_team/tools/` (mevcut tool pattern'i), `frontend/src/app/screens/Experiments.tsx`.
## 5. Kapsam Dışı

- Sequential/adaptive tasarım (grup sequential sınırlar).
- Cluster-randomized ve network-etkili deney tasarımı.
- Trafik bölme/atama altyapısı.
- Bayesian örneklem planlaması (A3 sonrası değerlendirilir).

## 6. Test & Definition of Done

Test senaryoları:
- Birim: binary metrik, baseline 0.04, MDE %10 rel., power 0.8 → n_per_group statsmodels referans değeriyle ±1 eşleşir; sürekli metrik Cohen's d yolu doğru.
- Birim: n_variants=3'te Bonferroni-ayarlı alfa ile n'in arttığı doğrulanır; geçersiz girdiler 422.
- Birim: dataset'ten baseline hesabı (NaN'lar düşülerek) doğru.
- E2E: slider hareketi grafiği günceller; "Tasarımı kaydet" sonrası A1 sihirbazı ön-dolu açılır.

DoD checklist:
- [ ] `POST /experiments/power` deterministik ve test kapsamında
- [ ] MDE↔süre canlı grafiği çalışıyor (client hesap + API doğrulama)
- [ ] Stratifikasyon önerisi LLM çağrısı fallback'li (LLM hatasında sadece hesap döner)
- [ ] Tasarım kaydet/oku + A1 ön-doldurma akışı çalışıyor
- [ ] `experiment_designs` migration'ı merge edildi
- [ ] Loading/empty/error durumları K3 standardında
