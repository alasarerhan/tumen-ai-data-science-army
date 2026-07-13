# E10 — Simulation / What-If

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** interaktif senaryo analizi

## 1. Amaç & Kullanıcı Hikâyeleri

Model tahminleri üzerinde interaktif senaryo analizi — slider/input değişimi → canlı tahmin + SHAP katkıları.

**Kabul senaryoları:**

1. Model detayında What-If paneli açılır.
2. Slider/input → model tahmini + SHAP katkıları canlı güncellenir.
3. Senaryolar kaydedilip karşılaştırılabilir.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/e10_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.whatif",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /whatif`
- `GET /whatif/{id}`
- `GET /whatif`

**Veri modeli:**
- `e10_runs (run_id, status, params_json, result_json, created_at)`
- `e10_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Model detayında 'What-If' sekmesi (K2 modelops)

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- E1 (model)
- F6 (LLM judge for explanations)
- K3 (interactive viz)
- `shap`
- `ipywidgets (server-side stubs)`

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
- İlgili node tipi `model.whatif` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
