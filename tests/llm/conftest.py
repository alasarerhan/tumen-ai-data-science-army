"""GERÇEK LLM test altyapısı — mock/stub yok.

Politika (PM kararı):
- Tüm testler gerçek production kodunu çalıştırır.
- LLM testleri gerçek model çağrısı yapar (ChatOpenAI, OPENAI_MODEL).
- RunnableLambda / _StubModel / MagicMock KULLANILMAZ.

Konfigürasyon (.env, ai_data_science_team/.env):
- OPENAI_API_KEY   — opencode hesabından (docs/llm-test-config.md)
- OPENAI_MODEL     — model adı (ör. gpt-4o-mini; kullanıcı daha sonra verecek)
- OPENAI_BASE_URL  — opsiyonel, OpenAI-uyumlu özel endpoint
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Minimal .env yükleyici (dependency'siz)."""
    env_file = _REPO / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def _model_name() -> str:
    return os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"


@pytest.fixture(scope="session")
def llm_model():
    """Gerçek ChatOpenAI — model adı OPENAI_MODEL'den, key OPENAI_API_KEY'den."""
    from langchain_openai import ChatOpenAI

    kwargs = {
        "model": _model_name(),
        "api_key": _api_key() or "not-configured",
        "temperature": 0,
    }
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


@pytest.fixture(scope="session")
def llm_or_skip():
    """Key yoksa net gerekçeyle skip; key varsa test gerçekten koşar."""
    if not _api_key():
        pytest.skip(
            "OPENAI_API_KEY tanımlı değil — opencode hesabını .env'e bağla "
            "(bkz. docs/llm-test-config.md). OPENAI_MODEL model adı bekleniyor."
        )
    return True


@pytest.fixture(scope="session")
def fixture_csv_dir() -> Path:
    return _REPO / "tests" / "fixtures" / "real" / "csv"


@pytest.fixture(scope="session")
def sample_df(fixture_csv_dir):
    """Gerçek fixture CSV → DataFrame (mock değil, tests/fixtures/real/csv/sample_1.csv)."""
    import pandas as pd

    df = pd.read_csv(fixture_csv_dir / "sample_1.csv")
    assert not df.empty, "fixture boş"
    return df


@pytest.fixture(scope="session")
def sample_data_dict(sample_df):
    """data_raw (InjectedState şeması dict bekler) — gerçek DataFrame'den türetilir."""
    return sample_df.to_dict(orient="list")
