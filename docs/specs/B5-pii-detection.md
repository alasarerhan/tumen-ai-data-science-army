# B5 — PII Detection & Anonymization

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** KVKK/GDPR sorumluluğu taşıyan data engineer, veri paylaşan analyst, governance sahibi.

**Neden:** Kişisel veri içeren kolonlar (TCKN, telefon, e-posta, ad-soyad, adres, IBAN) fark edilmeden modele/rapora sızabiliyor. Otomatik tespit + kolon bazlı anonimleştirme stratejisi ve katalogda görünür PII rozeti gerekiyor.

**Kabul senaryoları:**
1. Kullanıcı bir dataset'te PII taraması başlatır; sistem regex + NER (Presidio) ile kolonları tarar ve her kolon için PII tipi + güven skoru + örnek eşleşme (maskeli) listeler.
2. Kullanıcı kolon başına strateji seçer (maskele/hash/tokenize/sil/dokunma) ve `pii.anonymize` node'u pipeline'a eklenir; çıktı dataset'inde seçilen stratejiler uygulanmış olur.
3. TCKN kolonu tespit edildiğinde varsayılan strateji "hash" olarak önerilir ve katalogda kırmızı PII rozeti görünür.
4. Tarama sonucu onaylanmadan bu dataset'i kullanan `report.generate`/`artifact.export` node'ları çalıştırılırsa uyarı üretilir (B2 kalite kapısıyla engellenebilir).

## 2. Backend Tasarımı

**Agent:** `ai_data_science_team/agents/pii_agent.py` — `PIIDetectionAgent`. Motor: `presidio-analyzer` (spaCy NER) + Türkiye'ye özel custom recognizer'lar (TCKN checksum, TR telefon, TR IBAN, TR plaka). Kolon bazlı örnekleme (varsayılan 1000 satır) → hit oranı ≥ %30 ise kolon PII adayı. Anonimleştirme: `presidio-anonymizer` + kolon-seviyesi stratejiler.

**Node tipleri:** `pii.scan` ve `pii.anonymize`.

I/O sözleşmesi:
```json
{
  "type": "pii.anonymize",
  "inputs": {"dataset_ref": "artifact://run/77/raw.parquet", "scan_report_ref": "artifact://run/77/pii_scan.json"},
  "config": {
    "strategies": [
      {"column": "tckn", "pii_type": "TR_ID_NUMBER", "strategy": "hash", "params": {"salt_ref": "secret://pii_salt"}},
      {"column": "email", "pii_type": "EMAIL_ADDRESS", "strategy": "mask", "params": {"keep_domain": true}},
      {"column": "customer_name", "pii_type": "PERSON", "strategy": "tokenize"}
    ],
    "fail_on_unhandled_pii": true
  },
  "outputs": {
    "anonymized_dataset_ref": "artifact://run/77/anon.parquet",
    "audit": {"columns_processed": 3, "rows": 250000, "unhandled_pii": []}
  }
}
```

**API endpoint'leri** (`routes/pii.py`):
- `POST /api/pii/scans` — `{data_source_id | dataset_ref, sample_rows}` → async tarama
- `GET /api/pii/scans/{id}` — sonuç: kolon listesi, pii_type, confidence, hit_ratio
- `PUT /api/pii/scans/{id}/strategies` — kolon bazlı strateji kaydet/onayla
- `GET /api/pii/datasets/{dataset_id}/status` — katalog rozeti için özet

**Veri modeli:** `pii_scans` (id, tenant_id, dataset_ref, status, findings_json, created_at), `pii_column_policies` (dataset_id, column, pii_type, strategy, params_json, approved_by). Tokenizasyon eşleme tablosu şifreli ayrı store'da (`secret_store_service` üzerinden anahtar).

**Hata durumları:** spaCy modeli yüklenemedi → yalnız regex modu + uyarı; `fail_on_unhandled_pii=true` iken stratejisiz PII kolonu → `UNHANDLED_PII` node fail; salt secret eksik → `SECRET_MISSING`; tarama örneklemi boş → `EMPTY_SAMPLE` uyarısı, sonuç "belirsiz".

