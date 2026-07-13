# B1 — Data Profiling Genişletmesi

## 1. Amaç & Kullanıcı Hikâyeleri

**Kim:** İlk kez bir kaynağa bağlanan data scientist; I2 katalog sayfasını doldurmak isteyen platform admini.

**Neden:** Mevcut `pandas_profiling` çıktısı rapor olarak verilir ama platform kataloğuna girmez, PII için işaretlenmez, "katalog kolonu" olarak diğer spec'lerde kullanılamaz. B1'in amacı profiling → katalog entegrasyonunu sağlamak.

Kabul senaryoları:
1. Kullanıcı yeni bir kaynağa bağlandığında "profili oluştur" tıklar; her kolon için min/max/ortalama/kardinalite/eksik yüzde/PII sinyali hesaplanıp kataloğa yazılır.
2. I2'deki kolon kartı "istatistik" sekmesinde profiling çıktısı görünür (dağılım mini grafiği, top-N kategorik, sayısal özet).
3. Profil çıktısı "şema değişti mi" drift için baseline oluşturur (G1/J13 ile paylaşılır).
4. Toplu profil: birden çok tablo seç → her birini arka arkanda profil → katalog toplu güncellenir.

## 2. Backend Tasarımı

**Agent/Servis:** `ai_data_science_team/agents/data_profiling_agent.py`; deterministic çekirdek `ai_data_science_team/tools/profiling.py`. Streaming büyük tablolar için.

**Node tipi:** `data.profile`:
```json
{
  "type": "data.profile",
  "config": {
    "dataset_ref": "datawarehouse.public.users_v3",
    "scope": "full|sample",
    "sample_size": 50000,
    "include_pii_scan": true
  }
}
```

**API endpoint'leri:**
- `POST /datasets/{id}/profile` — başlatır async; `202 + run_id`.
- `GET /datasets/{id}/profile/{run_id}` — sonuç + status.
- `GET /datasets/{id}/columns/{col}/stats` — tek kolon kartı için.

**Veri modeli:** `column_profiles` (dataset_id, column, run_id, dtype, n_unique, null_pct, mean/median/std, top_values_json, hist_buckets_json, pii_signal). Tablo başına en son profil `current = true` flag.

**Hata durumları:** 100MB+ dataset → `scope=sample` otomatik öner · boolean/tarih kolonlarında mean uyarısı · PII scan "exclude_pii=true" setle devre dışı bırakılabilir.

## 3. UI Tasarımı

**Konum:** I2 Data Catalog ekranında "Profil oluştur" aksiyonu; kolon kartında "İstatistik" sekmesi.

Akış:
1. Dataset seç → "Yeni profil" butonu → job başlar, progress stepper'ı gösterir (scan→describe→PII→write).
2. Profil tamamlandığında "yeni badge" bildirimi.
3. Kolon kartı: dtype/eksik %/kardinalite/son değerler/dağılım sparkline + PII rozeti.
4. Toplu profil: dataset listesi → çoklu seçim → "Tümünü profille".

**Durumlar:** loading — sparkline skeleton; error — kaynak bağlantı koparsa retry + log; empty — ilk açılışta "henüz profil yok" CTA.

**Entegrasyon:** I2'nin `Catalog.tsx`'ine `ProfileBadge` eklenir. `Sparkline` (K3) kullanılır.

## 4. Bağımlılıklar

- B5 (PII Detection): `pii_signal` alanı B5 sonuçlarından gelir.
- B7 (Data Ingestion): profil yenileme periyodu ingestion'a bağlanır (J3 trigger'ı).
- I2 (Data Catalog): kolon istatistikleri katalog alanlarına map'lenir.
- G1 (Auto Drift): profili baseline olarak kullanır.
- J13 (Data Diff): iki profilin farkı.
- Backend: `pandas`, `great_expectations`, `pydeepl`, `presidio`.

## 5. Kapsam Dışı

- Streaming profili (debezium/CDV) — sadece batch profile'lar.
- Yapısal olmayan veri (PDF/IMG) — görüntü için E5.
- ML-tabanlı veri kalite skorlaması — B2'de (validation kapısı).

## 6. Test & Definition of Done

**Birim testleri:**
- Sayısal kolon: mean/median/std doğru hesaplanır.
- Tarih kolonu: dtype çıkarımı doğru.
- PII regex 5 fake isimde signal=high.

**E2E:** Snowflake dataset profili → I2'de görünür → G1 baseline olarak set edilir.

**Definition of Done:**
- Reaktif tool: `profile_create`, `profile_get`, `profile_column`.
- PII sinyali B5 ile entegre.
- I2 ekranı kolon kartında istatistik sekmesi aktif.
- Büyük dataset (10M satır) sample fallback ile çalışır.
- Spec durumu ✍️ → 🚧 → ✅.
