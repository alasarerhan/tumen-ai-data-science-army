# F6 — LLM-as-Judge

> **Öncelik:** P1 · **Faz:** 2 · **Kapsam:** agent çıktı kalite skorlama

## 1. Amaç & Kullanıcı Hikâyeleri

Agent çıktılarını kalite açısından skorlayan 'yargıç LLM'; düşük skorlu çıktı kullanıcıya ulaşmadan revize edilir.

**Kabul senaryoları:**

1. Agent çıktıları skorlanır: doğruluk, sadakat, kod kalitesi.
2. Düşük skorlu çıktı revize edilir.
3. Agents ekranında 'kalite skoru' sekmesi.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/f6_agent.py` — `langgraph` react-agent; deterministic çekirdek aynı paketin `tools/` altında.

**Node tipi:**
```json
{
  "type": "agent.judge",
  "config": {
    /* spec-specific configuration */
  }
}
```

**API endpoint'leri:**
- `POST /judge`
- `GET /judge/{id}`
- `GET /judge`

**Veri modeli:**
- `f6_runs (run_id, status, params_json, result_json, created_at)`
- `f6_artifacts (artifact_ref, run_id, kind, payload)`

**Hata durumları:**
- Bağlantı veya kimlik bilgisi hatası → 401/403 + retry/log
- Veri format uyumsuzluğu → 422 + kolon-bazlı mesaj
- Geçersiz config → 400.

## 3. UI Tasarımı

**Konum:** Agents ekranında 'Quality' sekmesi

**Akış:**
1. Konfig (form / dataset seçici / parametreler) adımı
2. Çalıştır / önizle (loading + stepper)
3. Sonuç görünümü (kart / tablo / graf)
4. Onay / kaydet / paylaş

**Durumlar:** yükleniyor (skeleton + stepper) · boş (CTA'lı empty state) · hata (eyleme dönük mesaj).

**Entegrasyon:** K3 tasarım sistemi bileşenleri kullanılır (DataTable / MetricCard / StatusBadge / ChartContainer / DiffView).

## 4. Bağımlılıklar

- Universal — observes every agent.
- J6 (responsible AI)
- `anthropic / openai judge model`

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
- İlgili node tipi `agent.judge` platform-api-app'te handler'a bağlı.
- UI bileşeni screens/<Name>.tsx (veya mevcut ekrana sekme) olarak eklenmiş.
- Reaktif agent tool'ları ile LLM-driven rota çalışıyor.
- PLATFORM_SPEC.md'deki durum güncellenir (✍️ → 🚧 → ✅).