## 3. UI Tasarımı

**Ekran/bileşenler:** DataSources / dataset detayına "PII" sekmesi — **PIIFindingsTable**: kolon | tespit tipi | güven | hit oranı | maskeli örnek | strateji dropdown'u | önizleme. Katalog (I2) kolon kartlarında renkli PII rozeti (kırmızı=stratejisiz, yeşil=anonimleştirme politikalı).

**Etkileşim akışı:**
1. "PII Tara" → progress (örnekleme→regex→NER) → bulgular tablosu, riskli tipler üstte.
2. Her kolon için strateji seç; sağ panelde canlı önizleme (5 örnek satır: önce/sonra).
3. "Politikayı Onayla" → policy kaydı + rozet güncellenir; "Pipeline'a anonimleştirme ekle" butonu Designer'da `pii.anonymize` node'u üretir.

**Durumlar:** loading — tarama adım stepper'ı; empty — "PII bulunamadı" yeşil onay kartı; error — motor bazlı mesaj ("NER modeli yüklenemedi, yalnız regex sonuçları gösteriliyor" gibi kısmi-sonuç davranışı).

**Entegrasyon:** Reports ekranında PII'lı kaynak kullanan raporlarda uyarı banner'ı; WorkflowDesigner'da PII rozetli dataset'e bağlanan export node'unda inline uyarı.

## 4. Bağımlılıklar

- **Spec:** B1 (profil sırasında PII aday işaretleme aynı tarayıcıyı kullanır), I2 (rozet gösterimi), B2 (kalite kapısı entegrasyonu), J7 (politika onay zinciri).
- **Kütüphaneler:** `presidio-analyzer`, `presidio-anonymizer`, `spacy` (+ `xx_ent_wiki_sm` veya TR modeli), `hashlib`/`hmac`.
- **Kod entegrasyonu:** `apps/platform-api-app/platform_api/services/workflow_node_catalog_service.py`, `workflow_node_executor_service.py`, `services/secret_store_service.py` (salt/token anahtarı), `services/data_source_service.py` (örnekleme), `services/audit_service.py` (kim hangi politikayı onayladı), `frontend/src/app/screens/DataSources.tsx`.

## 5. Kapsam Dışı

- Serbest metin doküman/e-posta gövdesi redaksiyonu (yalnız tablo kolonları; metin kolonlarında hücre içi eşleşme maskelenir ama doküman işleme yok).
- Differential privacy / k-anonymity garantileri (B6 sentetik veriyle ilişkili ileri konu).
- DSAR (veri sahibi talebi) iş akışları ve yasal raporlama.
- Görüntü içi PII (yüz, plaka fotoğrafı).

## 6. Test & Definition of Done

**Senaryolar:**
- Birim: TCKN checksum recognizer geçerli/geçersiz numaraları ayırır; TR telefon (+90/0 formatları) ve IBAN yakalanır; e-posta/isim NER'i çalışır.
- Birim: hash stratejisi deterministik+saltlı; tokenize geri çözülebilir (yetkili endpoint ile) ve eşleme şifreli saklanır.
- Entegrasyon: `fail_on_unhandled_pii` senaryosunda node fail + anlaşılır hata artifact'ı.
- E2E: tara → strateji seç → onayla → `pii.anonymize` node'lu run → çıktı dataset'inde ham PII kalmadığı otomatik doğrulama taramasıyla teyit edilir; katalog rozeti yeşile döner.

**DoD checklist:**
- [ ] `pii.scan` / `pii.anonymize` katalog + validator kayıtları
- [ ] TR custom recognizer seti test fikstürüyle ≥ %95 precision
- [ ] `pii_scans` / `pii_column_policies` migration'ları
- [ ] PIIFindingsTable + rozetler, üç durum tanımlı
- [ ] Audit log: tarama, politika onayı, anonimleştirme run'ları izlenebilir
- [ ] Token eşleme tablosuna erişim yetki testi
