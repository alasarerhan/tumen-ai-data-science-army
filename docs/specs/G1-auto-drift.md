# G1 — Otomatik Drift Hesabı

> **Öncelik:** P0 · **Faz:** 1 · **Kapsam:** prediction + performance drift

## 1. Amaç & Kullanıcı Hikâyeleri

Prediction drift (PSI/KS) + performans düşüşü zamanlanmış otomatik hesap; baseline profile (B1) ile delta.

**Kabul senaryoları:**

1. Prediction drift (PSI/KS) + performans düşüşü zamanlı hesap.
2. Feature bazlı drift ısı listesi + referans vs güncel dağılım grafiği.
3. Threshold aşımı G2'ye sinyal gönderir.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/g1_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.drift.compute",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /drift`
- `GET /drift/{id}`
- `GET /drift`

**Veri modeli:**
- `g1_runs (run_id, status, params_json, result_json, created_at)`
- `g1_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Drift metrikleri NaN dönerse uyarı + 200 boş sonuç.

## 3. UI Tasarımı

**Konum:** K2 içinde 'Drift' sekmesi

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- B1 (baseline profile)
- F1 (eval history)
- G2 (auto retrain trigger)
- `scipy`
- `scikit-learn`

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
- İlgili node tipi `model.drift.compute` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
