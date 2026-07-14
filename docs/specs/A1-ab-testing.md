# A1 — AB Testing

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** Growth analisti, data scientist, ürün yöneticisi (rapor tüketicisi).
**Neden:** Deney sonucu verisini yükleyip güvenilir, istatistiksel olarak doğru bir "ship / iterate / abort" kararına dakikalar içinde ulaşmak; SRM ve çoklu karşılaştırma gibi klasik tuzaklara düşmemek.

Kabul senaryoları:
1. Analist iki gruplu dönüşüm deneyi verisini (user_id, group, converted) seçer; sistem SRM kontrolü yapar, chi-square testi koşar, lift + %95 CI ve karar önerisi döner.
2. Üç varyantlı sürekli metrikte (gelir) sistem normallik/varyans varsayımlarını kontrol eder, Mann-Whitney veya Welch t seçer, Benjamini-Hochberg düzeltmesi uygular ve hangi varyantın kazandığını raporlar.
3. Grup oranları 50/50 beklenirken 58/42 gelirse sonuç sayfasının üstünde SRM uyarı banner'ı çıkar ve karar kutusu "sonuçlara güvenme" moduna düşer.
4. Pre-experiment kovaryat kolonu verilirse CUPED uygulanır ve varyans azaltımı yüzdesi raporlanır.

## 2. Backend Tasarımı

**Agent:** `ai_data_science_team/agents/ab_testing_agent.py` mevcut; `ABTestAnalysisAgent` olarak genişletilir (SRM, test seçimi, CUPED, düzeltme, karar motoru). LangGraph tarzı diğer agent'larla aynı yapıda (`make_ab_testing_agent`).

**Node tipi:** `experiment.analyze` — `apps/platform-api-app/platform_api/services/workflow_node_catalog_service.py` kataloğuna eklenir, yürütme `workflow_node_executor_service.py` içinde.

```json
{
  "type": "experiment.analyze",
  "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": true}],
  "outputs": [{"name": "experiment_report", "artifact_type": "experiment_report", "required": true}],
  "config": {
    "group_column": "variant",
    "metric_columns": [{"name": "converted", "kind": "binary"}, {"name": "revenue", "kind": "continuous"}],
    "expected_allocation": {"A": 0.5, "B": 0.5},
    "correction": "benjamini_hochberg",
    "cuped_covariate": "pre_revenue",
    "alpha": 0.05
  }
}
```

**Artifact şeması (`experiment_report`):** `srm: {p_value, passed}`, `tests: [{metric, test_name, reason, statistic, p_value, p_adjusted, lift, ci_low, ci_high, effect_size}]`, `cuped: {applied, variance_reduction}`, `decision: {verdict: "ship|iterate|abort", rationale}`.

**API endpoint'leri** (`apps/platform-api-app/platform_api/routes/` altına `experiments.py`):
- `POST /experiments/analyze` — body: `{dataset_ref, config}` → run başlatır, `run_id` döner (worker: `platform_api/workers/workflow_worker.py`).
- `GET /experiments/{id}` — analiz sonucu artifact'ı (JSON şema yukarıdaki).
- `POST /experiments/{id}/report` — C5 rapor üretimine köprü (`report.generate` node'u tetikler).

**Veri modeli:** yeni `experiments` tablosu (SQLAlchemy migration): `id, name, dataset_ref, config_json, result_artifact_id, decision, created_by, created_at`. Sonuçlar artifact service üzerinden saklanır.

**Hata durumları:** grup kolonu bulunamadı (400, kolon listesi önerisiyle) · tek grup / boş grup (422) · metrik tipi uyumsuz (binary bekleniyor, sürekli geldi) · örneklem < 30/grup → uyarı bayrağıyla nonparametrik fallback · SRM fail → analiz yine döner ama `decision.verdict = "abort"` ve `srm.passed=false`.

## 3. UI Tasarımı

**Ekran:** yeni `frontend/src/app/screens/Experiments.tsx` + kurulum sihirbazı bileşeni `ExperimentWizard`.

Akış:
1. Sihirbaz adım 1: dataset seçimi (DataSources picker'ı yeniden kullanılır).
2. Adım 2: grup kolonu, beklenen dağılım, metrik(ler) + tip seçimi; opsiyonel CUPED kovaryatı.
3. Adım 3: özet + "Analizi başlat" → run başlar, streaming durum (K3 progress standardı).
4. Sonuç sayfası: üstte SRM banner'ı (geçtiyse yeşil rozet), grup karşılaştırma kartları (n, ortalama/oran), metrik başına CI çubuğu grafiği (lift ± CI), test tablosu (test adı + neden seçildi tooltip'i), karar kutusu (ship/iterate/abort, gerekçe), "Rapora çevir" butonu (Reports ekranına).

**Durumlar:** loading — adımlı stepper ("SRM kontrolü → test seçimi → analiz"); empty — "Henüz deney yok" + CTA; error — eyleme dönük mesaj ("grup kolonu 'variant' bulunamadı, kolonlardan seç").

**Entegrasyon:** WorkflowDesigner paletine `experiment.analyze` node'u; RunDetail'de experiment_report artifact'ı için özel görselleştirici.

## 4. Bağımlılıklar
- **Spec:** A2 (sihirbazın ilk adımı olarak power analysis), A3 (Bayesian sekmesi), C5 (rapor export), (bileşen standartları).
- **Python:** `scipy.stats` (ttest_ind, mannwhitneyu, chi2_contingency, shapiro, levene), `statsmodels.stats.multitest` (multipletests), `statsmodels.stats.proportion` (proportion_confint), `numpy/pandas`.
- **JS:** mevcut chart kütüphanesi (ChartContainer, ), ReactFlow (Designer entegrasyonu).
- **Kod noktaları:** `ai_data_science_team/agents/ab_testing_agent.py`, `platform_api/services/workflow_node_catalog_service.py`, `platform_api/services/workflow_node_executor_service.py`, `platform_api/routes/workflows.py` (route pattern referansı), `frontend/src/app/screens/RunDetail.tsx`.
## 5. Kapsam Dışı

- Deney atama/feature-flag altyapısı (trafik bölme platform dışı).
- Sequential testing / always-valid p-values (ileride A3 ile).
- Bayesian analiz (A3'te), power analysis (A2'de).
- Kullanıcı-seviyesi olmayan (cluster-randomized) deneyler.

## 6. Test & Definition of Done

Test senaryoları:
- Birim: bilinen dataset'te chi-square p-değeri scipy referansıyla eşleşir; SRM 50/50 beklenti + 58/42 gerçekleşmede p<0.001 üretir; BH düzeltmesi 5 metrikte doğru sıralı p_adjusted verir; CUPED varyans azaltımı ≥0 ve lift işareti korunur.
- Birim: normallik ihlalinde (skewed veri) Mann-Whitney seçildiği ve `reason` alanının dolduğu doğrulanır.
- E2E: sihirbazdan dataset seç → analiz → sonuç sayfasında karar kutusu ve CI çubukları render olur; SRM fail senaryosunda banner görünür.
- API: geçersiz grup kolonu 400, tek grup 422 döner.

DoD checklist:
- [ ] `experiment.analyze` node kataloğa ve executor'a eklendi, workflow içinde çalışıyor
- [ ] `experiment_report` artifact şeması ve migration merge edildi
- [ ] REST endpoint'leri auth + testlerle hazır
- [ ] Experiments ekranı loading/empty/error durumlarıyla tamam
- [ ] SRM, çoklu karşılaştırma, CUPED birim testleri yeşil
- [ ] "Rapora çevir" akışı Reports ekranına çıktı üretiyor
