# TÜMEN Platform Spec Kataloğu (Harita)

> Bu dosya **haritadır**: her yetenek burada backend + UI birlikte, katalog seviyesinde tanımlanır.
> Her spec'in derinlemesine tasarımı `docs/specs/<ID>-<slug>.md` dosyasına yazılır (aşağıdaki şablonla).
> Eski `AGENT_SPEC_CATALOG.md` ve `UI_SPEC_CATALOG.md` bu dosyada birleştirilmiştir.

## Vizyon

Bir data scientist / ML engineer'ın en basit işten en karmaşığa yaptığı her şeyi, hem adım adım (sohbet) hem pipeline olarak yapabilen agentic platform: sohbetle uçtan uca pipeline kurma, her yapısal veri kaynağıyla çalışma, görsel tasarım + cron/olay tetikleyicili çalıştırma, drift→retrain→promote kapalı döngülü MLOps.

## Kapsam Kararı

Platform kapsamı **DS/ML**'dir. Bilinçli olarak **kapsam dışı**: GenAI/RAG uygulama builder'ı, uzak compute profilleri (K8s/Spark/GPU), dbt entegrasyonu, Kafka streaming ingest, custom agent marketplace/SDK — bunlar platformu başka ürün kategorilerine kaydırır.

## Detay Spec Şablonu (her `docs/specs/<ID>-<slug>.md` dosyası bunu izler)

```markdown
# <ID> — <Ad>
## 1. Amaç & Kullanıcı Hikâyeleri   (kim, neden, kabul senaryoları)
## 2. Backend Tasarımı              (agent sınıfı/dosyası, node tipi + I/O sözleşmesi, API endpoint'leri, veri modeli/migration, hata durumları)
## 3. UI Tasarımı                   (ekran/bileşenler, etkileşim akışı, loading/empty/error durumları, mevcut ekranlarla entegrasyon)
## 4. Bağımlılıklar                 (diğer spec ID'leri, kütüphaneler, mevcut kod entegrasyon noktaları)
## 5. Kapsam Dışı                   (bu spec'te bilinçli yapılmayanlar)
## 6. Test & Definition of Done     (birim/e2e test senaryoları, tamamlanma kriterleri)
```

## Goal Olarak Kullanım

Detaylandırma görevi şöyle verilebilir: *"PLATFORM_SPEC.md'deki <ID> spec'ini şablona göre `docs/specs/` altına detaylandır"* veya *"Durum tablosundaki tüm 📋 spec'leri sırayla detaylandır"*. Detay dosyası yazılınca aşağıdaki tabloda durum ✍️ (detaylandırıldı), implementasyon bitince ✅ yapılır.

---

## Durum Tablosu (tek bakışta takip)

Durum: 📋 katalogda · ✍️ detay spec yazıldı · 🚧 implementasyonda · ✅ bitti

