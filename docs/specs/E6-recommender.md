# E6 — Recommender System

## 1. Amaç & Kullanıcı Hikâyeleri

Kullanıcı–ürün etkileşim verisinden (implicit/explicit) öneri modeli eğitmek, offline metriklerle (recall@k, NDCG@k) değerlendirmek ve toplu öneri üretmek.

- **DS olarak**, sipariş tablomdan (user_id, item_id, quantity) ALS tabanlı bir collaborative filtering modeli eğitmek istiyorum ki e-ticaret önerilerini otomatikleştireyim.
- **Ürün yöneticisi olarak**, örnek bir kullanıcı seçip önerilen ürün listesini ve "neden önerildi" açıklamasını görmek istiyorum ki modeli işletmeye anlatabileyim.
- **ML engineer olarak**, popülerlik baseline'ına karşı recall@10 lift'ini görmek istiyorum ki modelin gerçekten değer ürettiğini doğrulayayım.

Kabul senaryosu: etkileşim dataset'i → kolon eşleme (user/item/rating) → ALS eğitimi → leave-last-out değerlendirme → recall@k/NDCG tablosu → örnek kullanıcı önizlemesi → batch öneri artifact'ı.

## 2. Backend Tasarımı

### Agent
- **Sınıf:** `RecommenderAgent` — yeni dosya `ai_data_science_team/ml_agents/recommender_agent.py` (`ClusteringAgent` deseninde ReAct agent).
- Tool'lar (`ai_data_science_team/tools/recommender.py`): `build_interaction_matrix`, `train_als` (implicit), `train_item_knn` (content-based, TF-IDF item feature'ları), `evaluate_topk` (recall@k, NDCG@k, coverage), `recommend_for_users`, `explain_recommendation` (benzer item/komşu kanıtı).

### Node tipi: `recsys.train`
```json
{
  "type": "recsys.train",
  "label": "Recommender Trainer",
  "category": "Modeling",
  "inputs": [
    {"name": "interactions", "artifact_type": "dataset", "required": true},
    {"name": "item_features", "artifact_type": "dataset", "required": false}
  ],
  "outputs": [
    {"name": "model", "artifact_type": "model", "required": true},
    {"name": "metrics", "artifact_type": "metrics", "required": true},
    {"name": "recommendations", "artifact_type": "dataset", "required": false}
  ],
  "ui": {"icon": "thumbs-up", "color": "orange", "config": [
    {"key": "algorithm", "type": "select", "options": ["als", "bpr", "item_knn", "popularity_baseline"], "required": true},
    {"key": "user_column", "type": "string", "required": true},
    {"key": "item_column", "type": "string", "required": true},
    {"key": "rating_column", "type": "string", "required": false},
    {"key": "top_k", "type": "number", "required": false}
  ]},
  "timeout_seconds": 3600,
  "retry_policy": {"max_attempts": 1, "backoff_seconds": 30},
  "resources": {"class": "cpu_large"}
}
```
Executor: `_execute_recsys_train` → `get_default_node_executors()`.

### API endpoint'leri
- `POST /api/recsys/models/{model_id}/recommend` — body: `{"user_ids": [...], "k": 10}` → öneri listeleri.
- `GET /api/recsys/models/{model_id}/preview?user_id=` — tek kullanıcı önizleme: geçmiş etkileşimler + öneriler + açıklama.
- `GET /api/recsys/models/{model_id}/metrics` — recall@k/NDCG@k, baseline karşılaştırması.

### Veri modeli
- Model artifact'ı: pickle (implicit ALS matrisleri) + `id_maps.json` (user/item index eşlemesi). Yeni tablo gerekmez; mevcut model registry kullanılır. Metrics artifact şeması: `{"recall_at_10": .., "ndcg_at_10": .., "baseline_recall_at_10": .., "coverage": ..}`.

### Hata durumları
- user/item kolonu dataset'te yok → config validasyon hatası (run başlamadan).
- Etkileşim matrisi çok seyrek (kullanıcı başına < 2 etkileşim medyanı) → uyarı + popularity baseline önerisi.
- Cold-start kullanıcı sorgusu → popülerlik fallback + `"fallback": true` bayrağı.

## 3. UI Tasarımı

### Bileşenler
- `RecsysConfigForm` — node config panelinde algoritma + kolon eşleme dropdown'ları (dataset şemasından beslenir).
- `TopKMetricCard` — recall@k/NDCG@k kartları + baseline lift oku (yeşil/kırmızı).
- `UserRecommendationPreview` — sol: kullanıcının geçmiş etkileşimleri (tablo); sağ: önerilen K item kartı (skor barı + "neden" tooltip'i); üstte kullanıcı arama/seçme combobox'ı.
- `CoverageChart` — katalog kapsama donut'ı (ECharts).

### Akış
1. Designer'da `recsys.train` node config'i doldurulur → run.
2. Run detayında "Öneri Önizleme" sekmesi: kullanıcı seç → önizleme çağrısı → liste render.
3. "Batch öneri üret" butonu → `recommendations` dataset artifact'ı → indirilebilir/hedef tabloya yazılabilir (G4 ile).

### Durumlar
- **Loading:** önizleme listesinde skeleton satırlar.
- **Empty:** model henüz eğitilmediyse "Önce recsys.train node'u çalıştırın" CTA'sı; cold-start kullanıcıda "Bu kullanıcı için geçmiş yok — popüler ürünler gösteriliyor" banner'ı.
- **Error:** kolon eşleme hatasında hangi kolonun eksik olduğu inline gösterilir.

### Entegrasyon
- WorkflowDesigner paleti (Modeling kategorisi); ModelOps model detayına "Öneriler" sekmesi; I3 leaderboard'unda recall@k kolonu.

## 4. Bağımlılıklar

- **Spec:** E1, G4 (batch scoring), I3, K3.
- **Kütüphaneler:** `implicit` (ALS/BPR), `scipy.sparse`, `scikit-learn` (TF-IDF/kNN); alternatif değerlendirildi: `surprise` (explicit rating senaryosu için opsiyonel).
- **Kod:** node catalog/executor servisleri, `_load_latest_dataframe`, artifact helper'ları.

## 5. Kapsam Dışı

- Gerçek zamanlı / online öneri servisi (G3 kapsamına ertelendi).
- Deep learning tabanlı recsys (two-tower, sequence modelleri).
- Bandit/online learning, yeniden sıralama (re-ranking) ve iş kuralı motoru.
- A/B test entegrasyonu (A1 ile ayrı spec'te birleşir).

## 6. Test & Definition of Done

- **Birim:** `build_interaction_matrix` id eşlemelerini doğru kurar; `evaluate_topk` bilinen küçük örnekte elle hesaplanan recall@2 ile eşleşir; cold-start fallback popüler item döner.
- **E2E:** MovieLens-mini benzeri fixture ile workflow run → metrics artifact'ında `recall_at_10 > baseline_recall_at_10`; önizleme endpoint'i 200 + K öneri döner.
- **Hata testi:** eksik `item_column` config'i validasyonda yakalanır.
- **DoD:** node katalogda, UI önizleme sekmesi çalışır, baseline karşılaştırması metrik kartında görünür, batch öneri artifact'ı üretilir, testler CI'da yeşil.
