# Gerçek LLM Test Konfigürasyonu (opencode hesabı)

> **Politika (PM kararı):** Tüm testler gerçek. Mock / stub / RunnableLambda yok.
> LLM testleri gerçek model çağrısı yapar. Model adı kullanıcı tarafından verilecek.

## 1. opencode hesabını bağla

opencode kurulu (`/opt/homebrew/bin/opencode`, v1.1.34). Sağlayıcı kimliği:

```bash
opencode auth login          # sağlayıcı seç (OpenAI / Anthropic / OpenRouter / özel)
opencode auth list           # aktif oturumları gör
```

**Önemli:** platform `langchain-openai` (`ChatOpenAI`) kullanıyor. Sağlayıcın OpenAI-uyumlu
bir API sunuyorsa `OPENAI_API_KEY` + `OPENAI_BASE_URL` yeterli. OpenAI-uyumlu değilse
(ör. Anthropic) ayrıca `langchain-anthropic` gerekecek — o durumda bu doküman güncellenir.

## 2. .env'e yaz (ai_data_science_team/.env)

```bash
OPENAI_API_KEY=<opencode hesabından aldığın API key>
OPENAI_MODEL=<model adı — sen daha sonra vereceksin, örn. gpt-4o-mini>
# Sadece özel endpoint varsa:
# OPENAI_BASE_URL=https://api.provider.example/v1
```

`.env` git'te ignore ediliyor — key asla commit'lenmez.

## 3. Testleri çalıştır

```bash
# Gerçek LLM testleri (key + model ayarlandığında):
uv run pytest tests/llm -m llm -v

# Bağlantıyı doğrula (config hatası varsa FAIL eder):
uv run pytest tests/llm/test_llm_connection.py -v

# Tüm suite (LLM hariç + LLM dahil):
uv run pytest tests/ -m "not llm"          # key gerektirmeyenler
uv run pytest tests/ -m "llm"              # gerçek LLM çağrıları
```

Key tanımlı değilse `tests/llm` testleri **net gerekçeyle skip** eder
("OPENAI_API_KEY tanımlı değil — opencode hesabını .env'e bağla"). Key varsa
testler gerçekten koşar; model/tool hatası **FAIL** olarak yüzeye çıkar (asla
"başarılı ya da dokümante edilmiş hata kabul edilir" deseni yoktur).

## 4. Neler gerçek

| Test | Ne yapıyor |
|---|---|
| `test_llm_connection.py` | Gerçek model çağrısı; non-empty yanıt + model adı doğrulaması |
| `test_eda_tool_calling.py` | 6 eda tool'u; model her tool'u tek tek çağırır (`bind_tools`), platform `data_raw` (InjectedState) enjekte eder, tool çalışır, content/artifact doğrulanır |

## 5. Viz bağımlılıkları (eda harness)

`visualize_missing` → missingno, `generate_sweetviz_report` → sweetviz,
`generate_dtale_report` → dtale. Kurulu (local venv). Taze ortamda:

```bash
uv sync --extra dev --extra viz
```

## 6. Stub test göçü

Mevcut stub tabanlı testler (45 dosya `RunnableLambda`/`_StubModel`, 45 dosya
"documented exception" deseni) modül modül gerçek LLM testleriyle değiştirilir.
Her modül için gerçek test yeşile döndüğünde stub dosyası silinir (sıra: eda →
agent'lar → tools → supervisor). CI'da `llm` marker'lı testler key olmadan
çalışmaz; CI key'li ortamda `-m llm` dahil edilir.
