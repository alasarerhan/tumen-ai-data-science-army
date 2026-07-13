# J9 — Proje Şablonları

> **Öncelik:** P1 · **Faz:** 2 · **Kapsam:** hazır uçtan uca pipeline'lar

## 1. Amaç & Kullanıcı Hikâyeleri

Churn, forecast, segmentasyon, fraud için hazır uçtan uca pipeline şablonları.

**Kabul senaryoları:**

1. Churn, forecast, segmentasyon, fraud için hazır uçtan uca pipeline'lar.
2. I1 planner'ın few-shot temeli.
3. 'Yeni Workflow' şablon galerisi + önizleme canvas'ı.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/j9_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "workflow.template",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /templates`
- `GET /templates/{id}`
- `GET /templates`

**Veri modeli:**
- `j9_runs (run_id, status, params_json, result_json, created_at)`
- `j9_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** 'New Workflow' şablon galerisi

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- J8 (visual recipes)
- I1 (planner few-shot)
- `none — content-driven`

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
- İlgili node tipi `workflow.template` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
