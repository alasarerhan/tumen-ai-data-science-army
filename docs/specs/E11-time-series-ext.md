# E11 — Time Series genişletmesi

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** hiyerarşik forecast

## 1. Amaç & Kullanıcı Hikâyeleri

Hiyerarşik forecast (top-down reconciliation), tatil takvimi entegrasyonu, Prophet/statsforecast motorları.

**Kabul senaryoları:**

1. Hiyerarşik forecast (top-down reconciliation).
2. TR + ABD tatil takvimi.
3. Prophet / statsforecast / Nixtla motorları.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/e11_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.train.timeseries",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /train/timeseries`
- `GET /train/timeseries/{id}`
- `GET /train/timeseries`

**Veri modeli:**
- `e11_runs (run_id, status, params_json, result_json, created_at)`
- `e11_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Designer'da time-series node + forecast bandı grafiği

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- E1 (engine)
- B7 (data ingest)
- F1 (evaluation)
- `prophet`
- `statsforecast`

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
- İlgili node tipi `model.train.timeseries` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
