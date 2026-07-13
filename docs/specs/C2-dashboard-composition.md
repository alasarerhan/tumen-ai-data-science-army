# C2 — Dashboard Kompozisyonu

> **Öncelik:** P2 · **Faz:** 3 · **Kapsam:** çoklu grafik dashboard'ı

## 1. Amaç & Kullanıcı Hikâyeleri

Birden çok grafik artifact'ını tek dashboard'a bağlar; sürükle-bırak düzenleyici, paylaşılabilir public URL.

**Kabul senaryoları:**

1. Birden çok grafik artifact'ı tek dashboard'ta toplanır.
2. Sürükle-bırak grid düzenleyici.
3. Paylaşılabilir public URL + snapshot.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/c2_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "report.compose",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /dashboards`
- `GET /dashboards/{id}`
- `GET /dashboards`

**Veri modeli:**
- `c2_runs (run_id, status, params_json, result_json, created_at)`
- `c2_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Reports ekranında 'New Dashboard' butonu

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- C3 (KPI cards)
- E10 (interactive)
- K3 (design system)
- `react-grid-layout`

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
- İlgili node tipi `report.compose` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