| ID | Ad | Öncelik | Faz | Durum | Detay dosyası |
|---|---|---|---|---|---|
| A1 | AB Testing | P0 | 1 | ✅ | specs/A1-ab-testing.md |
| A2 | Power Analysis & Deney Tasarımı | P1 | 2 | ✅ | specs/A2-power-analysis.md |
| A3 | Bayesian Analysis | P2 | 3 | ✅ | specs/A3-bayesian-analysis.md |
| A4 | Hypothesis Testing Danışmanı | P1 | 2 | ✅ | specs/A4-hypothesis-testing.md |
| A5 | Causal Inference | P2 | 3 | ✅ | specs/A5-causal-inference.md |
| B1 | Data Profiling genişletmesi | P1 | 2 | ✅ | specs/B1-data-profiling.md |
| B2 | Data Validation / Kalite Kapısı | P0 | 1 | ✅ | specs/B2-data-validation.md |
| B3 | Schema Inference & Mapping | P1 | 2 | ✅ | specs/B3-schema-inference.md |
| B5 | PII Detection & Anonymization | P1 | 2 | ✅ | specs/B5-pii-detection.md |
| B7 | Data Ingestion / ELT | P1 | 2 | ✅ | specs/B7-data-ingestion.md |
| C1 | Insight Mining (EDA eki) | P2 | 3 | ✅ | specs/C1-insight-mining.md |
| C2 | Dashboard Kompozisyonu | P2 | 3 | ✅ | specs/C2-dashboard-composition.md |
| C3 | KPI / Business Metrics | P1 | 2 | ✅ | specs/C3-kpi-metrics.md |
| C4 | Root Cause Analysis | P1 | 2 | ✅ | specs/C4-root-cause-analysis.md |
| C5 | Rapor genişletmesi (şablon/export) | P2 | 3 | ✅ | specs/C5-report-templates.md |
| D2 | Feature Selection + Leakage | P1 | 2 | ✅ | specs/D2-feature-selection.md |
| D3 | Feature Store | P2 | 3 | ✍️ | specs/D3-feature-store.md |
| D4 | Imbalanced Data | P1 | 2 | ✍️ | specs/D4-imbalanced-data.md |
| E1 | Sklearn/XGBoost/LightGBM Trainer | P0 | 1 | ✅ | specs/E1-multi-engine-trainer.md |
| E2 | Hyperparameter Optimization | P0 | 1 | ✅ | specs/E2-hpo.md |
| E3 | Deep Learning (Tabular/TS) | P1 | 2 | ✅ | specs/E3-deep-learning.md |
| E11 | Time Series genişletmesi | P2 | 3 | ✅ | specs/E11-time-series-ext.md |
| E12 | Clustering genişletmesi | P2 | 3 | ✍️ | specs/E12-clustering-ext.md |
| F1 | Evaluation genişletmesi | P1 | 2 | ✅ | specs/F1-evaluation-ext.md |
| F2 | Champion–Challenger | P0 | 1 | ✅ | specs/F2-champion-challenger.md |
| F3 | Fairness & Bias Audit | P2 | 3 | ✅ | specs/F3-fairness-audit.md |
| F4 | Model Card | P2 | 3 | ✅ | specs/F4-model-card.md |
| F5 | Robustness Test | P3 | 4 | ✍️ | specs/F5-robustness-test.md |
| F6 | LLM-as-Judge (agent kalite) | P1 | 2 | ✍️ | specs/F6-llm-judge.md |
| G1 | Otomatik Drift Hesabı | P0 | 1 | ✅ | specs/G1-auto-drift.md |
| G2 | Auto-Retraining Orchestrator | P0 | 1 | ✅ | specs/G2-auto-retraining.md |
| G3 | Gerçek Model Serving/Deploy | P1 | 2 | ✅ | specs/G3-model-serving.md |
| G4 | Batch Scoring + model.predict | P0 | 1 | ✅ | specs/G4-batch-scoring.md |
| G5 | Registry Promotion | P1 | 2 | ✅ | specs/G5-registry-promotion.md |
| G7 | Incident / Alerting | P2 | 3 | ✍️ | specs/G7-alerting.md |
| H1 | Snowflake Connector | P1 | 2 | ✍️ | specs/H1-snowflake.md |
| H2 | BigQuery Connector | P1 | 2 | ✍️ | specs/H2-bigquery.md |
| H3 | Tableau Connector | P1 | 2 | ✍️ | specs/H3-tableau.md |
| H4 | PowerBI Connector | P1 | 2 | ✍️ | specs/H4-powerbi.md |
| H5 | Google Sheets Connector | P2 | 3 | ✍️ | specs/H5-google-sheets.md |
| H6 | S3/GCS Dataset Connector | P1 | 2 | ✍️ | specs/H6-object-storage.md |
| H7 | REST API Data Source | P2 | 3 | ✍️ | specs/H7-rest-api-source.md |
| I2 | Data Catalog & Semantik Katman | P1 | 2 | ✅ | specs/I2-data-catalog.md |
| I3 | Experiment Tracking / Leaderboard | P1 | 2 | ✍️ | specs/I3-experiment-tracking.md |
| J1 | Otonom İnvestigasyon | P1 | 2 | ✍️ | specs/J1-autonomous-investigation.md |
| J4 | Model Evaluation Store | P1 | 2 | ✍️ | specs/J4-evaluation-store.md |
| J6 | Responsible AI Dashboard | P2 | 3 | ✍️ | specs/J6-responsible-ai.md |
| J7 | Governance Katmanı | P2 | 3 | ✍️ | specs/J7-governance.md |
| J11 | Shadow/Canary Deployment | P2 | 3 | ✍️ | specs/J11-shadow-canary.md |
| J12 | Uçtan Uca Lineage Grafı | P2 | 3 | ✍️ | specs/J12-lineage-graph.md |
| J13 | Data Diff Paneli | P2 | 3 | ✍️ | specs/J13-data-diff.md |
| K2 | ModelOps Kontrol Merkezi | P0 | 1 | ✅ | specs/K2-modelops-center.md |

