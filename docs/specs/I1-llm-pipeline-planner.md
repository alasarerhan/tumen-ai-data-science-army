# I1 — LLM Pipeline Planner + Copilot UI

> Öncelik: P0 · Faz 1 · Vizyonun 1 numaralı maddesi.
> Chat'teki heuristik workflow-design'ın yerini alan, doğal dilden doğrulanmış pipeline planı üreten LLM planner ve çift panelli copilot arayüzü.

## 1. Amaç & Kullanıcı Hikâyeleri

**Sorun:** Bugün `apps/platform-api-app/platform_api/services/chat_service.py` içindeki `_build_workflow_design()` (satır ~505) workflow spec'ini **anahtar kelime eşlemesiyle (heuristik)** üretiyor. Kullanıcı "churn tahmini yap" dediğinde sabit şablonlar dönüyor; parametreler, kolonlar ve adım sırası gerçek niyeti yansıtmıyor. Oysa `multiagents/supervisor_ds_team.py` içinde `WorkflowPlannerAgent` ile gerçek çok adımlı agent zincirleme zaten var — bu güç chat'e taşınmıyor.

**Hedef:** NL → streaming LLM planı → `workflow_chain_validator` doğrulaması → canlı önizleme → konuşarak iteratif revizyon.

**Kullanıcı hikâyeleri:**
- **US-1 (Analist):** "Satış verimden aylık forecast pipeline'ı kur" yazarım; sağ panelde plan node node belirir, eksik parametre (tarih kolonu) sorulur, dropdown'dan seçerim, planı Designer'da açarım.
- **US-2 (DS):** Üretilen plana "outlier temizleme adımı ekle, model olarak LightGBM kullan" derim; plan diff'i renklerle görünür (eklenen yeşil), onaylarım.
- **US-3 (ML Eng):** Planı doğrudan "Çalıştır" ile başlatırım veya "Zamanla" ile cron'a bağlarım; validasyon hatası varsa çalıştırma engellenir ve hata node üzerinde gösterilir.
- **US-4 (Yeni kullanıcı):** Boş chat'te guided starter'dan hedef/veri/sıklık seçerek başlarım; sonra serbest sohbete geçerim.

**Kabul senaryoları:**
1. "müşteri kaybı tahmin et" → geçerli (`validate_workflow_ir_v2` PASS) bir plan ≤15 sn'de streaming olarak canvas'a çizilir.
2. Revizyon isteği sonrası diff doğru renklenir; kabul edilmeden mevcut plan değişmez.
3. Eksik zorunlu parametre varsa plan kartında inline form-widget çıkar; doldurulmadan "Çalıştır" pasiftir.
4. Heuristik `_build_workflow_design` hiçbir chat yolundan çağrılmaz (feature flag ile kaldırılır).

## 2. Backend Tasarımı

### 2.1 Servis / Agent sınıfları

| Bileşen | Dosya | Sorumluluk |
|---|---|---|
| `PipelinePlannerService` | `apps/platform-api-app/platform_api/services/pipeline_planner_service.py` (yeni) | NL → plan orkestrasyonu, streaming, revizyon, validasyon döngüsü |
| `WorkflowPlannerAgent` (mevcut) | `ai_data_science_team/multiagents/supervisor_ds_team.py` | Plan üretimi çekirdeği; chat bağımsız kullanılabilecek şekilde `plan_workflow(nl_request, context) -> WorkflowPlan` arayüzü çıkarılır |
| `PlanRevisionEngine` | aynı yeni servis dosyası içinde sınıf | mevcut plan + revizyon isteği → yeni plan + node-düzeyi diff (`added/removed/changed`) |
| Validasyon (mevcut) | `apps/platform-api-app/platform_api/services/workflow_chain_validator.py` (`inspect_workflow_spec`) + `workflow_ir_service.validate_workflow_ir_v2` | Her üretilen/revize plan yayınlanmadan önce doğrulanır |

**Planlama döngüsü:** LLM plan üretir → validator çalışır → hata varsa hata şeması LLM'e geri beslenir (en fazla 2 otomatik onarım turu) → hâlâ hatalıysa plan `invalid` durumuyla ve hata listesiyle UI'a gönderilir.

### 2.2 I/O sözleşmesi — plan artifact'ı

`{"type":"workflow_design"}` artifact'ı korunur, `v2` şemasına genişletilir (mevcut `WorkflowDesignMessage.tsx` render'ı geriye uyumlu kalır):

