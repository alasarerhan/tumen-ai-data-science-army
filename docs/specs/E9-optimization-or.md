# E9 — Optimization / OR

> **Öncelik:** P3 · **Faz:** 4 · **Kapsam:** LP/MIP çözücü

## 1. Amaç & Kullanıcı Hikâyeleri

LP/MIP optimizasyon problemleri (tahsis, rota, envanter); PuLP/OR-Tools backend.

**Kabul senaryoları:**

1. LP/MIP problemleri: tahsis, rota, envanter.
2. PuLP / OR-Tools backend.
3. Kısıt/objective formu, çözüm tablosu, duyarlılık raporu.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/e9_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.train.or",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /train/or`
- `GET /train/or/{id}`
- `GET /train/or`

**Veri modeli:**
- `e9_runs (run_id, status, params_json, result_json, created_at)`
- `e9_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Designer'da OR node + kısıt formu

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- I2 (data source)
- F1 (evaluation)
- `pulp`
- `ortools`

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
- İlgili node tipi `model.train.or` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
