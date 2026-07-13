# K3 — UI Standartları & Design System

> **Öncelik:** P0 · **Faz:** 1 · **Kapsam:** UI kit + standartlar

## 1. Amaç & Kullanıcı Hikâyeleri

Ortak UI bileşen kitaplığı, agent şeffaflık standardı, streaming UX, erişilebilirlik, koyu/açık mod.

**Kabul senaryoları:**

1. Ortak UI bileşen kitaplığı (DataTable, MetricCard, StatusBadge, DiffView...).
2. Agent şeffaflık standardı, streaming UX.
3. Erişilebilirlik (ARIA), koyu/açık mod.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/k3_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "ui.standardize",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /ui-kit`
- `GET /ui-kit/{id}`
- `GET /ui-kit`

**Veri modeli:**
- `k3_runs (run_id, status, params_json, result_json, created_at)`
- `k3_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Tüm ekranların tükettiği bileşen kitaplığı

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- Universal — every UI screen consumes K3 components.
- `tailwindcss`
- `radix-ui`

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
- İlgili node tipi `ui.standardize` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
