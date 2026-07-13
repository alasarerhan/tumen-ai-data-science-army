# B6 — Synthetic Data

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** SDV/CTGAN ile sentetik tablo

## 1. Amaç & Kullanıcı Hikâyeleri

Gerçek tabloyu paylaşamadığınız durumlar için (PII, sözleşme, geliştirme ortamı) istatistiksel olarak benzer sentetik tablo üretir. Üretim sonrası orijinal-sentetik benzerlik raporu görünür.

**Kabul senaryoları:**

1. Kullanıcı satır sayısı + korunacak ilişkileri belirler; sentetik tablo üretilir.
2. Üretim raporu: gerçek-sentetik benzerlik skoru, KS/PSI dağılım farkları.
3. Sentetik veri 'özel' olarak işaretlenir; gerçek veriyle karışmaz.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/b6_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "data.synthesize",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /synthetic`
- `GET /synthetic/{id}`
- `GET /synthetic`

**Veri modeli:**
- `b6_runs (run_id, status, params_json, result_json, created_at)`
- `b6_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Hedef satır sayısı sıfır/negatif → 400.

## 3. UI Tasarımı

**Konum:** Datasets ekranında 'Generate Synthetic' aksiyonu

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- B1 (profiling baseline)
- B5 (PII masking)
- J13 (diff quality)
- `sdv`
- `ctgan`

## 5. Kapsam Dışı

- MVP dışı: çoklu kullanıcı işbirliği (CRDT) yetenekleri
- Üretime hazır olmayan deneysel algoritmaların kütüphaneye eklenmesi
- Cross-tenant veri paylaşımı (governance tarafından yönetilir)

## 6. Test & Definition of Done

**Birim testleri:**
- Birim: temel happy-path input → beklenen çıktı şeması.
- Birim: kötü parametre (eksik alan, yanlış tip) → 400/422 + tanımlı mesaj.
- Birim: deterministic seed ile çalıştırıldığında aynı sonuç.

**Definition of Done:**
- Şablondaki 6 bölümün hepsi doldurulmuş.
- Backend tool ajan için tool-name registry'si export edilmiş.
- İlgili node tipi `data.synthesize` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
