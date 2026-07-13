# G3 — Gerçek Model Serving / Deploy (P1)

## 1. Amaç & Kullanıcı Hikâyeleri

Bugün `agents/model_serving_agent.py` yalnız **in-process** inference yapar (`load_model` / `run_inference` / `health_check`); ModelOps ekranındaki "deploy" gerçek bir deployment üretmez. Bu spec, kayıtlı bir model versiyonundan gerçek servis edilebilir çıktılar üretir: FastAPI endpoint scaffold'u, Docker image ve BentoML servisi + tek tık rollback.

- **ML engineer olarak**, Production'a promote edilmiş modeli tek tıkla `/predict` REST endpoint'i olarak ayağa kaldırmak istiyorum.
- **Platform sahibi olarak**, hatalı deployment'ı önceki versiyona confirm dialog'lu tek tıkla geri almak istiyorum.
- **Kabul senaryosu 1:** Deploy sihirbazından "endpoint" hedefi seçilir → lokal FastAPI süreci ayağa kalkar, `POST /predict` örnek payload ile 200 döner, ModelOps'ta deployment kartı RUNNING görünür.
- **Kabul senaryosu 2:** "Container" hedefi seçilir → Dockerfile + bentofile üretilir, `docker build` başarılıysa image tag'i kaydedilir.
- **Kabul senaryosu 3:** Rollback → trafik önceki versiyona döner, timeline'a rollback olayı işlenir.

## 2. Backend Tasarımı

### Agent / sınıf
- **Yeni:** `ai_data_science_team/agents/deployment_agent.py` — `DeploymentAgent`; scaffold üretimi (Jinja2 şablonları `templates/serving/` altında: `fastapi_app.py.j2`, `Dockerfile.j2`, `bentofile.yaml.j2`), süreç yönetimi (uvicorn subprocess), BentoML paketleme (`bentoml.sklearn.save_model` + `bentoml build`).
- **Yeni servis:** `services/deployment_service.py` — deployment CRUD, süreç/port havuzu (8100-8199), health polling (mevcut `health_check` yeniden kullanılır), rollback mantığı.
- `modelops_service.py` deployment durumunu model versiyonuna bağlar.

### Node tipi + I/O sözleşmesi
Node tipi: `model.deploy` (pipeline sonunda otomatik deploy için; UI sihirbazı da aynı API'yi çağırır).

```json
{
  "type": "model.deploy",
  "config": {
    "model_id": "churn_xgb",
    "version": "4",
    "target": "endpoint",            
    "port": null,
    "replace_active": true,
    "resources": { "workers": 1 }
  },
  "outputs": {
    "deployment": {
      "deployment_id": "dep_01H...",
      "target": "endpoint",
      "url": "http://localhost:8101/predict",
      "artifacts": ["serving/app.py", "Dockerfile", "bentofile.yaml"],
      "status": "running",
      "previous_deployment_id": "dep_01G..."
    }
  }
}
```
`target ∈ {endpoint, container, bentoml}`.

### API endpoint'leri
- `POST   /api/deployments` — deploy başlat (async; job döner).
- `GET    /api/deployments?model_id=` — liste; `GET /api/deployments/{id}` — detay + health.
- `POST   /api/deployments/{id}/rollback` — önceki versiyona dön (body: `confirm: true`).
- `DELETE /api/deployments/{id}` — durdur/kaldır.
- `GET    /api/deployments/{id}/logs` — uvicorn/build logları (son N satır).

### Veri modeli / migration
`deployments` tablosu: `id, model_id, model_version, target, status(pending|building|running|failed|stopped|rolled_back), url, port, image_tag, scaffold_path, previous_deployment_id, created_by, created_at, stopped_at`. + `deployment_events` (timeline: deploy/health_fail/rollback/stop, HITL onay referansı).

### Hata durumları
- `PORT_EXHAUSTED` (409), `BUILD_FAILED` (422; docker/bento build log özeti), `HEALTH_CHECK_FAILED` (deploy sonrası 3 deneme → status=failed, otomatik eski deployment aktif kalır), `DOCKER_UNAVAILABLE` (424; container hedefi seçilemez, UI'da disable), `ROLLBACK_TARGET_MISSING` (409). Production'a deploy HITL `notification_router` üzerinden onaya düşer (J7 ile uyumlu).

## 3. UI Tasarımı

### Bileşenler & akış
- **Deploy sihirbazı** (ModelOps model detayından "Deploy"): Adım 1 versiyon seçimi (stage rozetli) → Adım 2 hedef kartları (Endpoint / Container / BentoML; Docker yoksa Container kartı disabled + tooltip) → Adım 3 özet + üretilecek dosya önizlemesi (CodeBlock) → Başlat.
- **Deployment kartları** (K2 "Deployment'lar" sekmesi): durum StatusBadge, URL kopyala, health sinyali (yeşil/kırmızı nokta + son kontrol zamanı), "Test isteği gönder" (örnek payload formu → yanıt JSON), log çekmecesi.
- **Rollback:** kart üzerinde tek buton → confirm dialog ("v4 → v3'e dönülecek, aktif endpoint yeniden başlatılır") → timeline'a olay.

### Loading / empty / error
- Loading: build sırasında adımlı progress (scaffold → build → start → health) — K3 agent şeffaflık standardı.
- Empty: hiç deployment yoksa "Bu model henüz deploy edilmedi" + Deploy CTA.
- Error: BUILD_FAILED'da log özeti inline + "logları aç"; HEALTH_CHECK_FAILED'da "eski sürüm aktif kaldı" bilgi banner'ı.

### Mevcut ekran entegrasyonu
`ModelOps.tsx` model detayına "Deployment'lar" sekmesi; header bildirim çanına deploy/rollback olayları (G7 ile).

## 4. Bağımlılıklar
- Mevcut kod: `agents/model_serving_agent.py` (load/health yeniden kullanımı), `modelops_service.py`, HITL `notification_router`, `services/secret_store_service.py` (registry credentials ileride).
- Spec'ler: G5 (stage bilgisi), G4 (aynı model çözüm katmanı), K2, J11 (canary — üstüne kurulur).
- Kütüphaneler: fastapi, uvicorn, jinja2, **bentoml**, docker SDK (`docker` pypi, opsiyonel).

## 5. Kapsam Dışı
- K8s/uzak compute'a deploy, autoscaling, canary/shadow trafik bölme (J11), API gateway/auth katmanı, model endpoint'inin internet'e açılması, GPU serving.

## 6. Test & Definition of Done
- **Birim:** scaffold şablon render'ı (üç hedef), port havuzu, rollback durum makinesi, health polling.
- **Entegrasyon:** sklearn modeliyle endpoint deploy → gerçek HTTP `POST /predict` → 200 + doğru şekilli yanıt; stop; rollback zinciri (v3→v4→rollback→v3 aktif).
- **E2E (UI):** sihirbaz akışı, test isteği gönderme, confirm'li rollback, Docker'sız ortamda container kartının disabled olması.
- **DoD:** üç hedef de çalışır (Docker yoksa graceful degrade), deployments migration'ı uygulanmış, rollback timeline'ı görünür, hata kodları testli.
