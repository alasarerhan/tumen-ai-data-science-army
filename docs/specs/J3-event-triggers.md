# J3 — Olay Tabanlı Tetikleyiciler

> **Öncelik:** P1 · **Faz:** 2 · **Kapsam:** trigger + koşul + aksiyon

## 1. Amaç & Kullanıcı Hikâyeleri

Trigger + koşul + aksiyon zinciri: yeni veri, dataset değişimi, kalite geçişi, workflow bitimi.

**Kabul senaryoları:**

1. Trigger + koşul + aksiyon zinciri.
2. Yeni veri / dataset değişimi / kalite geçişi / workflow bitimi.
3. Tetiklenme geçmişi + dry-run simülasyon.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/j3_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "trigger.configure",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /triggers`
- `GET /triggers/{id}`
- `GET /triggers`

**Veri modeli:**
- `j3_runs (run_id, status, params_json, result_json, created_at)`
- `j3_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Workflow ekranında 'Triggers' sekmesi

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- B7 (data events)
- G1 (drift events)
- J7 (governance gate)
- `temporalio (advisor)`

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
- İlgili node tipi `trigger.configure` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
