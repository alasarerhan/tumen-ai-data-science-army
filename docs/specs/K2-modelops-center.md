# K2 — ModelOps Kontrol Merkezi

> **Öncelik:** P0 · **Faz:** 1 · **Kapsam:** ModelOps kapalı döngü kokpit

## 1. Amaç & Kullanıcı Hikâyeleri

ModelOps kapalı döngü kokpit: registry, detay sekmeleri, retrain policy, champion-challenger ekranları.

**Kabul senaryoları:**

1. Registry görünümü, model detay sekmeleri.
2. G2 Retrain Policy Editor + F2 Champion-Challenger burada.
3. Drift/perf trend + lineage görselleştirmesi.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/k2_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "modelops.render",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /modelops`
- `GET /modelops/{id}`
- `GET /modelops`

**Veri modeli:**
- `k2_runs (run_id, status, params_json, result_json, created_at)`
- `k2_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** ModelOps ekranı (kapalı döngü kokpit)

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- K1 (designer for new workflows)
- G1/G2 (drift/retrain)
- F2 (champion-challenger)
- `react-flow`
- `echarts`

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
- İlgili node tipi `modelops.render` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