---

## A. İstatistik & Deney Tasarımı

### A1 🆕 AB Testing — P0
- **Amaç:** Uçtan uca A/B(/n) analizi: SRM kontrolü, doğru test seçimi (t/Mann-Whitney/chi-square), lift+CI, çoklu karşılaştırma düzeltmesi (Bonferroni/BH), CUPED, "ship/iterate/abort" kararı.
- **Backend:** yeni agent + `experiment.analyze` node tipi; sonuç artifact şeması (test tablosu, karar).
- **UI:** deney kurulum sihirbazı (metrik, gruplar) → sonuç sayfası: grup karşılaştırma kartları, CI çubukları, SRM uyarı banner'ı, karar kutusu, "rapora çevir".

### A2 🆕 Power Analysis & Deney Tasarımı — P1
- **Amaç:** Deney öncesi örneklem/MDE/süre hesabı, randomizasyon-stratifikasyon önerisi.
- **UI:** A1 sihirbazının ilk adımı; MDE↔süre canlı güncellenen grafik.

### A3 🆕 Bayesian Analysis — P2
- **Amaç:** Bayesian A/B (posterior, expected loss), tahmin aralıkları. **Backend:** PyMC veya conjugate-prior.
- **UI:** A1 sonuç sayfasında "Bayesian görünüm" sekmesi (posterior dağılım grafiği, "B'nin daha iyi olma olasılığı").

### A4 🆕 Hypothesis Testing Danışmanı — P1
- **Amaç:** Serbest soruyu doğru teste yönlendirme: varsayım kontrolleri, parametrik/nonparametrik seçim, etki büyüklüğü, sade dilde açıklama.
- **UI:** chat-first; sonuç inline kartı (test adı, neden seçildi, sonuç, yorum).

### A5 🆕 Causal Inference — P2
- **Amaç:** Deneysiz nedensel etki: propensity matching, diff-in-diff, IV (DoWhy/EconML).
- **UI:** analiz kurulum formu (treatment/outcome/confounder seçimi) + varsayım/duyarlılık rapor görünümü.

### A6 🆕 Uplift Modeling — P3
- **Amaç:** T/X-learner, uplift trees; "kimi hedeflersek en çok kazanırız" segmentasyonu. **UI:** uplift eğrisi + segment tablosu.

## B. Veri Mühendisliği & Kalite

