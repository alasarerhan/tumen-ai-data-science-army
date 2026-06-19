# Operations — Persistence Policy

## Karar (2026-06-19)

**Persistence seçeneği: A — Diskte kalıcı, repo'ya commit edilmez.**

### Neden A?

Bu kişisel bir uygulama — başka clone olmayacak. Ama:

- **DB hassas veri içerir** → asla commit edilmemeli (PII, API key riski)
- **Log'lar şu an debug sprey** ama production için gerekli olacak → diskte tutulur, versiyonlanmaz
- **Repo şişmesin** → büyüyen DB / log dosyaları ignore

### Bu politika ne demek?

| Katman | Davranış |
|---|---|
| Disk üzerinde | DB + log dosyaları **kalıcı** (silinmez, silinmesi istenmez) |
| `.gitignore` | `*.log`, `logs/`, `*.db`, `db.sqlite3` vb. **ignore edilir** |
| Git history | Commit'lenmez, push edilmez, remote'a gitmez |
| Yeni clone | Boş başlar; DB ilk çalıştırmada oluşur, log'lar runtime'da dolar |

### Persistence haritası (güncel)

Bu repo için bilinçli kayıt politikası:

| Tür | Konum | Politika |
|---|---|---|
| `*.log` | repo içi (root + alt klasörler) | **KALICI** — application log'ları, operasyonel iz |
| `log/` klasörü | repo root | **KALICI** — session/runtime log çıktısı |
| `*.db`, `*.sqlite`, `*.sqlite3` | repo içi | **KALICI** — uygulama veritabanları (SQLite vb.) |

## Silinebilir / geçici dosyalar

Yalnızca aşağıdaki kalıplar geçici sayılır ve silinebilir:

| Pattern | Neden geçici |
|---|---|
| `*.tmp` | Geçici yazım / atomic rename öncesi |
| `*.bak` | Yedek / eski sürüm |
| `*.swp`, `*~` | Editör geçici dosyaları (vim vb.) |
| `*.db-journal`, `*.db-wal`, `*.db-shm` | SQLite WAL yan ürünleri (DB kapanınca silinir) |
| `.DS_Store`, `Thumbs.db` | OS metadata artıkları |
| IDE metadata | `.idea/`, `.vscode/` (kişiye özel, opsiyonel) |

**DB WAL/journal dosyaları normalde DB açıkken oluşur; SQLite kapandığında `*.db`'ye geri birleşir.** Eğer `*.db` yok ama `*.db-wal` varsa, orphan WAL'dir ve silinebilir.

## Commit öncesi kontrol

Bir temizlik commit'i atmadan önce şu kalıpların taranması önerilir:

```
**/*.tmp
**/*.bak
**/*.swp
**/*~
**/.DS_Store
**/Thumbs.db
```

## Neden bu politika?

- **Log'lar operasyonel iz taşır**: incident triage, audit, debug için gerekli.
- **DB'ler uygulama state'idir**: kullanıcı verisi, konfigürasyon, cache. Silinmemeli.
- **Geçici dosyalar gerçekten geçicidir**: işleri bittiğinde silinmesi beklenir; kalmışlarsa artıktır.

## Değişiklik günlüğü

- 2026-06-19 — İlk politika belgesi. **C seçeneği kabul edildi → A'ya revize edildi**: kişisel repo + hassas DB gerçeği nedeniyle commit politikası korundu, persistence haritası disk üzerinde tutulacak şekilde güncellendi.