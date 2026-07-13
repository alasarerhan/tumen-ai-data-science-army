# A3 — Bayesian Analysis

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** A/B sonuçlarını p-değeri yerine olasılık diliyle okumak isteyen analist; "B'nin daha iyi olma olasılığı %96" cümlesini isteyen ürün yöneticisi.
**Neden:** Frequentist sonuçların yanına posterior dağılım, "probability to be best" ve expected loss ekleyerek erken/az veriyle daha sezgisel karar desteği vermek.

Kabul senaryoları:
1. A1'de analiz edilmiş binary metrikli deneyde kullanıcı "Bayesian görünüm" sekmesini açar; Beta-Binomial posterior'lar, P(B>A) ve expected loss tablosu görünür.
2. Sürekli metrikte (gelir) PyMC ile normal/log-normal model örneklenir; posterior fark dağılımı grafiği ve %95 HDI raporlanır.
3. Kullanıcı karar eşiği belirler (ör. expected loss < 0.1%); sistem "B'yi yayınlamak güvenli" rozetini bu eşiğe göre renklendirir.
4. Üç varyantta her varyant için "en iyi olma olasılığı" bar'ı gösterilir.

## 2. Backend Tasarımı

**Agent:** `ai_data_science_team/agents/bayesian_analysis_agent.py` — çekirdek hesap saf fonksiyonlarda (`ai_data_science_team/tools/bayesian.py`): binary metrikler için **conjugate Beta-Binomial** (hızlı, örnekleme gerekmez, `numpy` Monte Carlo ile P(best)/expected loss), sürekli metrikler için **PyMC** (opsiyonel bağımlılık; yoksa normal-approx fallback).

**Node tipi:** ayrı node açılmaz; `experiment.analyze` config'ine `"bayesian": true` bayrağı eklenir, çıktı artifact'ına `bayesian` bloğu yazılır. Ağır PyMC işi `workflow_worker.py` üzerinden async çalışır.

```json
{
  "type": "experiment.analyze",
  "config": {"bayesian": true, "priors": {"kind": "beta", "alpha": 1, "beta": 1}, "loss_threshold": 0.001},
  "outputs_extension": {
    "bayesian": {
      "posteriors": [{"variant": "B", "dist": "beta", "params": [341, 7893], "samples_summary": {"mean": 0.0414, "hdi_low": 0.037, "hdi_high": 0.046}}],
      "prob_best": {"A": 0.04, "B": 0.96},
      "expected_loss": {"A": 0.0041, "B": 0.0002},
      "decision": {"safe_to_ship": "B", "threshold": 0.001}
    }
  }
}
```

**API endpoint'leri:**
- `POST /experiments/{id}/bayesian` — mevcut deney sonucuna Bayesian katman hesaplar (async, `job_id` döner; Beta-Binomial ise senkron döner).
- `GET /experiments/{id}/bayesian` — sonuç + posterior grafik verisi (yoğunluk eğrisi noktaları, x/y dizileri).

**Veri modeli:** yeni tablo yok; `experiments.result_artifact_id` altındaki artifact'a `bayesian` bloğu eklenir (artifact service, versiyonlu).

**Hata durumları:** deney sonucu yok (404) · PyMC kurulu değil + sürekli metrik → 200 ama `method: "normal_approx"` uyarısıyla · MCMC divergence oranı > %1 → sonuç döner, `diagnostics.warning` alanı dolar · geçersiz prior parametresi (422) · örnekleme timeout (dakika sınırı, worker'da 504-eşleniği run hatası).

## 3. UI Tasarımı

**Konum:** A1 deney sonuç sayfasında ikinci sekme — **"Bayesian görünüm"** (`frontend/src/app/screens/Experiments.tsx` içinde `BayesianTab` bileşeni).

Akış:
1. Sekmeye ilk girişte "Bayesian analizi hesapla" CTA'sı (binary'de anında, sürekli metrikte progress'li).
2. Sonuç: üstte varyant başına posterior yoğunluk eğrileri (üst üste, yarı saydam); altında "B'nin daha iyi olma olasılığı: %96" büyük metrik kartı.
3. Expected loss tablosu + karar eşiği input'u; eşik değişince rozet client'ta yeniden renklenir.
4. "Frequentist ile karşılaştır" info kutusu: iki yaklaşımın kararı çelişiyorsa sarı uyarı.

**Durumlar:** loading — MCMC için adımlı progress ("model kuruluyor → örnekleniyor → özetleniyor"); empty — hesapla CTA'sı; error — diagnostics uyarıları amber banner, sert hatalar eyleme dönük mesaj ("PyMC yüklü değil; yaklaşık yöntem kullanıldı" gibi bilgi durumu ayrı).

**Entegrasyon:** A1 sonuç sayfası sekme yapısı; ChartContainer/MetricCard (K3).

## 4. Bağımlılıklar

- **Spec:** A1 (zorunlu ön koşul — aynı deney kaydı ve sonuç sayfası), K3.
- **Python:** `numpy`, `scipy.stats` (beta, norm), `pymc>=5` + `arviz` (opsiyonel extra: `pip install .[bayesian]`), `pandas`.
- **JS:** yoğunluk eğrisi çizimi (mevcut chart kütüphanesi, area chart).
- **Kod noktaları:** `platform_api/routes/experiments.py`, `platform_api/workers/workflow_worker.py` (async job), `ai_data_science_team/tools/`, `frontend/src/app/screens/Experiments.tsx`.

## 5. Kapsam Dışı

- Bayesian örneklem planlaması / sequential durdurma kuralları.
- Hiyerarşik modeller (segment bazlı partial pooling).
- A1 dışındaki genel amaçlı Bayesian modelleme (regresyon vb.).
- Prior elicitation UI'ı (varsayılan zayıf-bilgilendirici prior'lar; sadece parametre alanı).

## 6. Test & Definition of Done

Test senaryoları:
- Birim: Beta-Binomial posterior parametreleri (prior + başarı/deneme) elle hesapla eşleşir; simetrik veride P(B>A) ≈ 0.5 (±0.02, MC toleransı).
- Birim: expected loss monotonluğu — açık kazanan varyantta loss ≈ 0; kaybedende pozitif.
- Birim: PyMC yokken sürekli metrik normal-approx fallback'ine düşer ve `method` alanı doğru işaretlenir.
- E2E: A1 sonucu → Bayesian sekmesi → posterior grafiği ve P(best) kartı render; eşik değişimi rozeti günceller.

DoD checklist:
- [ ] Beta-Binomial yolu senkron, PyMC yolu async worker'da çalışıyor
- [ ] `bayesian` artifact bloğu şemaya eklendi ve versiyonlu saklanıyor
- [ ] PyMC opsiyonel bağımlılık olarak paketlendi, fallback testli
- [ ] BayesianTab grafikleri + karar eşiği etkileşimi tamam
- [ ] MCMC diagnostics uyarıları UI'da görünüyor
- [ ] Frequentist-Bayesian çelişki uyarısı çalışıyor
