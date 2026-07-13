# D3 — Feature Store

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** versiyonlu feature saklama

## 1. Amaç & Kullanıcı Hikâyeleri

Feature tanımlarını versiyonlanmış şekilde saklar; train-serve tutarlılığı için feature katalog (P2).

**Kabul senaryoları:**

1. Feature tanımı versiyonlanmış şekilde saklanır.
2. Train-serve consistency: eğitim ve batch serving aynı feature tanımından okur.
3. Katalog görünümü: arama, versiyon, kullanan modeller.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/d3_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "feature.register",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /features`
- `GET /features/{id}`
- `GET /features`

**Veri modeli:**
- `d3_runs (run_id, status, params_json, result_json, created_at)`
- `d3_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Yeni 'Features' ekranı (katalog + versiyon + kullanım)

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- I2 (catalog)
- D2 (selection)
- E1/G4 (consumption)
- `feast (advisor only — base registry on artifact store)`

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
- İlgili node tipi `feature.register` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
