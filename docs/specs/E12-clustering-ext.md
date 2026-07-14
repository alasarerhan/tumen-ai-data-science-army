# E12 — Clustering genişletmesi

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** LLM kümeleri isimlendirme

## 1. Amaç & Kullanıcı Hikâyeleri

K-means/DBSCAN/Hierarchical; LLM ile küme profilleme ve iş anlamı isimlendirme.

**Kabul senaryoları:**

1. K-means/DBSCAN/Hierarchical clustering.
2. LLM her kümeye iş anlamı veren isim ve açıklama önerir.
3. Segmentasyon şablonu: kümeleri pazarlama segmenti olarak etiketleme.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/e12_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "model.train.cluster",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /train/cluster`
- `GET /train/cluster/{id}`
- `GET /train/cluster`

**Veri modeli:**
- `e12_runs (run_id, status, params_json, result_json, created_at)`
- `e12_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Designer'da cluster node + küme kartları

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar
- F1 (evaluation)
- I2 (catalog)
- (visual recipes)
- `sklearn`
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
- İlgili node tipi `model.train.cluster` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
