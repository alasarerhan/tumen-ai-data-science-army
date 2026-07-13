# J2 — Self-Healing Pipeline

> **Öncelik:** P1 · **Faz:** 2 · **Kapsam:** AI diagnose + repair

## 1. Amaç & Kullanıcı Hikâyeleri

Node hatasında AI kök-neden + otomatik onarım (şema düzeltme, fallback agent).

**Kabul senaryoları:**

1. Node hatası → AI kök-neden analizi.
2. Otomatik onarım denemeleri (şema düzeltme, fallback agent).
3. Onarılamazsa HITL'e düşer (açıklamalı).

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/j2_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "pipeline.heal",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /heal`
- `GET /heal/{id}`
- `GET /heal`

**Veri modeli:**
- `j2_runs (run_id, status, params_json, result_json, created_at)`
- `j2_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Run detayında 'Auto-Repair' timeline'ı

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- A1/F2 (run analysis)
- J7 (governance approval)
- `langgraph diagnose`
- `monitoring`

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
- İlgili node tipi `pipeline.heal` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
