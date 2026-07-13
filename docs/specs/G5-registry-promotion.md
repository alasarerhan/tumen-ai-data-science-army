# G5 — Registry Promotion (P1)

## 1. Amaç & Kullanıcı Hikâyeleri

Model versiyonlarının **dev → staging → prod** yaşam döngüsü yönetimi: stage geçişleri, imza/şema doğrulama, onay zinciri ve MLflow Model Registry ile senkron. Bugün `modelops_service.py` kayıt tutar ama stage kavramı ve promotion akışı yoktur.

- **ML engineer olarak**, F2 Champion-Challenger sonucu "promote" dediğimde model staging'e geçsin, prod'a geçiş onaydan sonra olsun istiyorum.
- **Governance sahibi olarak**, prod'daki her modelin kim tarafından, hangi gerekçeyle, hangi doğrulamalardan geçerek promote edildiğini timeline'da görmek istiyorum.
- **Kabul senaryosu 1:** `dev→staging` geçişinde imza (feature şeması + çıkış tipi) doğrulanır; uyumsuzsa promotion reddedilir.
- **Kabul senaryosu 2:** `staging→prod` HITL onayı gerektirir; onaylanınca eski prod versiyonu otomatik `archived` olur ve MLflow Registry'de alias güncellenir.
- **Kabul senaryosu 3:** G4 `stage: "Production"` ile skorlama yapan pipeline, promotion sonrası bir sonraki run'da otomatik yeni versiyonu kullanır.

## 2. Backend Tasarımı

### Agent / sınıf
- **Yeni servis:** `services/registry_promotion_service.py` — stage durum makinesi (`dev → staging → production → archived`; geri alma: `demote`), imza doğrulama (`mlflow.models.get_model_info` signature vs kayıtlı dataset şeması), MLflow senkron (`MlflowClient.set_registered_model_alias` / `transition_model_version_stage`).
- `modelops_service.py` genişletmesi: `get_version_by_stage(model_id, stage)` (G3/G4 tüketir).

### Node tipi + I/O sözleşmesi
Node tipi: `model.promote` (G2 auto-retraining zincirinin son halkası).

```json
{
  "type": "model.promote",
  "config": {
    "model_id": "churn_xgb",
    "version": "5",
    "to_stage": "staging",
    "require_approval": true,
    "validations": ["signature", "schema", "min_metrics"],
    "min_metrics": { "auc": 0.82 },
    "reason": "F2 challenger kazandı (DeLong p<0.05)"
  },
  "outputs": {
    "promotion": {
      "promotion_id": "prm_01H...",
      "status": "pending_approval",
      "checks": [{ "name": "signature", "passed": true }, { "name": "min_metrics", "passed": true }],
      "approved_by": null
    }
  }
}
```

### API endpoint'leri
- `POST /api/models/{model_id}/versions/{v}/promote` — body: `to_stage, reason, require_approval`.
- `POST /api/promotions/{id}/approve` · `POST /api/promotions/{id}/reject` (HITL; onaycı ≠ talep eden kuralı).
- `POST /api/models/{model_id}/versions/{v}/demote` — archived/staging'e indirme (confirm zorunlu).
- `GET  /api/models/{model_id}/promotions` — timeline verisi.

### Veri modeli / migration
- `model_versions` tablosuna `stage` kolonu (default `dev`) + `mlflow_alias`.
- **Yeni:** `promotions` tablosu: `id, model_id, version, from_stage, to_stage, status(pending_checks|pending_approval|approved|rejected|failed), checks_json, reason, requested_by, approved_by, created_at, resolved_at`.

### Hata durumları
- `SIGNATURE_MISMATCH` (422; beklenen/gelen imza diff'i), `METRIC_BELOW_THRESHOLD` (422), `INVALID_TRANSITION` (409; ör. dev→prod atlaması policy ile kapalıysa), `SELF_APPROVAL_FORBIDDEN` (403), `MLFLOW_SYNC_FAILED` (502; lokal durum güncellenir, senkron retry kuyruğuna alınır ve UI'da "senkron bekliyor" rozeti). Prod promotion'da eski versiyonun archive edilmesi transaction içinde yapılır.

## 3. UI Tasarımı

### Bileşenler
- **Stage rozetleri** (K2 registry görünümü): `dev` gri · `staging` mavi · `production` yeşil · `archived` soluk; her satırda mevcut stage + bekleyen promotion işareti.
- **Promotion timeline'ı** (model detayı): dikey zaman çizelgesi — her olayda from→to, gerekçe, check sonuçları (✓/✗ chip'leri), talep eden/onaylayan avatarları.
- **Promote dialog'u:** hedef stage seçimi, gerekçe (zorunlu), otomatik check'lerin canlı sonucu (stepper: imza → şema → metrik) → "Onaya gönder".
- **Onay kuyruğu:** mevcut HITLApproval ekranına `promotion` tipi kart (model card özeti + check tablosu + Onayla/Reddet).

### Akış, loading/empty/error
- Check'ler çalışırken adımlı progress; başarısız check kırmızı satır + detay (imza diff'i CodeBlock).
- Empty: promotion geçmişi yoksa "Bu model hiç promote edilmedi".
- Error: `MLFLOW_SYNC_FAILED` sarı banner "Yerel kayıt güncellendi, MLflow senkronu bekleniyor" + yeniden dene butonu.

### Mevcut ekran entegrasyonu
`ModelOps.tsx` registry tablosu stage kolonu kazanır; F2 Champion-Challenger karar barındaki **Promote** butonu bu API'yi çağırır; G2 policy editor "onaylı promotion" aksiyonunu bu node ile kurar.

## 4. Bağımlılıklar
- Mevcut kod: `modelops_service.py`, HITL `notification_router`, MLflow tracking altyapısı.
- Spec'ler: F2 (promotion tetikleyicisi), G2 (otomatik zincir), G3/G4 (stage tüketicileri), J7 (governance genişletmesi), K2.
- Kütüphaneler: mlflow (`MlflowClient`), pydantic (check şemaları).

## 5. Kapsam Dışı
- Çoklu onay zinciri/rol matrisi (J7), model imzalama/kriptografik attestation, çoklu registry (yalnız MLflow), otomatik rollback-on-degradation (G7+J11).

## 6. Test & Definition of Done
- **Birim:** durum makinesi geçiş matrisi, imza karşılaştırma, min_metrics değerlendirme, self-approval engeli.
- **Entegrasyon:** promote→approve→MLflow alias güncellemesi (yerel mlflow ile); prod promotion'da eski versiyonun archive olması; G4'ün `stage` çözümünün yeni versiyona dönmesi.
- **E2E (UI):** promote dialog → onay kuyruğu → timeline'da olay; reddedilen promotion'ın stage'i değiştirmemesi.
- **DoD:** migration uygulanmış, tüm geçişler API'den yönetilebilir, timeline UI canlı veriyle çalışır, hata kodları testli.
