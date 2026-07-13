# E8 — Graph ML

> **Öncelik:** P3 · **Faz:** 4 · **Kapsam:** topluluk tespiti + node embedding

## 1. Amaç & Kullanıcı Hikâyeleri

Topluluk tespiti (Louvain), merkezilik (betweenness/eigenvector), node embedding (node2vec/GraphSAGE).

**Kabul senaryoları:**

1. Topluluk tespiti (Louvain) + merkezilik metrikleri.
2. Node embedding (node2vec, GraphSAGE) + downstream task.
3. İnteraktif ağ görselleştirmesi.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/e8_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.train.graph",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /train/graph`
- `GET /train/graph/{id}`
- `GET /train/graph`

**Veri modeli:**
- `e8_runs (run_id, status, params_json, result_json, created_at)`
- `e8_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Designer'da graph node + graf görselleştirme

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- B1 (profiling)
- I2 (graph schema)
- K3 (network viz)
- `networkx`
- `stellargraph`

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
- İlgili node tipi `model.train.graph` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