### B1 🔶 Data Profiling genişletmesi — P1
- **Amaç:** Kolon istatistik/dağılım kartları, kardinalite, PII adayı işaretleme, otomatik veri sözlüğü.
- **UI:** profil sonucu ekranı (kolon grid'i, dağılım mini grafikleri); I2 katalog kolonlarıyla aynı bileşen.

### B2 🆕 Data Validation / Kalite Kapısı — P0
- **Amaç:** Great Expectations tarzı veri sözleşmeleri; pipeline'da kalite kapısı — ihlalde durdur veya HITL'e düşür.
- **Backend:** `data.validate` node (mevcut `data_quality_agent` üstüne kural motoru); kural CRUD API.
- **UI:** expectation suite editörü (kolon+kural+eşik listesi), kural başına pass/fail geçmişi sparkline'ı; run detayında ihlal paneli (hangi kural, kaç satır, örnekler).

### B3 🆕 Schema Inference & Mapping — P1
- **Amaç:** Yeni kaynakta tip çıkarımı, tarih/para normalizasyonu, hedef şemaya LLM destekli kolon eşleme.
- **UI:** eşleme tablosu (kaynak kolon → hedef kolon, güven skoru, onayla/düzelt).

### B4 🆕 Deduplication & Entity Resolution — P2
- **Amaç:** Fuzzy matching ile mükerrer tespit/birleştirme; blocking + benzerlik skoru.
- **UI:** şüpheli eşleşme inceleme kuyruğu (yan yana kayıt karşılaştırma, birleştir/ayrı tut) — HITL altyapısıyla.

### B5 🆕 PII Detection & Anonymization — P1
- **Amaç:** PII kolon tespiti (regex+NER), maskeleme/hash/tokenizasyon; Presidio adayı.
- **UI:** tespit sonucu listesi + kolon başına strateji seçimi; katalogda PII rozeti.

### B6 🆕 Synthetic Data — P2
- **Amaç:** SDV/CTGAN veya istatistiksel sentetik tablo verisi; orijinal-sentetik benzerlik raporu.
- **UI:** üretim formu (satır sayısı, korunacak ilişkiler) + benzerlik rapor görünümü.

### B7 🆕 Data Ingestion / ELT — P1
- **Amaç:** Kayıtlı kaynaktan periyodik/incremental çekim (watermark), dosya-drop tetiklemeli ingest; J3 ile birleşir.
- **UI:** ingest job tanım formu (kaynak, hedef, artımlılık anahtarı, takvim), çalışma geçmişi tablosu.

### B8 🆕 SQL Optimizer — P2
- **Amaç:** EXPLAIN planı analizi, indeks/rewrite önerisi. **UI:** sorgu + plan + öneri diff görünümü.

## C. Keşif, Görselleştirme & Raporlama

### C1 🔶 Insight Mining — P2 · EDA'ya otomatik ilginç segment/korelasyon/aykırılık bulan anlatı katmanı. **UI:** sıralanmış içgörü kartları (bulgu + kanıt grafiği).
### C2 🔶 Dashboard Kompozisyonu — P2 · birden çok grafiği tek dashboard artifact'ına bağlama. **UI:** grid tabanlı dashboard düzenleyici, paylaşılabilir görünüm.
### C3 🆕 KPI / Business Metrics — P1
- **Amaç:** Metrik tanımı → hesap kodu → periyodik izleme + anomali alarmı; metrik kataloğu.
- **UI:** **KPI Board** — metrik kartları grid'i (değer, trend sparkline, hedef çizgisi, anomali işareti); kart → detay + alarm kural editörü.
### C4 🆕 Root Cause Analysis — P1
- **Amaç:** "Metrik neden değişti" — boyut bazlı katkı ayrıştırması, dönem karşılaştırma.
- **UI:** waterfall katkı grafiği, boyut drill-down ağacı, agent anlatı özeti.
### C5 🔶 Rapor genişletmesi — P2 · şablonlu periyodik rapor, PDF/PPTX export. **UI:** şablon seçimi + zamanlama; Reports ekranına export butonları.

## D. Feature Engineering & Yönetimi

### D2 🆕 Feature Selection + Leakage — P1
- **Amaç:** Filtre/wrapper/embedded seçim, **target leakage taraması**, multicollinearity raporu.
- **UI:** feature importance/eleme tablosu, leakage uyarı banner'ı (hangi kolon, neden şüpheli).
### D3 🆕 Feature Store — P2
- **Amaç:** Versiyonlu feature saklama/paylaşım, train-serve tutarlılığı (artifact tabanlı başlangıç).
- **UI:** feature kataloğu (arama, versiyon, kullanan modeller), "pipeline'a ekle" aksiyonu.
### D4 🆕 Imbalanced Data — P1
- **Amaç:** Dengesizlik tespiti + SMOTE/undersampling/class weights/threshold tuning; PR-AUC odaklı metrik önerisi.
- **UI:** sınıf dağılım grafiği + strateji seçim kartları (her stratejinin beklenen etkisiyle).

## E. Model Eğitimi

### E1 🆕 Sklearn/XGBoost/LightGBM Trainer — P0
- **Amaç:** H2O dışı klasik ML: problem tipine göre model adayları, CV, sklearn pipeline üretimi, MLflow loglama.
- **Backend:** `model.train` node'una `engine` parametresi (`h2o|sklearn|xgboost|lightgbm|dl`); yeni trainer agent.
- **UI:** train node config panelinde engine seçici + engine'e özel parametre formları; sonuç metrik kartı.
### E2 🆕 Hyperparameter Optimization — P0
- **Amaç:** Optuna HPO: arama uzayı önerisi, budget (trial/süre), pruning, MLflow kaydı.
- **UI:** I3 içinde HPO görünümü — trial'lar paralel-koordinat grafiği, optimizasyon eğrisi, "en iyi konfigürasyonla node oluştur".
### E3 🆕 Deep Learning (Tabular/TS) — P1 · PyTorch MLP/TabNet + LSTM/TFT; early stopping, GPU farkındalığı. **UI:** eğitim eğrisi canlı grafiği (loss/metric per epoch), erken durdurma göstergesi.
### E4 🆕 NLP / Text Analytics — P1 · sınıflandırma, duygu, konu modelleme (BERTopic), NER, embedding. **UI:** konu/duygu dağılım görselleri, örnek metin açıklamaları.
### E5 🆕 Computer Vision — P3 · transfer learning (timm); dataset doğrulama, augmentation. **UI:** örnek grid + tahmin overlay'i.
### E6 🆕 Recommender — P2 · collaborative/content-based; recall@k, NDCG. **UI:** örnek kullanıcı → öneri listesi önizlemesi.
### E7 🆕 Survival Analysis — P3 · Kaplan-Meier, Cox PH (lifelines). **UI:** survival eğrileri, hazard oranı tablosu.
### E8 🆕 Graph ML — P3 · community detection, centrality, node embedding. **UI:** interaktif ağ görselleştirmesi.
### E9 🆕 Optimization / OR — P3 · LP/MIP (PuLP/OR-Tools): tahsis, rota, stok. **UI:** kısıt formu + çözüm tablosu/duyarlılık.
### E10 🆕 Simulation / What-If — P2
- **Amaç:** Model üzerinde senaryo analizi, sensitivity, Monte Carlo.
- **UI:** **What-If paneli** — model detayında slider/input'larla girdi değiştir → tahmin + SHAP katkıları canlı güncellenir.
### E11 ✅+ Time Series genişletmesi — P2 · hiyerarşik forecast, tatil takvimi, Prophet/statsforecast motorları. **UI:** forecast bandı grafiği (CI'lı), seri seçici.
### E12 ✅+ Clustering genişletmesi — P2 · LLM ile küme profilleme/isimlendirme, segmentasyon şablonu. **UI:** küme kartları (isim, boyut, ayırt edici özellikler).

## F. Değerlendirme, Güven & Sorumlu AI

### F1 ✅+ Evaluation genişletmesi — P1 · kalibrasyon, iş maliyet matrisiyle threshold optimizasyonu, segment bazlı performans. **UI:** kalibrasyon grafiği, maliyet matrisi editörü + threshold slider'ı, segment performans tablosu.
### F2 🆕 Champion–Challenger — P0
- **Amaç:** Modelleri aynı protokolde karşılaştırma, istatistiksel anlamlılık (McNemar/DeLong), promotion önerisi.
- **UI (K2 içinde):** yan yana metrik tablosu (anlamlılık işaretli), üst üste ROC/PR eğrileri, segment farkları; karar barı: **Promote (HITL'e düşer) / Reddet / Bekle**.
### F3 🆕 Fairness & Bias Audit — P2 · grup bazlı adalet metrikleri, azaltma önerileri. **UI:** J6 dashboard'unda grup bazlı bar grafikleri.
### F4 🆕 Model Card — P2 · otomatik model dokümantasyonu (veri, feature'lar, metrikler, sınırlamalar, lineage). **UI:** model detayının "Genel bakış" sekmesi + PDF export.
### F5 🆕 Robustness Test — P3 · perturbation/edge-case testleri. **UI:** test sonuç matrisi.
### F6 🆕 LLM-as-Judge — P1 · agent'ların ürettiği kod/analiz/raporların kalite skorlaması; hatalı codegen'i kullanıcıya ulaşmadan yakalama. **UI:** agent başına kalite metrikleri paneli (Agents ekranına sekme).

## G. MLOps — Kapalı Döngü

### G1 🔶 Otomatik Drift Hesabı — P0
- **Amaç:** Prediction drift (PSI/KS) + performance decay'in zamanlanmış otomatik hesabı (şu an sadece kayıt katmanı var).
- **UI (K2 içinde):** feature bazlı drift ısı listesi, referans vs güncel dağılım karşılaştırma grafikleri, drift trend zaman serisi.
### G2 🆕 Auto-Retraining Orchestrator — P0 · **kapalı döngünün kalbi**
- **Amaç:** Policy motoru: tetikleyici (drift eşiği/performans düşüşü/veri tazeliği/takvim) → retrain workflow başlat → F2 değerlendirme → HITL onay → promotion.
- **UI (K2 içinde):** **Retrain Policy Editor** — görsel kural builder (TETİKLEYİCİ→AKSİYON→DEĞERLENDİRME→ONAY) + politika simülasyonu ("bu kural geçen ay 3 kez tetiklenirdi").
### G3 🔶 Gerçek Model Serving/Deploy — P1
- **Amaç:** FastAPI endpoint scaffold / Docker / BentoML üretimi; ModelOps "deploy"unun gerçekten deploy etmesi; rollback.
- **UI:** deploy sihirbazı (hedef: endpoint/batch/container), tek tık rollback (confirm dialoglu).
### G4 🆕 Batch Scoring + `model.predict` node — P0
- **Amaç:** Kayıtlı modelle pipeline içinde toplu tahmin → artifact/hedef tablo. (Şu an tahmin node'u hiç yok — kritik boşluk.)
- **UI:** predict node config (model versiyonu seçici, çıktı hedefi); sonuç önizleme tablosu.
### G5 🆕 Registry Promotion — P1 · dev→staging→prod stage yönetimi, imza/şema doğrulama, onay zinciri; MLflow Registry senkron. **UI:** stage rozetleri + promotion timeline'ı.
### G6 🆕 Cost Optimization — P2 · run bazında LLM token/compute/storage maliyeti, pahalı node tespiti. **UI:** maliyet breakdown grafiği, workflow bazlı trend, en pahalı node tablosu (finops route'larıyla).
### G7 🆕 Incident / Alerting — P2 · drift/failure/SLA bildirimleri (Slack/e-posta/webhook). **UI:** alarm kuralı CRUD, olay zaman çizelgesi, header bildirim çanı (severity renkli).

## H. Konektörler & Veri Kaynakları

Ortak UI: **konektör galerisi** (logo grid), konektör-özel auth formları, adım adım bağlantı testi sonucu (DNS→auth→sorgu→örnek okuma).

### H1 🆕 Snowflake — P1 · key-pair/SSO auth, warehouse seçimi, pushdown.
### H2 🆕 BigQuery — P1 · servis hesabı JSON upload, dataset tarama, dry-run maliyet tahmini.
### H3 🆕 Tableau — P1 · Hyper API okuma + published datasource'a yazma.
### H4 🆕 PowerBI — P1 · REST dataset okuma/push, refresh tetikleme.
### H5 🆕 Google Sheets — P2.
### H6 🆕 S3/GCS Dataset — P1 · bucket'tan parquet/csv, kayıtlı kaynak olarak.
### H7 🆕 REST API Data Source — P2 · `api_connector_agent`'ı data source kataloğuna bağlama (kayıtlı endpoint + auth + şema).

## I. Platform / Chat Katmanı

### I1 🆕 LLM Pipeline Planner + Copilot UI — P0 · **vizyonun 1 numaralı maddesi**
- **Amaç:** Chat'teki heuristik workflow-design yerine LLM planner: NL → plan → `workflow_chain_validator` doğrulaması → önizleme → konuşarak iteratif revizyon.
- **Backend:** planner servisi (streaming plan chunk'ları), supervisor/`WorkflowPlannerAgent` entegrasyonu, validasyon hata şeması.
- **UI:** **çift panel copilot** — solda chat, sağda canlı ReactFlow plan canvas'ı (Designer node bileşenleri yeniden kullanılır). Plan kartı aksiyonları: *Designer'da Aç / Kaydet / Çalıştır / Zamanla*. Revizyon diff'i (eklenen yeşil/silinen kırmızı/değişen sarı). Eksik parametrede inline form-widget (kolon seçici dropdown). Plan üretim adımları şeffaflık stepper'ı. Guided starter (hedef/veri/sıklık) → serbest sohbet.
### I2 🆕 Data Catalog & Semantik Katman — P1
- **Amaç:** Kaynaklardan şema/istatistik toplayan katalog; planner'ın "churn verisi hangi tabloda" sorusuna cevabı; iş terimi↔kolon eşlemesi.
- **UI:** kaynak→şema→tablo→kolon ağacı, arama, kolon istatistik kartı, PII rozeti, "hangi pipeline'lar kullanıyor"; chat'teki kaynak picker'ı aynı bileşen.
### I3 🆕 Experiment Tracking / Leaderboard — P1
- **Amaç:** MLflow verisini frontend'e taşıma.
- **UI:** yeni `Experiments` ekranı — sıralanabilir leaderboard (metrik kolonları, engine rozeti, süre/maliyet); 2–4 run karşılaştırma (radar chart, hiperparametre diff — yalnız farklılaşanlar, feature importance yan yana); E2 HPO görünümü.
### I4 🆕 Notebook Export — P2 · run'ı çalıştırılabilir Jupyter notebook'a paketleme (agent kodları zaten mevcut). **UI:** run detayında "Notebook olarak indir".

## J. Sektör Pratiğinden Gelen Yetenekler

### J1 🆕 Otonom İnvestigasyon — P1 · KPI değişince sorulmadan çok adımlı araştırma (tespit→ayrıştır→nicelendir→anlatı). **UI:** Dashboard'a "İçgörüler" feed'i (bulgu kartı + kanıt grafiği + "derinleştir").
### J2 🆕 Self-Healing Pipeline — P1 · node hatasında AI kök-neden analizi + otomatik onarım (şema düzeltme, fallback agent), onarılamazsa açıklamalı HITL. **Backend:** `runtime_engine` retry/circuit-breaker üstüne diagnose&repair. **UI:** run detayında "onarım denemesi" timeline'ı (ne denendi, sonuç).
### J3 🆕 Olay Tabanlı Tetikleyiciler — P1 · "yeni veri gelince / dataset değişince / kalite geçince / workflow bitince" çalıştır; tetikleyici+koşul+aksiyon zinciri. **UI:** trigger builder formu + tetiklenme geçmişi.
### J4 🆕 Model Evaluation Store — P1 · değerlendirme sonuçlarının versiyonlu mağazası: metrik trendi, dilim bazlı geçmiş, status check'ler. **UI:** K2 model detayında "Performans trendi" sekmesinin veri katmanı.
### J5 🆕 Data Labeling — P2 · etiketleme görevi, aktif öğrenme önceliklendirmesi, LLM ön-etiket + insan doğrulama (HITL). **UI:** klavye kısayollu etiketleme ekranı, ilerleme + anlaşmazlık metrikleri.
### J6 🆕 Responsible AI Dashboard — P2 · F3 fairness + explainability + hata analizi tek ekranda. **UI:** model detayı sekmesi.
### J7 🆕 Governance Katmanı — P2 · onay iş akışları, risk sınıflandırması, üretime alma checklist'i, denetim raporu. **UI:** HITLApproval'ın genişlemesi — risk rozetleri, imza zinciri timeline'ı, rapor export.
### J8 🆕 Visual Recipe Kitaplığı — P2 · kodsuz ince taneli dönüşüm node'ları: join, group, pivot, filter, split, union, window. **UI:** Designer paletinde "Recipes" sekmesi; çift tık → görsel konfigürasyon (kolon seçici, koşul builder).
### J9 🆕 Proje Şablonları — P1 · churn, forecast, segmentasyon, fraud hazır uçtan uca pipeline'lar; I1 planner'ın few-shot temeli. **UI:** "Yeni Workflow" şablon galerisi — önizleme canvas'ı + "verine uyarla" sihirbazı (kolon eşleme adımı).
### J10 🆕 Blueprint/Leaderboard Arama — P2 · çoklu algoritma+preprocessing kombinasyonunu paralel yarıştırma, ensemble. **UI:** I3 leaderboard'unun "yarışma modu".
### J11 🆕 Shadow/Canary Deployment — P2 · yeni modeli kısmi/gölge trafikte canlı karşılaştırma, otomatik rollback eşiği. **UI:** K2 deploy panelinde canary yüzde slider'ı + canlı trafik karşılaştırma grafiği.
### J12 🆕 Uçtan Uca Lineage Grafı — P2 · kaynak→dataset→feature→model→deployment→rapor zinciri. **UI:** tam ekran interaktif graf; düğüm→varlığa git; "impact analysis" modu (downstream highlight).
### J13 🆕 Data Diff Paneli — P2 · iki dataset/run versiyonu farkı: satır/kolon, dağılım kayması mini grafikleri, şema değişiklikleri. **UI:** karşılaştırma seçici + diff görünümü.

## K. Platform UI Yüzeyleri (özellik-üstü ekran spec'leri)

### K1 🆕 Workflow Designer 2.0 — P0
- **Flow Zones:** node'ları isimli bölgelere gruplama (Ingest/Prep/Train/Evaluate/Deploy), collapse/expand.
- **Zengin node kartları (P0):** canlı durum (✓/✗/süre), giriş-çıkış şema özeti, veri önizleme popover'ı (ilk 20 satır), kalite kapısı rozeti.
- **Inline validasyon (P0):** canvas'ta anlık hata/uyarı işaretleri; "sorunlar paneli" → tıkla, node'a zoom.
- **Node config panel standardı:** sağ drawer — Parametreler / I-O şeması / Retry-timeout / Son çalıştırmalar / node-scoped chat.
- **Sürüm diff:** iki workflow versiyonu renkli overlay diff (versioning backend'i mevcut).
- **Copilot dock:** Designer içinde I1 motorlu chat çekmecesi, mevcut canvas'ı bağlam alır.

### K2 🆕 ModelOps Kontrol Merkezi — P0
- Mevcut `ModelOps.tsx`'in kapalı döngü kokpitine dönüşümü.
- **Registry görünümü:** stage rozetleri, sürüm zinciri, drift durumu sinyali, "retrain adayı" bayrağı.
- **Model detay sekmeleri:** Genel bakış (F4 model card) · Performans trendi (J4) · Drift (G1 görselleri) · Deployment'lar (G3/J11) · Lineage (J12'ye link).
- G2 Retrain Policy Editor ve F2 Champion-Challenger ekranı bu merkezin parçasıdır.

### K3 🆕 UI Standartları & Design System — P0 (her yeni ekran için zorunlu)
- **Ortak bileşen kitaplığı:** DataTable, MetricCard, StatusBadge, DiffView, SchemaTree, CodeBlock, ChartContainer.
- **Agent şeffaflık standardı:** uzun işlemlerde adımlı progress; her AI çıktısında "kodu göster / nasıl üretildi" izi.
- **Streaming/optimistic UX:** chat ve run loglarında streaming; TanStack Query invalidation haritası.
- **Durum standardı:** her ekranda tanımlı empty (CTA'lı) / error (eyleme dönük mesaj) / loading.
- **Erişilebilirlik & tema:** canvas klavye navigasyonu, ARIA, renk-körü güvenli durum renkleri, koyu/açık mod.

---

## Yol Haritası

| Faz | Spec'ler |
|---|---|
| **Faz 1 — Kapalı döngü + planner (P0)** | I1 · G1 · G2 · G4 · F2 · E1 · E2 · B2 · A1 · K1 · K2 · K3 |
| **Faz 2 — Genişlik (P1)** | A2 · A4 · B1 · B3 · B5 · B7 · C3 · C4 · D2 · D4 · E3 · E4 · F1 · F6 · G3 · G5 · H1 · H2 · H3 · H4 · H6 · I2 · I3 · J1 · J2 · J3 · J4 · J9 |
| **Faz 3 — Derinlik (P2)** | A3 · A5 · B4 · B6 · B8 · C1 · C2 · C5 · D3 · E6 · E10 · E11 · E12 · F3 · F4 · G6 · G7 · H5 · H7 · I4 · J5 · J6 · J7 · J8 · J10 · J11 · J12 · J13 |
| **Faz 4 — Niş (P3)** | A6 · E5 · E7 · E8 · E9 · F5 |
