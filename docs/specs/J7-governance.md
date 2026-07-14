# J7 — Governance Katmanı

## 1. Amaç & Kullanıcı Hikâyeleri

**Amaç:** Model/pipeline'ların üretime alınmasını denetlenebilir kılmak: risk sınıflandırması, çok adımlı onay iş akışları (imza zinciri), üretime alma checklist'i ve denetim raporu. Mevcut HITL onay mekanizmasının kurumsal governance'a genişletilmesi.

**Kullanıcı hikâyeleri:**
- Bir risk sorumlusu olarak, her modele risk sınıfı (düşük/orta/yüksek) atamak ve yüksek riskte 2 kişilik onay zorunluluğu tanımlamak istiyorum.
- Bir DS olarak, prod promotion öncesi checklist'in (model card var mı, fairness pass mı, drift izleme açık mı) hangi maddelerinin eksik olduğunu görmek istiyorum.
- Bir denetçi olarak, "bu model üretime nasıl geldi" sorusuna imza zinciri timeline'ı ve PDF denetim raporuyla cevap almak istiyorum.

**Kabul:** Yüksek riskli model, checklist tamamlanmadan ve 2 onay toplanmadan `prod` stage'ine geçemez; her karar audit log'a düşer.

## 2. Backend Tasarımı

**Servis:**
- `apps/platform-api-app/platform_api/services/governance_service.py` — risk sınıfı CRUD, onay politikaları, checklist değerlendirme motoru (kural: `check_id → evaluator fonksiyonu`), denetim raporu derleme.
- `hitl/escalation_manager.py` genişletmesi: tek onay yerine **onay zinciri** (sıralı/paralel N imza, rol kısıtı); `services/hitl_service.py`'ye `approval_chain` desteği.
- Tüm kararlar `services/audit_service.py` üzerinden loglanır (mevcut).

**Node tipi yok** (governance pipeline node'u değil, promotion/deploy aksiyonlarına takılan kapıdır). G5 promotion isteği governance politikasına yönlenir.

Checklist tanımı örneği:

```json
{
  "policy_id": "prod-promotion-high-risk",
  "applies_to": {"stage_target": "prod", "risk_class": "high"},
  "checks": [
    {"id": "model_card_exists", "source": "F4", "required": true},
    {"id": "fairness_pass", "source": "J6", "required": true},
    {"id": "drift_monitoring_enabled", "source": "G1", "required": true},
    {"id": "eval_above_baseline", "source": "F2", "required": true}
  ],
  "approvals": {"count": 2, "roles": ["ml_lead", "risk_officer"], "mode": "sequential"}
}
```

**API endpoint'leri:**
- `GET/PUT /api/governance/policies` · `GET /api/governance/policies/{id}`
- `PUT /api/models/{id}/risk-class` — `{risk_class, justification}`
- `GET /api/models/{id}/governance/checklist` — madde başına pass/fail + kanıt linki
- `POST /api/governance/requests` — promotion/deploy onay isteği aç → onay zinciri başlar
- `POST /api/governance/requests/{id}/decision` — `{decision: approve|reject, comment}` (imza)
- `GET /api/models/{id}/governance/audit-report?format=pdf|json`

**Veri modeli (migration):** `governance_policies` (id, definition JSON, version), `model_risk_classes` (model_id, risk_class, justification, assigned_by), `governance_requests` (id, model_id, action, policy_id, status), `governance_signatures` (request_id, order, approver_id, role, decision, comment, signed_at).

**Hata durumları:** checklist evaluator kaynağı yok (ör. J6 raporu üretilmemiş) → madde `fail` + "kanıt eksik" nedeni; onaycı kendi isteğini onaylayamaz → 403; politika versiyonu istek açıkken değişirse istek eski versiyonla tamamlanır; imza sırası ihlali → 409.

## 3. UI Tasarımı

**Bileşenler:**
- `HITLApproval.tsx` genişlemesi: onay kartında **risk rozeti** (renk kodlu), checklist accordion'u (madde + pass/fail ikonu + kanıta git linki), **imza zinciri timeline'ı** (kim, ne zaman, yorum; bekleyen adım vurgulu).
- `GovernancePolicies.tsx` — politika listesi + JSON-form editörü (check ekle/çıkar, onay sayısı/rol).
- `RiskClassBadge.tsx` — registry ve model detayında ortak rozet (K3 StatusBadge varyantı).
- `AuditReportButton.tsx` — model detayında "Denetim raporu indir (PDF)".

**Akış:** DS "Promote to prod" der (K2/G5) → governance isteği açılır → onaycılara bildirim (`notification_router.py`) → onaycı HITLApproval'da checklist'i inceler → imzalar → zincir tamamlanınca promotion otomatik yürür; red → gerekçeli geri dönüş.

**Durumlar:** loading: checklist skeleton; empty: "Bu model için politika tanımlı değil — varsayılan uygulanıyor" bilgisi; error: evaluator hatasında madde yanında "yeniden değerlendir" butonu.

**Entegrasyon:** K2 registry'de risk rozeti kolonu; G5 promotion akışı governance kapısından geçer; J12 lineage düğümüne "onay geçmişi" bağlantısı.

## 4. Bağımlılıklar
- Mevcut: `hitl/` modülü, `services/hitl_service.py`, `services/audit_service.py`, `HITLApproval.tsx`, workflow versiyonlama/ETag deseni (`routes/workflows.py`).
- Spec'ler: G5 (promotion), F4/J6/G1/F2 (checklist kanıt kaynakları), K2, .
- PDF üretimi: mevcut rapor export altyapısı (C5 ile ortak).
## 5. Kapsam Dışı

- Harici GRC sistem entegrasyonu (ServiceNow vb.), yasal uyum şablonları (EU AI Act formu), veri erişim yetkilendirmesi/RBAC'ın kendisi (platform genel auth'unun işi), otomatik risk sınıfı tahmini.

## 6. Test & Definition of Done

- Birim: checklist motoru (eksik kanıt → fail), imza sırası kuralı, self-approval engeli, politika versiyon sabitleme.
- E2E: yüksek riskli model promotion isteği → 1. onay → 2. onay → stage değişir; red senaryosu → stage değişmez, audit log tam.
- DoD: imza zinciri timeline UI'da doğru sırayla görünüyor; PDF denetim raporu checklist + imzalar + lineage özetini içeriyor; tüm kararlar audit_service kaydında.