```json
{
  "type": "workflow_design",
  "version": 2,
  "plan_id": "plan_8f2c",
  "revision": 3,
  "status": "valid",
  "workflow_spec": {
    "name": "Aylık Satış Forecast",
    "nodes": [
      {"id": "n1", "type": "data.load", "params": {"source_id": "src_sales", "table": "sales"}},
      {"id": "n2", "type": "data.clean", "params": {"strategies": ["drop_duplicates", "impute_median"]}},
      {"id": "n3", "type": "model.train", "params": {"task": "forecast", "date_column": null, "target": "revenue"},
       "missing_params": [{"name": "date_column", "widget": "column_picker", "source_node": "n1"}]}
    ],
    "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}]
  },
  "diff": {"added": ["n2"], "removed": [], "changed": [{"id": "n3", "fields": ["params.engine"]}]},
  "validation": {"passed": false, "errors": [{"node_id": "n3", "code": "MISSING_PARAM", "message": "date_column zorunlu", "fix_widget": "column_picker"}]},
  "planning_steps": [
    {"step": "intent", "label": "Niyet çözümlendi: forecast", "status": "done"},
    {"step": "data_resolution", "label": "Kaynak eşlendi: src_sales", "status": "done"},
    {"step": "plan", "label": "Plan üretiliyor", "status": "running"},
    {"step": "validate", "label": "Doğrulama", "status": "pending"}
  ],
  "actions": ["open_in_designer", "save", "run", "schedule"]
}
```

### 2.3 API endpoint'leri

| Method | Path | Açıklama |
|---|---|---|
| `POST` | `/api/chat/plan` | `{message, session_id, current_plan_id?}` → **SSE stream**: `plan_step` (stepper), `plan_chunk` (node/edge parçaları), `plan_validation`, `plan_done` event'leri |
| `POST` | `/api/plans/{plan_id}/revise` | `{message}` → aynı SSE akışı + `diff` |
| `POST` | `/api/plans/{plan_id}/params` | inline widget'tan gelen parametre değerleri; yeniden validasyon sonucu döner |
| `POST` | `/api/plans/{plan_id}/materialize` | `{action: "save"\|"run"\|"schedule", schedule_expr?}` → workflow kaydı oluşturur; `run` mevcut run API'sine, `schedule` `routes/scheduler.py`'a delege eder |
| `GET` | `/api/plans/{plan_id}` | son revizyon + revizyon geçmişi |

### 2.4 Veri modeli / migration

Yeni tablo `chat_plans` (Alembic migration):
`id (pk)`, `session_id`, `revision (int)`, `spec_json (JSON)`, `diff_json (JSON)`, `validation_json (JSON)`, `status (draft|valid|invalid|materialized)`, `workflow_id (nullable fk)`, `created_at`.
Her revizyon yeni satır → tam revizyon geçmişi ve geri alma.

### 2.5 Hata durumları

| Durum | Davranış |
|---|---|
| LLM timeout / sağlayıcı hatası | `runtime_engine` fallback zinciri (ikincil model); yine olmazsa `plan_error` event'i + "tekrar dene" |
| Validasyon 2 onarım turunda geçmedi | plan `invalid` olarak gösterilir; hatalı node'lar canvas'ta kırmızı, hata paneli açık; Çalıştır/Kaydet pasif |
| LLM'in geçersiz JSON üretmesi | şema-korumalı parse (pydantic) + 1 yeniden deneme; sonra `plan_error` |
| Bilinmeyen node tipi önerisi | validator `UNKNOWN_NODE_TYPE` döner, LLM'e katalogdaki geçerli tip listesiyle geri beslenir |
| Stream kopması | client `GET /api/plans/{plan_id}` ile son durumu çeker (plan sunucuda persist) |

## 3. UI Tasarımı

### 3.1 Çift panel copilot ekranı

`frontend/src/app/components/copilot/CopilotWorkspace.tsx` (yeni) — mevcut `AIWorkspace.tsx`'in chat modunun evrimi:

- **Sol panel — Chat:** mevcut chat bileşenleri; plan mesajları `WorkflowDesignMessage.tsx`'in v2 uyarlaması olan **PlanCard** ile render edilir.
- **Sağ panel — Canlı plan canvas'ı:** `PlanCanvas.tsx` (yeni), ReactFlow; **`WorkflowDesigner.tsx`'in node bileşenleri aynen yeniden kullanılır** (ortak `nodes/` klasörüne çıkarılır). Salt-okunur + parametre widget etkileşimi; streaming sırasında node'lar geldikçe animasyonla eklenir, otomatik layout (dagre/elkjs).

### 3.2 PlanCard aksiyonları

Kart altında dört buton: **Designer'da Aç** (spec'i Designer'a taşır, oradan düzenlenir) · **Kaydet** · **Çalıştır** (validasyon PASS şartı) · **Zamanla** (NL→cron `ScheduleParser` destekli mini zamanlama popover'ı).

