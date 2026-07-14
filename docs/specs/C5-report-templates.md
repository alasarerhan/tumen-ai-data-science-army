# C5 — Rapor genişletmesi

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** şablonlu periyodik rapor

## 1. Amaç & Kullanıcı Hikâyeleri

Şablonlu periyodik raporlar: 'haftalık KPI özeti', 'deney sonuç raporu' vb. PDF/PPTX/Markdown export.

**Kabul senaryoları:**

1. Hazır rapor şablonları: 'haftalık KPI özeti', 'deney sonuç raporu'.
2. Periyod zamanlama + dağıtım listesi.
3. PDF / PPTX / Markdown export.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/c5_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "report.template",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /reports`
- `GET /reports/{id}`
- `GET /reports`

**Veri modeli:**
- `c5_runs (run_id, status, params_json, result_json, created_at)`
- `c5_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Reports ekranında template galerisi + schedule form

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar
- A1 (experiment reports)
- C3 (KPI rolls)
- (exports)
- `jinja2`
- `weasyprint`
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
- İlgili node tipi `report.template` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
