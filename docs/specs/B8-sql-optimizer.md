# B8 — SQL Optimizer

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** EXPLAIN plan analizi + öneri

## 1. Amaç & Kullanıcı Hikâyeleri

Kullanıcı sorgu yapıştırır → EXPLAIN planı çekilir → indeks önerisi, JOIN sırası değişikliği ve sorgu rewrite önerileri sunulur.

**Kabul senaryoları:**

1. Sorgu yapıştırılır → EXPLAIN planı otomatik çekilir.
2. Öneriler: indeks önerisi, JOIN sırası, rewrite önerisi.
3. Diff görünümü: 'önceki plan' vs 'öneri uygulandıktan sonra plan'.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/b8_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "sql.optimize",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /sql`
- `GET /sql/{id}`
- `GET /sql`

**Veri modeli:**
- `b8_runs (run_id, status, params_json, result_json, created_at)`
- `b8_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Sorgu parse edilemedi → 400.

## 3. UI Tasarımı

**Konum:** Sorgu editörü (yeni QueryPanel.tsx) + plan diff görünümü

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- I2 (catalog query examples)
- B7 (data source)
- `sqlfluff`
- `sqlalchemy`

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
- İlgili node tipi `sql.optimize` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
