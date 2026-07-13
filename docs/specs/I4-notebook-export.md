# I4 — Notebook Export

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** run → jupyter notebook

## 1. Amaç & Kullanıcı Hikâyeleri

Run'ı çalıştırılabilir Jupyter notebook'a paketler.

**Kabul senaryoları:**

1. Run → çalıştırılabilir Jupyter notebook.
2. Agent kodları zaten mevcut; paketleme basit.
3. Run detayında 'Notebook indir' butonu.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/i4_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "run.export.notebook",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /runs/{run_id}/notebook`
- `GET /runs/{run_id}/notebook/{id}`
- `GET /runs/{run_id}/notebook`

**Veri modeli:**
- `i4_runs (run_id, status, params_json, result_json, created_at)`
- `i4_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Run detayında 'Notebook indir' butonu

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- A1/F2 (run artifacts)
- I3 (experiment exports)
- `papermill`
- `nbformat`

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
- İlgili node tipi `run.export.notebook` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
