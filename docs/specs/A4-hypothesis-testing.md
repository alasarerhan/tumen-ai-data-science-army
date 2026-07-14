# A4 — Hypothesis Testing Danışmanı

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** İstatistik bilgisi sınırlı analist/iş kullanıcısı; hızlı doğrulama isteyen data scientist.
**Neden:** "Bu iki bölgenin satış ortalaması gerçekten farklı mı?" gibi serbest soruları doğru istatistiksel teste yönlendirmek; varsayım kontrollerini otomatik yapmak; sonucu sade dilde, etki büyüklüğüyle birlikte açıklamak.

Kabul senaryoları:
1. Kullanıcı chat'te "premium ve free kullanıcıların oturum süresi farklı mı?" yazar; agent kolonları tespit eder, normallik (Shapiro/Anderson) + varyans homojenliği (Levene) kontrol eder, Welch t veya Mann-Whitney seçer ve inline sonuç kartı döner.
2. İkiden fazla grupta (4 bölge) ANOVA/Kruskal-Wallis + post-hoc (Tukey/Dunn) otomatik zincirlenir.
3. İki kategorik değişken sorulduğunda chi-square (beklenen frekans < 5 hücre çoksa Fisher exact) seçilir ve Cramér's V raporlanır.
4. Sonuç kartında "neden bu test" açıklaması, p-değeri, etki büyüklüğü (Cohen's d / r / V) ve sade dilde yorum ("fark istatistiksel olarak anlamlı ama etki küçük") yer alır.

## 2. Backend Tasarımı

**Agent:** yeni `ai_data_science_team/agents/hypothesis_testing_agent.py` — `make_hypothesis_testing_agent(llm)`; akış: NL soru → kolon/grup eşleme (LLM) → veri tipi tespiti → varsayım kontrolleri (deterministik) → test seçim karar ağacı (deterministik, LLM değil) → test koşumu → LLM ile sade dilde anlatı. Karar ağacı `ai_data_science_team/tools/stat_tests.py` içinde test edilebilir saf fonksiyon.

**Node tipi:** `stats.hypothesis_test` (chat-first ama pipeline'da da kullanılabilir):

```json
{
  "type": "stats.hypothesis_test",
  "inputs": [{"name": "dataset", "artifact_type": "dataset", "required": true}],
  "outputs": [{"name": "test_result", "artifact_type": "stat_test_report", "required": true}],
  "config": {
    "question": "premium ve free kullanıcıların oturum süresi farklı mı?",
    "target_column": "session_minutes",
    "group_column": "plan",
    "alpha": 0.05,
    "alternative": "two-sided"
  }
}
```

**Artifact şeması (`stat_test_report`):** `assumptions: [{name, test, statistic, p_value, passed}]`, `selected_test: {name, reason}`, `result: {statistic, p_value, effect_size: {name, value, interpretation}}`, `posthoc: [...]|null`, `narrative: {plain_tr, caveats}`.

**API endpoint'leri** (`platform_api/routes/` altına `stats.py`):
- `POST /stats/hypothesis-test` — `{dataset_ref, question?, target_column?, group_column?, alpha}` → senkron/kısa async; soru verilirse kolon eşleme LLM ile.
- `GET /stats/tests/{id}` — geçmiş sonuç.
- Chat entegrasyonu: `platform_api/routes/chat.py` üzerinden `multiagents/chat_workspace.py` ve `multiagents/supervisor_ds_team.py`'e yeni agent'ın kayıt edilmesi (supervisor routing'ine "istatistiksel test" niyeti eklenir).

**Veri modeli:** `stat_tests` tablosu: `id, dataset_ref, question, config_json, result_artifact_id, created_by, created_at` (chat geçmişinden bağımsız erişilebilirlik için).

**Hata durumları:** kolon eşlenemedi → 200 + `clarification_needed` (chat'te takip sorusu) · grup başına n<3 (422, "test için yetersiz veri") · hedef kolon tamamı NaN (400) · LLM anlatı hatası → deterministik sonuç yine döner, `narrative=null`.

## 3. UI Tasarımı

**Konum:** chat-first — `frontend/src/app/screens/AIWorkspace.tsx` içinde yeni inline mesaj kartı bileşeni `StatTestResultCard`.

Akış:
1. Kullanıcı serbest soru yazar; supervisor bu agent'a yönlendirir.
2. Kolon eşleme belirsizse chat'te inline seçim widget'ı (kolon dropdown'u) çıkar.
3. Sonuç kartı: başlıkta test adı + "neden seçildi" genişletilebilir satırı; p-değeri ve etki büyüklüğü rozetleri (renk: anlamlı/yeşil, değil/gri); varsayım kontrol listesi (✓/✗); sade dilde yorum paragrafı; "kodu göster" izi (K3 şeffaflık standardı).
4. Kart aksiyonları: "dataset'te grupları görselleştir" (box plot), "rapora ekle".

**Durumlar:** loading — kartın skeleton hali + "varsayımlar kontrol ediliyor" adımı; empty — yok (chat akışı); error — kart içinde eyleme dönük mesaj + tekrar dene.

**Entegrasyon:** AIWorkspace mesaj renderer'ına yeni artifact tipi; RunDetail'de `stat_test_report` görselleştirici; Designer paletinde node.

## 4. Bağımlılıklar
- **Spec:** (supervisor routing genişlemesi ile uyum), A1 (etki büyüklüğü/CI bileşenleri paylaşılır).
- **Python:** `scipy.stats` (shapiro, levene, ttest_ind, mannwhitneyu, f_oneway, kruskal, chi2_contingency, fisher_exact), `statsmodels.stats.multicomp` (pairwise_tukeyhsd), `scikit-posthocs` (Dunn), `pingouin` (opsiyonel, etki büyüklükleri).
- **Kod noktaları:** `ai_data_science_team/multiagents/supervisor_ds_team.py`, `ai_data_science_team/multiagents/chat_workspace.py`, `platform_api/routes/chat.py`, `frontend/src/app/screens/AIWorkspace.tsx`.
## 5. Kapsam Dışı

- Deney analizi (A1'in işi; agent A/B sorusu algılarsa A1'e yönlendirme mesajı verir).
- Bayesian testler (A3), nedensel iddialar (A5) — anlatı katmanı korelasyon≠nedensellik uyarısı verir.
- Zaman serisi testleri (stationarity vb.) ve çok değişkenli testler (MANOVA).

## 6. Test & Definition of Done

Test senaryoları:
- Birim (karar ağacı): normal+eşit varyans→Student t; normal+eşit olmayan→Welch; normal değil→Mann-Whitney; 3+ grup normal→ANOVA+Tukey; değil→Kruskal+Dunn; 2 kategorik + küçük beklenen frekans→Fisher. Her dal fixture dataset'le doğrulanır.
- Birim: etki büyüklüğü hesapları (Cohen's d, Cramér's V) referans değerlerle eşleşir.
- Birim: kolon eşleme belirsizliğinde `clarification_needed` döner.
- E2E: chat'te soru → inline kart render; varsayım listesi ve "neden bu test" açılır satırı çalışır.

DoD checklist:
- [ ] Test seçim karar ağacı %100 birim test kapsamında (LLM'siz)
- [ ] Supervisor routing yeni agent'ı doğru niyette tetikliyor
- [ ] `stats.hypothesis_test` node kataloğa/executor'a eklendi
- [ ] StatTestResultCard chat'te ve RunDetail'de render oluyor
- [ ] Clarification (kolon seçim) akışı e2e testli
- [ ] "Kodu göster" şeffaflık izi mevcut
