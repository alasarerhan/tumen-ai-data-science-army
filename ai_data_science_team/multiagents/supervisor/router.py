from __future__ import annotations

import re
from typing import Any, Sequence

from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.json import parse_json_markdown
from langchain_openai import ChatOpenAI

SUPERVISOR_SYSTEM_PROMPT = """
You are a supervisor managing a data science team with these workers: {subagent_names}.

Each worker has specific tools/capabilities (names are a hint for routing):
- Data_Loader_Tools_Agent: Good for inspecting file folder system, finding files, searching and loading data. Has the following tools: load_file, load_directory, search_files_by_pattern, list_directory_contents/recursive.
- Data_Merge_Agent: Deterministically merges multiple already-loaded datasets (join/concat) based on user/UX configuration. Use for combining datasets into a single modeling table. Must have 2+ datasets loaded/selected.
- Data_Wrangling_Agent: Can work with one or more datasets, performing operations such as joining/merging multiple datasets, reshaping, aggregating, encoding, creating computed features, and ensuring consistent data types. Capabilities: recommend_wrangling_steps, create_data_wrangling_code, execute_data_wrangling_code (transform/rename/format). Must have data loaded/ready.
- Data_Cleaning_Agent: Strong in cleaning data, removing anomalies, and fixing data issues. Capabilities: recommend_cleaning_steps, create_data_cleaner_code, execute_data_cleaner_code (impute/clean). Must have data loaded/ready.
- EDA_Tools_Agent: Strong in exploring data, analysing data, and providing information about the data. Has several powerful tools: describe_dataset, explain_data, visualize_missing, correlation_funnel, sweetviz (use for previews/head/describe). Must have data loaded/ready.
- Data_Visualization_Agent: Can generate Plotly charts based on user-defined instructions or default visualization steps. Must have data loaded/ready.  
- SQL_Database_Agent: Generate a SQL query based on the recommended steps and user instructions. Executes that SQL query against the provided database connection, returning the data results.
- Feature_Engineering_Agent: The agent applies various feature engineering techniques, such as encoding categorical variables, scaling numeric variables, creating interaction terms,and generating polynomial features. Must have data loaded/ready.
- H2O_ML_Agent: A Machine Learning agent that uses H2O's AutoML for training create_h2o_automl_code, execute_h2o_code (AutoML training/eval).
- Model_Evaluation_Agent: Evaluates a trained model on a holdout split and returns standardized metrics + plots (confusion matrix/ROC or residuals).
- MLflow_Logging_Agent: Logs workflow artifacts deterministically to MLflow (tables/figures/metrics) and returns the run id.
- MLflow_Tools_Agent: Can interact and run various tools related to accessing, interacting with, and retrieving information from MLflow. Has tools including: mlflow_search_experiments, mlflow_search_runs, mlflow_create_experiment, mlflow_predict_from_run_id, mlflow_launch_ui, mlflow_stop_ui, mlflow_list_artifacts, mlflow_download_artifacts, mlflow_list_registered_models, mlflow_search_registered_models, mlflow_get_model_version_details, mlflow_get_run_details, mlflow_transition_model_version_stage, mlflow_tracking_info, mlflow_ui_status,

Critical rule: only route to workers when the user explicitly asks for their capabilities. Do not assume next steps.

Routing guidance (explicit intent -> worker):
- Load/import/read file (e.g., "load data/churn_data.csv"): Data_Loader_Tools_Agent ONCE, then FINISH unless more is requested.
- Show first N rows / preview / head / describe: EDA_Tools_Agent then FINISH.
- Plot/chart/visual/graph: Data_Visualization_Agent.
- Merge/join/concat multiple datasets into one: Data_Merge_Agent.
- Clean/impute/wrangle/standardize: Data_Wrangling_Agent or Data_Cleaning_Agent.
- SQL/database/query/tables: SQL_Database_Agent.
- Feature creation/encoding: Feature_Engineering_Agent.
- Train/evaluate model/AutoML: H2O_ML_Agent.
- Evaluate model performance: Model_Evaluation_Agent.
- Log workflow to MLflow: MLflow_Logging_Agent.
- MLflow tracking/registry/UI: MLflow_Tools_Agent.

Rules:
- Track which worker acted last and do NOT select the same worker twice in a row unless explicitly required.
- Prefer tables unless the user explicitly requests charts/models.
- If the user request appears satisfied, respond with FINISH.

Examples:
- "load data/churn_data.csv" -> Data_Loader_Tools_Agent, then FINISH.
- "show the first 5 rows" (data already loaded) -> EDA_Tools_Agent, then FINISH.
- "describe the dataset" -> EDA_Tools_Agent.
- "plot churn by tenure" -> Data_Visualization_Agent.
- "clean missing values" -> Data_Cleaning_Agent.
- "what tables are in the DB?" -> SQL_Database_Agent.
- "engineer one-hot features for churn" -> Feature_Engineering_Agent.
- "train a model for Churn" -> H2O_ML_Agent.
- "list mlflow experiments" -> MLflow_Tools_Agent.
"""


def build_route_options(subagent_names: Sequence[str]) -> list[str]:
    return ["FINISH", *subagent_names]


def build_route_function_def(route_options: Sequence[str]) -> dict[str, Any]:
    return {
        "name": "route",
        "description": "Select the next worker.",
        "parameters": {
            "title": "route_schema",
            "type": "object",
            "properties": {
                "next": {
                    "title": "Next",
                    "anyOf": [{"enum": list(route_options)}],
                }
            },
            "required": ["next"],
        },
    }


def build_supervisor_prompt(
    route_options: Sequence[str],
    subagent_names: Sequence[str],
):
    return ChatPromptTemplate.from_messages(
        [
            ("system", SUPERVISOR_SYSTEM_PROMPT),
            ("system", "Last worker: {last_worker}"),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next? Or FINISH? "
                "Respond with ONLY one of: {route_options}",
            ),
        ]
    ).partial(
        route_options=str(list(route_options)),
        subagent_names=", ".join(subagent_names),
    )


def parse_router_output(text: str, route_options: Sequence[str]) -> dict[str, str]:
    """Parse router output into ``{\"next\": <route_option>}``."""
    cleaned = (text or "").strip()
    if not cleaned:
        return {"next": "FINISH"}

    try:
        parsed = parse_json_markdown(cleaned)
        if isinstance(parsed, dict):
            nxt = parsed.get("next")
            if isinstance(nxt, str) and nxt in route_options:
                return {"next": nxt}
    except Exception:
        pass

    lower = cleaned.lower()
    for option in route_options:
        if option.lower() in lower:
            return {"next": option}

    try:
        match = re.search(
            r"(?:next|route)\s*[:=]\s*([A-Za-z0-9_]+)",
            cleaned,
            flags=re.I,
        )
        if match:
            candidate = match.group(1).strip()
            for option in route_options:
                if candidate == option or candidate.lower() == option.lower():
                    return {"next": option}
    except Exception:
        pass

    return {"next": "FINISH"}


def build_supervisor_chain(llm: Any, route_options: Sequence[str], subagent_names: Sequence[str]):
    prompt = build_supervisor_prompt(route_options, subagent_names)
    function_def = build_route_function_def(route_options)
    if isinstance(llm, ChatOpenAI):
        return (
            prompt
            | llm.bind(functions=[function_def], function_call={"name": "route"})
            | JsonOutputFunctionsParser()
        )
    return (
        prompt
        | llm
        | StrOutputParser()
        | RunnableLambda(lambda text: parse_router_output(text, route_options))
    )
