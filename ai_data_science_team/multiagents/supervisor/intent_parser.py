import logging
import re
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


def _get_last_human_text(msgs: Sequence[BaseMessage]) -> str:
    """Get the content of the last human message."""
    for m in reversed(msgs or []):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("human", "user"):
            return getattr(m, "content", "") or ""
    return ""


def _has(text: str, *words: str) -> bool:
    """Check if any word is in the text (case-insensitive substring)."""
    lower = text.lower()
    return any(w in lower for w in words)


def _has_word(text: str, *words: str) -> bool:
    """Check if any word appears as a whole word in the text."""
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", lower) for w in words)


def _detect_list_files_intent(text: str) -> bool:
    return _has(
        text,
        "what files",
        "list files",
        "show files",
        "files are in",
        "directory contents",
        "list directory",
        "list only",
    ) and _has(text, "file", "files", "csv", ".csv", "./", "directory", "folder", "data")


def _detect_preview_intent(text: str) -> bool:
    return _has(
        text,
        "head",
        "first 5",
        "first five",
        "preview",
        "show rows",
        "top 5",
        "first five rows",
        "first 5 rows",
    )


def _detect_viz_intent(text: str) -> bool:
    return _has(text, "plot", "chart", "visual", "graph")


def _detect_sql_intent(text: str) -> bool:
    return _has(text, "sql", "query", "database", "schema")


def _detect_clean_intent(text: str) -> bool:
    return _has(text, "clean", "impute", "missing", "null", "na", "outlier")


def _detect_merge_intent(text: str) -> bool:
    merge_signal = _has(text, "merge", "concat", "append", "union", "combine")
    join_signal = _has(text, "join")
    merge_context = (
        _has(text, "with", "between", "together", "into", "using")
        or (" on " in text.lower())
        or _has(text, "dataset", "datasets", "dataframe", "table", "tables")
        or _has(text, "left join", "right join", "inner join", "outer join")
        or _has(text, ".csv", ".parquet", ".xlsx", ".xls", ".json")
    )
    return bool(merge_signal or (join_signal and merge_context))


def _detect_wrangling_intent(text: str) -> bool:
    standardize_column_names = _has(text, "standardize") and _has(
        text,
        "column name",
        "column names",
        "rename column",
        "rename columns",
        "snake case",
        "snake_case",
    )
    return (
        _has(
            text,
            "wrangle",
            "transform",
            "reshape",
            "pivot",
            "melt",
            "rename",
            "format",
        )
        or standardize_column_names
    )


def _detect_eda_intent(text: str) -> bool:
    return _has(text, "describe", "eda", "summary", "correlation", "sweetviz", "missingness")


def _detect_feature_intent(text: str) -> bool:
    feature_action = _has(
        text,
        "encode",
        "one-hot",
        "one hot",
        "label encoding",
        "target encoding",
        "scale",
        "scaling",
        "standardize",
        "normalize",
        "model-ready features",
        "model ready features",
        "feature engineering",
        "feature-engineering",
        "feature engineer",
        "engineer features",
        "create features",
        "build features",
        "make features",
        "generate features",
    )
    return bool(feature_action)


def _detect_model_intent(text: str) -> bool:
    explicit_modeling = _has(
        text,
        "train",
        "automl",
        "fit",
        "tune",
        "cross-validation",
        "cross validation",
        "cv",
        "hyperparameter",
    ) or _has_word(text, "predict")

    ml_context = _has(
        text,
        "classification",
        "classify",
        "regression",
        "xgboost",
        "random forest",
        "lightgbm",
        "catboost",
        "logistic",
        "neural network",
        "deep learning",
    )

    model_word = "model" in text.lower()
    product_model_context = _has(
        text,
        "bike model",
        "car model",
        "product model",
        "model year",
        "phone model",
        "vehicle model",
    ) or (_detect_viz_intent(text) and _has(text, "by model", "per model", "for each model"))

    model_ready_context = _has(
        text, "model-ready", "model ready", "model-ready data", "model ready data"
    )

    ml_signal = explicit_modeling or (ml_context and not _detect_feature_intent(text))

    return bool(
        ml_signal
        or (
            model_word
            and _has(text, "build", "create", "fit", "train", "tune", "predict", "develop")
            and not product_model_context
            and not model_ready_context
        )
    )


