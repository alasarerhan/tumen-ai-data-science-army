# B2 — Data Validation / Kalite Kapısı

> **Öncelik:** P0 · **Faz:** 1 · **Kapsam:** great-expectations tarzı veri sözleşmeleri

## 1. Amaç & Kullanıcı Hikâyeleri

Pipeline dünyasının 'güvenlik kapısı' — downstream her node çalışmadan önce tanımlı beklentiler (kolon tipleri, değer aralıkları, null oranları, dağılım kontrolleri) sağlanıyor mu diye bakar. İhlalde node durur veya HITL'e düşer.

**Kabul senaryoları:**

1. Kullanıcı expectation suite tanımlar (kolon + kural + eşik); pipeline node'unda kalite kapısı olarak çalışır.
2. İhlalde pipeline durur veya HITL'e düşer; run detayında hangi kural, kaç satır ve örnek ihlaller gösterilir.
3. Şablon galerisinden 'müşteri verisi için hazır' seti tek tıkla seçilebilir.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/b2_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "data.validate",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /validation`
- `GET /validation/{id}`
- `GET /validation`

**Veri modeli:**
- `b2_runs (run_id, status, params_json, result_json, created_at)`
- `b2_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Kuralda var olmayan kolon → 400.

## 3. UI Tasarımı

**Konum:** Datasets ekranında beklenti eki; Designer'da 'quality gate' node config

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- A1 (data shape assumptions)
- I2 (catalog)
- G1 (drift baseline)
- J13 (diff panel)
- `great_expectations`

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
- İlgili node tipi `data.validate` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
