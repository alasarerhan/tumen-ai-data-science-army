# B7 — Data Ingestion / ELT

> **Öncelik:** P1 · **Faz:** 2 · **Kapsam:** watermark'lı artımlı ingest

## 1. Amaç & Kullanıcı Hikâyeleri

Planlanmış veya artımlılık anahtarı olan veri kaynaklarından periyodik olarak çekim yapar. Watermark tabanlı incremental ingestion, dosya-drop tetiklemeli akışı ve audit trail'i destekler.

**Kabul senaryoları:**

1. Kayıtlı kaynak + hedef + artımlılık anahtarı + takvim belirlenir; ingest job kayıt edilir.
2. Watermark'lı incremental yükleme: yeni/silinen satırlar otomatik takip edilir.
3. Çalışma geçmişi tablosu: durum, satır sayısı, hata varsa neden.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/b7_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "data.ingest",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /ingest`
- `GET /ingest/{id}`
- `GET /ingest`

**Veri modeli:**
- `b7_runs (run_id, status, params_json, result_json, created_at)`
- `b7_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Watermark kolonu bulunamadı → 422.

## 3. UI Tasarımı

**Konum:** Data Sources ekranında ingest job listesi + scheduler form

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar
- B1 (profiling on ingest)
- (event triggers)
- I2 (catalog registration)
- `sqlalchemy`
- `pyarrow`
- `pandas`
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
- İlgili node tipi `data.ingest` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
