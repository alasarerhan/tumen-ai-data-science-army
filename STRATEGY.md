# DEPRECATED — canonical strategy is at `docs/STRATEGY.md`

> Bu kök dosya artık **canonical değil**. Yeni birleştirilmiş, İngilizce canonical strateji belgesi için bkz: [`docs/STRATEGY.md`](docs/STRATEGY.md).
>
> Buradaki içerik (Türkçe, 2026-03-04, v1.4) tarihsel referans olarak korunmuştur. Canonical sürüm Türkçe locked-decisions bölümünü ve İngilizce güncel roadmap/positioning'i tek dosyada birleştirir.

---

# Proje Geliştirme ve Strateji Belgesi: Otonom Stratejik Danışmanlık Platformu

  Belge Sürümü: 1.4
  Tarih: 04 Mart 2026

  İçindekiler:

1. Mevcut Durum Analizi
   * 1.1. Genel Bakış
   * 1.2. Mevcut Varlıklar (Uygulamalar, Agent'lar)
   * 1.3. Güçlü Yönler
   * 1.4. Gelişim Fırsatları ve Zayıf Yönler
2. Gelecek Vizyonu ve Stratejik Çerçeve
   * 2.1. Nihai Misyon
   * 2.2. Temel İşletim Modları
   * 2.3. Mimari Prensipler
   * 2.4. Hedef Platform Bileşenleri
   * 2.5. Multi-Tenant ve Concurrency Prensipleri
3. Detaylı Geliştirme Yol Haritası
   * Faz 1: Platform Temeli (API + Auth + Metadata + Orkestrasyon Entegrasyonu)
   * Faz 2: İş Akışı Tasarımcısı ve Çalıştırma (Designer → Execution)
   * Faz 3: Kurumsal Hazırlık ve Hibrit Dağıtım
   * Faz 4: İleri Analitik ve Stratejik Sentez
     * Görev 4.1: Stratejik İçgörü Süpervizörü
     * Görev 4.2: Gelişmiş JS Görselleştirme
     * Görev 4.3: AI Workspace — Konuşmalı Veri Analizi (M21)
4. Kilitlenen Kararlar (Özet)
5. Uygulama Durum Notu (Execution Status)

---

1. Mevcut Durum Analizi

  1.1. Genel Bakış
  Proje, "AI Data Science Team" konsepti altında, veri bilimi görevlerini otomatikleştirmeyi amaçlayan modüler Python agent'ları ve bu agent'ları kullanan
  Streamlit tabanlı prototip uygulamalardan oluşmaktadır.

  1.2. Mevcut Varlıklar

* Uygulamalar (`apps/`): AI Pipeline Studio, Exploratory Copilot, Pandas Data Analyst, SQL Database App.
* Tekil Agent'lar (`ai_data_science_team/agents/`): Veri temizleme, yükleme, görselleştirme, işleme, özellik mühendisliği ve SQL sorgulama gibi görevler için uzmanlaşmış agent'lar.
* Çoklu Agent Sistemleri (`ai_data_science_team/multiagents/`): PandasDataAnalyst, SQLDataAnalyst ve bu ekipleri yöneten bir SupervisorDSTeam gibi daha karmaşık görevler için tasarlanmış yapılar.

  1.3. Güçlü Yönler

* Modüler Mimari: Agent tabanlı yapı, yeni yeteneklerin kolayca eklenmesine olanak tanır.
* Sağlam Temel: Veri bilimi yaşam döngüsünün temel adımları (veri yükleme, temizleme, modelleme) için fonksiyonel agent'lar mevcuttur.
* Pipeline Odaklılık: Pipeline snapshot ve provenance yaklaşımı, yeniden üretilebilirlik ve süreç takibi için iyi bir başlangıç noktasıdır.
* Supervisor Altyapısı: LangGraph supervisor yaklaşımı (routing + tool-aware) platformun “interactive” çalışma modu için iyi bir omurga sağlar.

  1.4. Gelişim Fırsatları ve Zayıf Yönler

* Monolitik Arayüz: Streamlit prototipleme için iyi; ancak kurumsal ölçekte UX, RBAC, audit ve entegrasyon ihtiyaçlarında yetersiz.
* Concurrency / Multi-user Eksikliği: Birden fazla kullanıcının aynı anda, birbirinden tamamen bağımsız çalışması için tenant/workspace izolasyonu yok.
* Orkestrasyon Eksikliği: Güvenilir scheduling/retry/run history/queue mekanizması yok.
* Üretim Operasyonu: Cloud/on-prem dağıtım, secrets, observability, audit log, rate limit/quotas, artifact erişim politikaları eksik.

---

2. Gelecek Vizyonu ve Stratejik Çerçeve

  2.1. Nihai Misyon
  Projenin nihai misyonu, onu teknik bir araç setinden, veriye dayalı "Otonom Stratejik Danışmanlık Platformu"na dönüştürmektir. Bu platform, sadece analiz
  yapmakla kalmayacak, aynı zamanda bu analizleri yorumlayacak, iş bağlamını anlayacak ve eyleme geçirilebilir stratejik öneriler sunacaktır.

  2.2. Temel İşletim Modları
  Platform, farklı kullanıcı ihtiyaçlarına hizmet etmek üzere dört temel modda çalışabilecek şekilde tasarılanacaktır:

1. Tam Otonom Mod: Kullanıcı bir iş hedefi belirler. Platform tüm süreci uçtan uca yürütür.
2. **Opsiyonel Müdahale Modu (Human-in-the-Loop):** Pipeline hiçbir zaman kullanıcı için beklemez / durmaz. `WorkflowSignal` aracılığıyla kullanıcı istediği anda gözlemleyebilir, müdahale edebilir veya not ekleyebilir. Sistem yalnızca tüm otomatik kurtarma adımları (retry+backoff, fallback, circuit breaker) tükenmişse bildirim gönderir.
3. İnsan Tasarımlı, Otonom İcra Modu: Kullanıcı iş akışını tasarılar/kaydeder; akış zamanlanır veya event ile tetiklenir.
4. **Konuşmalı Analiz Modu (AI Workspace):** Kullanıcı doğal dilde soru sorar veya veri yükler; platform uygun agent’ı seçer, analiz/tahmin/raporu streaming olarak sunar. Workflow tasarlamak veya kod yazmak gerekmez.

  2.3. Mimari Prensipler

* Ayrık Mimari: Frontend (React) ve Backend (FastAPI) katmanları ayrılır; API contract ile konuşur.
* Hibrit Orkestrasyon:
  * Interactive (chat/UX): LangGraph supervisor + mevcut agent/tool ekosistemi.
  * Production runs (schedule/retry/history): Prefect (Prefect Cloud).
* Çok-kiracılı (Multi-tenant) Güvenlik: İzolasyon yalnızca UI ile değil, backend enforcement ile sağlanır.
* Artifact Erişim Politikası: Artifact’lar backend üzerinden kontrollü erişilir (signed URL / stream); doğrudan bucket erişimi varsayılmaz.
* Operasyonel Disiplin: Structured logging, audit logging, rate limit/quotas, secrets yönetimi, migration ve rollback yaklaşımı.
* On-Prem Önceliği: İlk hedef on-prem dağıtımı Docker Compose-first; Kubernetes (Helm) sonraki faz.

  2.4. Hedef Platform Bileşenleri

* Frontend: React (kurumsal UX + RBAC görünürlüğü + workflow designer yüzeyi + **AI Workspace konuşma arayüzü**).
* Backend API: FastAPI (auth, tenancy, metadata, orchestration gateway).
* Orchestrator:
  * Prefect Cloud: schedule, retries, queue/worker, run history.
  * LangGraph: supervisor-led interactive routing ve tool çağrıları.
* Metadata Store: PostgreSQL (Cloud SQL - Postgres) – tenant/workspace/user/RBAC, workflow tanımları, run kayıtları, audit log.
* Artifact Store: GCS (tek bucket + tenant/workspace prefix). Erişim: backend-only.
* Secrets: GCP Secret Manager (cloud). On-prem: env/secrets dosyası (compose) ile eşdeğer.
* Runtime:
  * Cloud: GCP Cloud Run (API ve gerektiğinde worker servisleri).
  * On-prem: Docker Compose.

  2.5. Multi-Tenant ve Concurrency Prensipleri

* Tenant: Kurumsal müşteri sınırı. Her kullanıcı bir veya daha fazla tenant’a üyedir.
* Workspace: Tenant içindeki proje/çalışma alanı. Data sources, workflow’lar ve run’lar workspace altında tutulur.
* İzolasyon:
  * Her API çağrısı tenant/workspace context ile doğrulanır.
  * DB’de tüm kayıtlar tenant/workspace ile scope edilir; yetkisiz erişim backend’de engellenir.
  * Prefect tarafında tenant izolasyonu için en azından workspace/tag/queue ayrımı yapılır (prefer: Prefect workspace-per-tenant).
* Provisioning: Admin-created / invite-only (self-serve sign-up yok).
* Audit + Quotas: Tüm kritik işlemler (invite, workflow run, artifact erişimi, secrets) audit log’a yazılır; tenant bazlı rate limit/quotas uygulanır.

---

3. Detaylı Geliştirme Yol Haritası

  Faz 1: Platform Temeli (API + Auth + Metadata + Orkestrasyon Entegrasyonu)
  Amaç: Multi-tenant ve concurrency’yi taşıyacak çekirdek platformu ayağa kaldırmak.

* Görev 1.1: Ayrık Mimari Başlangıcı
  * React frontend projesi başlatmak (skeleton).
  * FastAPI backend projesi başlatmak (skeleton).
  * Dev stack: Docker Compose ile Postgres + API.
* Görev 1.2: Kimlik Doğrulama ve Tenancy Temeli
  * OIDC (Google Workspace) JWT doğrulama.
  * Tenant/workspace/user/RBAC veri modeli ve API enforcement.
  * Invite-only provisioning akışı.
* Görev 1.3: Orkestrasyon Gateway (Prefect)
  * Prefect Cloud bağlantısı (workspace/queue tasarımı).
  * API’den basit bir “flow run” başlatma ve run status sorgulama.
* Görev 1.4: Artifact ve Secrets Temeli
  * GCS prefix stratejisi + backend-only access pattern.
  * Secret Manager entegrasyonu için arayüz (cloud) + on-prem fallback.

  Faz 2: İş Akışı Tasarımcısı ve Çalıştırma (Designer → Execution)
  Amaç: Workflow plan/spec formatı, designer UI ve execution pipeline.

* Görev 2.1: Workflow Spec ve Validasyon
  * Workflow JSON/YAML şeması (mevcut planner agent step sözleşmesiyle uyum).
  * Backend tarafında validasyon ve versiyonlama.
* Görev 2.2: Workflow Designer UI (React)
  * Minimum yüzey: workflow listeleme, oluşturma, spec edit, run tetikleme.
* Görev 2.3: Execution
  * Prefect flow’ları: dataset load → wrangle/clean → EDA/viz → model/evaluate.
  * Run history + artifact index.

  Faz 3: Kurumsal Hazırlık ve Hibrit Dağıtım
  Amaç: Operasyon, güvenlik, dağıtım paketleri.

* Görev 3.1: On-Prem Paket
  * Docker Compose-first (API + worker + DB + optional local artifact store).
* Görev 3.2: Cloud Run Dağıtımı
  * Cloud Run için containerizasyon + env/secrets.
* Görev 3.3: Observability
  * Structured logs, audit log, temel metrikler.

  Faz 4: İleri Analitik ve Stratejik Sentez
  Amaç: Sonuçları “stratejik öneri” katmanına yükseltmek.

* Görev 4.1: Stratejik İçgörü Süpervizörü
  * Results synthesis + context gathering + öneri motoru.* Görev 4.2: Gelişmiş JS Görselleştirme
  * D3.js/ECharts bileşenler, Sankey, network graph.
* **Görev 4.3: AI Workspace — Konuşmalı Veri Analizi (→ M21)**
  * Julius AI / ChatGPT Advanced Data Analysis benzeri konuşma arayüzü.
  * Kullanıcı CSV/Excel yükler, doğal dilde soru sorar; SupervisorRouter mesajı uygun agent'a yönlendirir (Pandas, SQL, Forecast, Clustering, Strategic).
  * Yanıtlar SSE ile streaming olarak gelir; grafik/tablo/rapor artifact otomatik render edilir.
  * Tablo backend: `chat_sessions` + `chat_messages` (PostgreSQL); geçmiş konversasyonlar saklanır.
---

4. Kilitlenen Kararlar (Özet)

* Orkestrasyon: Prefect Cloud (production runs) + LangGraph (interactive supervisor).
* Bulut: GCP öncelikli; runtime Cloud Run.
* On-prem: Docker Compose-first.
* Frontend: React.
* Kimlik Doğrulama: OIDC (Google Workspace).
* Metadata Store: Cloud SQL (Postgres).
* Artifacts: GCS, tenant/workspace prefix; erişim backend-only (signed URL / stream).
* Secrets: GCP Secret Manager.
* Provisioning: Admin-created / invite-only.
* **HITL (Human-in-the-Loop):** Opsiyonel müdahale (`WorkflowSignal`) — pipeline hiçbir zaman bloklayıcı beklemez; çalışma zamanında kullanıcı istediği an devreye girebilir.
* **Orkestrasyon Katmanı (M22):** AgentRegistry + ContextStore + WorkflowResolver + RuntimeEngine + WorkflowSignal + OrchestratorAgent — 3 çalışma senaryosunu destekler (dinamik, denetimli, tam manuel).

---

5. Uygulama Durum Notu (Execution Status)

  02 Mart 2026 itibarıyla Faz 1 çekirdek hedefleri tamamlanmıştır. Faz 2 ve Faz 3 kısmi ilerleme seviyesindedir; Faz 4 başlatılmış ancak tamamlanmamıştır.

* Detaylı ve güncel milestone takibi:
  * `ai-data-science-team/PLAN.md` (kanonik icra planı)

* Tamamlanan teknik kapsam (özet):
  * FastAPI tabanlı `platform-api-app` servisi, multi-tenant veri modeli, invite-only provisioning ve audit log altyapısı.
  * Prefect run persistence, run history ve artifact index/access temel uçları.
  * Workflow spec/versioning API başlangıcı, observability ve quota için ilk hardening adımları.
  * Docker Compose dev stack, migration-on-start ve smoke test akışları.

* Kısmi/aktif kapsam:
  * Workflow lifecycle sertleştirmesi ve daha güçlü doğrulama kapıları.
  * Tenant/workspace RBAC matrisinin ince taneli genişletilmesi.
  * Cloud Run production hardening checklist maddelerinin kapanması.

* Sonraki öncelikler:
  * **Orkestrasyon Katmanı (M22):** AgentRegistry + RuntimeEngine + OrchestratorAgent + WorkflowSignal — tüm agent'ları yönetecek altyapı; M21 ve M23–M25 için kritik ön bağımlılık. En yüksek öncelik.
  * Workflow Designer ve execution zincirinin uçtan uca olgunlaştırılması.
  * Operasyonel güvenilirlik (SLO/alerting/runbook/rollback) kapanışları.
  * Stratejik sentez katmanının kalite ve kapsam genişletmesi.
  * **AI Workspace (M21):** Konuşmalı arayüzle veri analizi, tahmin ve rapor üretimi (M10 + M22 tamamlandıktan sonra).
  * **Yeni Agent'lar (M23–M25):** Model açıklanabilirlik, model izleme, veri kalitesi, API bağlayıcı, belge parser (M22 sonrası).
