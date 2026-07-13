# C1 — Insight Mining (EDA eki)

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** otomatik içgörü katmanı

## 1. Amaç & Kullanıcı Hikâyeleri

EDA ajanının ürettiği grafiklerden öte, 'ilginç olan' segmentleri/korelasyonları/aykırılıkları ön plana çıkaran otomatik içgörü katmanı.

**Kabul senaryoları:**

1. EDA ajanı bir dataset analiz ederken otomatik içgörü kartları üretir.
2. Her içgörü: bulgu + kanıt grafiği + 'derinleştir' linki.
3. İçgörüler feed'inde sıralı görünür; kullanıcı 'ilginç değil' diyebilir.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/c1_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "data.insight",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /insights`
- `GET /insights/{id}`
- `GET /insights`

**Veri modeli:**
- `c1_runs (run_id, status, params_json, result_json, created_at)`
- `c1_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** EDA çıktı ekranında 'Insights' sekmesi

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- B1 (profiling)
- E1 (EDA core)
- J1 (autonomous investigation)
- `pandas-profiling`
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
- İlgili node tipi `data.insight` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
