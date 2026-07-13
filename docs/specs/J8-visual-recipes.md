# J8 — Visual Recipe Kitaplığı

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** kodsuz dönüşüm node'ları

## 1. Amaç & Kullanıcı Hikâyeleri

Kodsuz ince taneli dönüşüm node'ları (join, group, pivot, filter, split, union, window).

**Kabul senaryoları:**

1. Kodsuz ince taneli dönüşüm node'ları (join, group, pivot, filter, split, union, window).
2. Designer palette'inde 'Recipes' sekmesi.
3. Çift tık → görsel konfig (kolon seçici, koşul builder).

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/j8_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "transform.recipe",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /recipes`
- `GET /recipes/{id}`
- `GET /recipes`

**Veri modeli:**
- `j8_runs (run_id, status, params_json, result_json, created_at)`
- `j8_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Designer paletinde 'Recipes' sekmesi

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- J9 (template)
- B3 (schema)
- `react-flow custom nodes`

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
- İlgili node tipi `transform.recipe` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
