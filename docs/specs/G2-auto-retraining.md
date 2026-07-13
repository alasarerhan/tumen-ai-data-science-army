# G2 — Auto-Retraining Orchestrator

> **Öncelik:** P0 · **Faz:** 1 · **Kapsam:** kapalı döngü retrain

## 1. Amaç & Kullanıcı Hikâyeleri

Policy motoru: tetikleyici → retrain → F2 değerlendirme → HITL onayı → promotion. Kapalı döngünün kalbi.

**Kabul senaryoları:**

1. Policy motoru: tetikleyici → retrain → F2 değerlendirme → HITL → promotion.
2. Politika simülasyonu: geçmiş veriye uygulandığında tetiklenme sayısı.
3. Audit trail: tetikleme→karar→uygulama zaman çizelgesi.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/g2_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.retrain.policy",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /retrain`
- `GET /retrain/{id}`
- `GET /retrain`

**Veri modeli:**
- `g2_runs (run_id, status, params_json, result_json, created_at)`
- `g2_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Policy çakışması (iki politika aynı tetikleyici için) → 409.

## 3. UI Tasarımı

**Konum:** K2 içinde 'Retrain Policy' bölümü

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- G1 (drift input)
- F2 (champion-challenger)
- J7 (governance)
- E1 (retrain)
- `Prefect flows`

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
- İlgili node tipi `model.retrain.policy` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