def _detect_eval_intent(text: str) -> bool:
    return _has(
        text,
        "evaluate",
        "evaluation",
        "metrics",
        "performance",
        "confusion matrix",
        "roc",
        "auc",
        "precision",
        "recall",
        "f1",
    )


def _detect_load_intent(text: str) -> bool:
    return _has(text, "load", "import", "read csv", "read file", "open file")


def _detect_mlflow_intent(text: str) -> bool:
    return "mlflow" in text.lower()


def _detect_workflow_intent(text: str) -> bool:
    return _has(
        text,
        "workflow",
        "end-to-end",
        "end to end",
        "full pipeline",
        "full data science",
        "data science workflow",
        "ds workflow",
    )


def parse_heuristic_intents(text: str) -> Dict[str, bool]:
    """
    Parse user intent using heuristic rules.

    Returns a dictionary of intent flags.
    """
    lower = text.lower()

    wants_workflow = _detect_workflow_intent(lower)
    wants_list_files = _detect_list_files_intent(lower)
    wants_preview = _detect_preview_intent(lower)
    wants_viz = _detect_viz_intent(lower)
    wants_sql = _detect_sql_intent(lower)
    wants_clean = _detect_clean_intent(lower)
    wants_merge = _detect_merge_intent(lower)
    wants_wrangling = _detect_wrangling_intent(lower)
    wants_eda = _detect_eda_intent(lower)
    wants_feature = _detect_feature_intent(lower)
    wants_model = _detect_model_intent(lower)
    wants_eval = _detect_eval_intent(lower)
    wants_load = _detect_load_intent(lower)
    wants_mlflow = _detect_mlflow_intent(lower)

    mentions_file = (
        (".csv" in lower) or (".parquet" in lower) or (".xlsx" in lower) or ("file" in lower)
    )

    wants_mlflow_tools = wants_mlflow and _has(
        lower,
        "ui",
        "launch",
        "stop",
        "status",
        "list",
        "search",
        "experiment",
        "run",
        "artifact",
        "tracking",
        "uri",
        "registry",
        "registered model",
        "model version",
    )

    wants_mlflow_log = wants_mlflow and _has(
        lower,
        "log",
        "logging",
        "save to mlflow",
        "track",
        "record",
    )

    if wants_workflow:
        wants_clean = True
        wants_eda = True
        wants_viz = True
        wants_model = True
        wants_eval = True

    wants_more_processing = any(
        [
            wants_preview,
            wants_viz,
            wants_sql,
            wants_merge,
            wants_clean,
            wants_wrangling,
            wants_eda,
            wants_feature,
            wants_model,
        ]
    )

    load_only = wants_load and mentions_file and not wants_more_processing

    return {
        "list_files": wants_list_files,
        "preview": wants_preview,
        "merge": wants_merge,
        "viz": wants_viz,
        "sql": wants_sql,
        "clean": wants_clean,
        "wrangle": wants_wrangling,
        "eda": wants_eda,
        "feature": wants_feature,
        "model": wants_model,
        "evaluate": wants_eval,
        "mlflow": wants_mlflow,
        "mlflow_log": wants_mlflow_log,
        "mlflow_tools": wants_mlflow_tools,
        "workflow": wants_workflow,
        "load": wants_load and mentions_file,
        "load_only": load_only,
    }


