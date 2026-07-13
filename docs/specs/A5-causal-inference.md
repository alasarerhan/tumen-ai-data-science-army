# A5 — Causal Inference

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** Deney kültürü olgunlaşmamış organizasyonlarda "bu ürün değişikliği gerçekten metriği etkiledi mi" sorusunu cevaplaması gereken analistler; pazarlama/cheddar (gelir) ekibi atribüsyon soruları.

**Neden:** Tedavi her zaman deneyle değerlendirilemez (etik, maliyet, geçmiş veri). Observational data üzerinde nedensel etki tahmini gerekir — propensity matching, doubly-robust estimators, diff-in-diff, IV.

Kabul senaryoları:
1. Kullanıcı tedavi (treatment), sonuç (outcome), karıştırıcı (confounder) kolonlarını seçer; ajan tahmini nedensel etkiyi (ATE/ATT) + güven aralığını + varsayım ihlali uyarılarını döner.
2. Diff-in-diff için "önce/sonra + tedavi/kontrol" verisi verildiğinde parallel-trends testi otomatik yapılır; ihlalde uyarı.
3. Duyarlılık analizi: gizli karıştırıcı eklenince tahmin ne kadar değişir (E-value).
4. Çıktı "yorum" diline uygun — iş sorusuna bağlanır, sadece istatistik değil.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/causal_agent.py` — `langgraph` react-agent; deterministic çekirdek `ai_data_science_team/tools/causal.py`.

**Node tipi:** `experiment.causal`:
```json
{
  "type": "experiment.causal",
  "config": {
    "method": "propensity|did|iv|dr",
    "treatment_col": "exposed",
    "outcome_col": "revenue",
    "confounders": ["age","region","tenure"]
  }
}
```

**API endpoint'leri** (`platform_api/routes/causal.py`):
- `POST /causal/estimate` — body: yukarıdaki config + dataset_ref → `{ate, att, ci_low, ci_high, p_value, method, diagnostics: {propensity_overlap, parallel_trends_p, sensitivity_e_value}}`.
- `GET /causal/diagnostics/{run_id}` — refuter/duyarlılık raporu (DoWhy/EconML).

**Veri modeli:** `causal_analyses` tablosu: `id, run_id, dataset_id, config_json, result_json, method, status, created_at`. Tablo çıktıları `causal_effect_estimates` (her refuter/method için bir satır).

**Hata durumları:** treatment varyansı sıfır (400) · confounder listede yok (400) · propensity overlap < 0.1 (200 + uyarı) · IV için instrument kolonu zayıf (F<10) (200 + uyarı).

## 3. UI Tasarımı

**Konum:** `Experiments.tsx` veya yeni `Causal.tsx` ekranı; chat'ten inline çağrılabilir.

Akış:
1. Dataset seç → tedavi/sonuç/confounder kolon seçici (I2 catalog picker'ı yeniden kullanılır).
2. Method seçimi (radio: Propensity / DiD / IV / Doubly Robust) → method'a özel ek alanlar (zaman kolonu için DiD, instrument için IV).
3. Sonuç: treatment effect kartı (nokta tahmin + CI), yöntem tanı açıklaması ("neden bu yöntem, hangi varsayımlar").
4. Diagnostics paneli: propensity dağılımı, parallel-trends grafiği, E-value uyarısı.
5. "Raporla" → F4 model card'a benzer "Causal Report" PDF.

**Durumlar:** loading — diagnostics hesaplanırken skeleton; empty — ilk açılışta dataset seçilmemişse CTA; error — veri format uyumsuzluğunda kolon bazlı inline.

**Entegrasyon:** `frontend/src/app/screens/Causal.tsx`; `MethodExplainerCard`, `EffectEstimateCard`, `DiagnosticsChart` (ChartContainer K3).

## 4. Bağımlılıklar

- A1 (AB Testing): nedensel vs deneysel sonuç karşılaştırması.
- B3 (Schema Inference): kolon tiplerini temiz çıkarmak için.
- D2 (Feature Selection): confounder listesini önermek için.
- F3 (Fairness Audit): korunan özellik (protected attribute) için aynı kolon seçici bileşen.
- I2 (Data Catalog): kolon metadata.
- Backend tool kütüphanesi: `dowhy`, `econml`.

## 5. Kapsam Dışı

- Rastgele nedensel çıkarım ağaçları (causal forest) — F2 Champion-Challenger'la çakışır; MVP dışı.
- Zaman-değişkenli karıştırıcılar (longitudinal treatments) — Faz 4+ düşünülebilir.
- Tıbbi nedensellik (epidemiyoloji) domain bilgisi — genel kalsın.

## 6. Test & Definition of Done

**Birim testleri:**
- ATE tahmini sentetik veriyle gerçek değere ±5% yakın.
- Refuter: random common cause eklenince tahmin ±10% içinde (sıfır etki testi).
- IV: zayıf instrument F<10 olduğunda uyarı döner.

**E2E senaryolar:**
- DiD ile iki dönemli marketing campaign analizi; parallel-trends görselleştirmesi.
- Propensity matching sonrası kontrol/tedavi Kovariate balance raporu.

**Definition of Done:**
- 4 method (Propensity, DiD, IV, DR) hepsi çalışır.
- Reaktif agent tool'ları: `causal_estimate`, `causal_diagnostics`, `causal_refute`.
- UI'da 4 method için ayrı form şeması.
- PLATFORM_SPEC.md bu spec'in durumu ✍️ → 🚧 → ✅.
