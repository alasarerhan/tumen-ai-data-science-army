# I3 — Experiment Tracking / Leaderboard

> **Öncelik:** P1 · **Faz:** 2 · **Kapsam:** MLflow leaderboard UI

## 1. Amaç & Kullanıcı Hikâyeleri

MLflow verisini frontend'e taşır; sıralanabilir leaderboard + çoklu-run karşılaştırma.

**Kabul senaryoları:**

1. MLflow verisini frontend'e taşır.
2. Sıralanabilir leaderboard: metrik kolonları, engine rozeti, süre/maliyet.
3. 2-4 run karşılaştırma: radar chart, hiperparametre diff.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/i3_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "experiment.leaderboard",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /experiments`
- `GET /experiments/{id}`
- `GET /experiments`

**Veri modeli:**
- `i3_runs (run_id, status, params_json, result_json, created_at)`
- `i3_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Yeni 'Experiments' ekranı + leaderboard tablosu

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- F1 (eval)
- E2 (HPO)
- G4 (predict artifacts)
- `mlflow`

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
- İlgili node tipi `experiment.leaderboard` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