def parse_llm_intents(
    text: str,
    llm: Any,
    allowed_keys: list[str],
) -> Dict[str, bool]:
    """
    Parse user intent using an LLM for ambiguous cases.
    """
    import json  # noqa: E402, F401

    llm_intents: Dict[str, bool] = {}

    try:
        intent_prompt = (
            "You classify user intent for a data-science assistant router.\n"
            "Return ONLY valid JSON with boolean fields:\n"
            f"{', '.join(allowed_keys)}\n\n"
            "Guidelines:\n"
            "- Set `viz` when the user asks to plot/chart/visualize.\n"
            "- Set `merge` when the user asks to merge/join/concat multiple datasets.\n"
            "- Sweetviz/D-Tale requests are EDA reports: set `eda` true and keep `viz` false unless an additional plot is requested.\n"
            "- Set `model` ONLY for ML modeling (train/AutoML/predict), not product/bike 'model'.\n"
            "- Set `load_only` only when the user only wants data loaded (no preview/eda/viz/etc).\n"
            "- If `mlflow_log` or `mlflow_tools` is true, set `mlflow` true.\n"
            "- If `workflow` is true, you may also set common steps true (clean/eda/viz/model/evaluate).\n"
        )

        intent_llm = llm.bind(temperature=1.0) if hasattr(llm, "bind") else llm
        raw = intent_llm.invoke(
            [
                SystemMessage(content=intent_prompt),
                HumanMessage(content=text),
            ]
        )

        content = getattr(raw, "content", raw)
        if not isinstance(content, str):
            content = str(content)

        try:
            parsed = json.loads(content)
        except Exception as e:
            logger.debug(
                "Failed to parse JSON from LLM response, attempting regex extraction: %s", e
            )
            match_obj = re.search(r"\{.*\}", content, flags=re.DOTALL)
            parsed = json.loads(match_obj.group(0)) if match_obj else {}

        if isinstance(parsed, dict):
            for k in allowed_keys:
                if k in parsed:
                    llm_intents[k] = bool(parsed.get(k))
    except Exception as e:
        logger.warning("Failed to parse LLM intents: %s", e)
        llm_intents = {}

    if llm_intents.get("load_only"):
        llm_intents["load"] = True
    if llm_intents.get("mlflow_log") or llm_intents.get("mlflow_tools"):
        llm_intents["mlflow"] = True
    if llm_intents.get("workflow"):
        llm_intents["clean"] = True
        llm_intents["eda"] = True
        llm_intents["viz"] = True
        llm_intents["model"] = True
        llm_intents["evaluate"] = True

    return llm_intents


def parse_intent(
    msgs: Sequence[BaseMessage],
    *,
    use_llm: bool = False,
    llm: Optional[Any] = None,
) -> Dict[str, bool]:
    """
    Parse user intent from messages.

    Combines heuristic parsing with optional LLM-based parsing for ambiguous cases.
    """
    last_human_text = _get_last_human_text(msgs)
    heuristic_intents = parse_heuristic_intents(last_human_text)

    if not use_llm or llm is None:
        return heuristic_intents

    lower = last_human_text.lower()
    llm_intents = parse_llm_intents(
        last_human_text,
        llm,
        list(heuristic_intents.keys()),
    )

    wants_eda_report = _has(
        lower,
        "sweetviz",
        "dtale",
        "d-tale",
        "exploratory report",
        "profiling report",
        "eda report",
    )
    explicit_plot_request = _has(lower, "plot", "chart", "graph") or _has_word(lower, "visualize")
    if wants_eda_report:
        llm_intents["eda"] = True
    if wants_eda_report and not explicit_plot_request:
        llm_intents["viz"] = False

    feature_action = _detect_feature_intent(lower)
    references_feature_engineered_data = (
        ("feature-engineered" in lower or "feature engineered" in lower)
        and ("data" in lower or "dataset" in lower)
        and ("from" in lower or "using" in lower or "on" in lower)
    ) or (
        ("engineered features" in lower or "engineered feature" in lower)
        and ("from" in lower or "using" in lower or "on" in lower)
    )
    if references_feature_engineered_data and not feature_action:
        llm_intents["feature"] = False

    standardize_column_names = _has(lower, "standardize") and _has(
        lower,
        "column name",
        "column names",
        "rename column",
        "rename columns",
        "snake case",
        "snake_case",
    )
    explicit_wrangling = standardize_column_names or _has(
        lower,
        "wrangle",
        "transform",
        "reshape",
        "pivot",
        "melt",
        "rename",
    )
    explicit_cleaning = _has(
        lower,
        "clean",
        "impute",
        "missing",
        "null",
        "na",
        "outlier",
        "duplicate",
        "deduplicate",
    )
    if feature_action and not explicit_wrangling:
        llm_intents["wrangle"] = False
    if feature_action and not explicit_cleaning:
        llm_intents["clean"] = False
    if llm_intents.get("preview") and not llm_intents.get("workflow"):
        llm_intents["merge"] = False

    return {**heuristic_intents, **llm_intents}