### 3.3 Revizyon diff renklendirmesi

Yeni revizyon geldiğinde canvas overlay: **eklenen node/edge yeşil**, **silinen kırmızı (soluk, üstü çizili)**, **parametresi değişen sarı** (hover'da alan bazlı eski→yeni tooltip). "Diff'i kapat" ile normal görünüme dönülür; diff renk seti renk-körü güvenli (K3).

### 3.4 Eksik parametre inline form-widget'ları

`missing_params` olan node'da uyarı rozeti; PlanCard içinde inline widget: `column_picker` (kaynak şemasından dropdown — I2 katalogdan, yoksa kaynak önizlemesinden), `source_picker`, `number_input`, `select`. Değer seçilince `POST /params` → validasyon rozetleri canlı güncellenir.

### 3.5 Şeffaflık stepper'ı

Plan üretilirken kartın üstünde adımlı progress (K3 standardı): *Niyet → Veri eşleme → Plan → Doğrulama*; her adım done/running/error ikonlu, hata adımı tıklanınca detay açılır.

### 3.6 Guided starter & durumlar

- **Empty:** boş sohbette 3 soruluk starter (Hedef ne? · Hangi veri? · Ne sıklıkla?) + J9 şablon kısayolları; yanıtlar ilk planner çağrısının bağlamı olur, sonrası serbest sohbet.
- **Loading:** stepper + canvas skeleton node'ları.
- **Error:** eyleme dönük mesaj ("Plan doğrulanamadı: n3 için date_column seçin") + ilgili widget'a odak.
- **Entegrasyon:** `Dashboard.tsx`'e "Sohbetle pipeline kur" CTA'sı; K1 Copilot dock aynı `PipelinePlannerService`'i kullanır (mevcut canvas'ı bağlam olarak gönderir).

## 4. Bağımlılıklar

- **Spec'ler:** K1 (node bileşenlerinin paylaşılması, Copilot dock), K3 (stepper/diff/durum standartları), I2 (kolon picker için katalog — opsiyonel zenginleştirme), J9 (few-shot şablonlar), J3 (materialize→trigger).
- **Mevcut kod:** `chat_service.py` (heuristik yolun sökülmesi), `supervisor_ds_team.py` `WorkflowPlannerAgent`, `workflow_chain_validator.py`, `workflow_ir_service`, `routes/scheduler.py` + `ScheduleParser`, `runtime_engine.py` (LLM fallback), `WorkflowDesignMessage.tsx`, `WorkflowDesigner.tsx`.
- **Kütüphaneler:** ReactFlow (mevcut), dagre/elkjs (layout), SSE (mevcut streaming altyapısı), pydantic.

## 5. Kapsam Dışı

- Designer içi tam düzenleme (Designer'da Aç sonrası K1'in işi).
- Plan çalıştırma runtime'ı (mevcut runtime kullanılır; self-healing J2'de).
- Çoklu-kullanıcı eşzamanlı plan düzenleme.
- Sesli giriş, çok dilli planlama optimizasyonu.
- GenAI/RAG pipeline planlama (platform kapsam kararı).

## 6. Test & Definition of Done

**Birim:**
- `PipelinePlannerService.plan()` — geçerli NL → şema-geçerli spec; validator hatasında onarım turu; 2 turda düzelmezse `invalid`.
- `PlanRevisionEngine.diff()` — ekleme/silme/param değişikliği kombinasyonları doğru sınıflanır.
- Geçersiz LLM JSON → parse retry → `plan_error`.
- `materialize(run)` invalid planda 409 döner.

**E2E:**
1. "churn modeli kur" → stream → canvas'ta ≥4 node → validasyon PASS → Kaydet → workflow DB'de.
2. Revizyon "SMOTE ekle" → diff'te 1 yeşil node → onay → revision=2 persist.
3. Eksik `target` → inline picker → seçim → Çalıştır aktifleşir → run başlar.
4. "her pazartesi 09:00" ile Zamanla → scheduler kaydı doğru cron ile oluşur.
5. Heuristik yol devre dışı: chat'ten hiçbir `workflow_design` artifact'ı keyword şablonundan gelmez (regresyon testi).

**DoD:** Yukarıdaki E2E'ler CI'da yeşil; plan üretimi p50 < 15 sn; stream kopmasında kurtarma çalışıyor; `_build_workflow_design` çağrısı kod tabanından kaldırıldı/flag'lendi; K3 durum standartları (empty/loading/error) mevcut; PLATFORM_SPEC durum tablosu ✍️ → 🚧 geçişine hazır.
