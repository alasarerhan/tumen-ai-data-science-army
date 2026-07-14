from __future__ import annotations



import logging

logger = logging.getLogger(__name__)
from typing import Sequence, Optional, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from IPython.display import Markdown
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, END
from langgraph.types import Checkpointer
from langgraph.graph.message import add_messages

from ai_data_science_team.multiagents.supervisor import (
    SupervisorDSState,
    DATASET_REGISTRY_MAX,
    _clean_messages,
    _get_last_human_text,
    append_agent_feedback,
    append_error_message,
    build_route_options,
    build_supervisor_chain,
    ensure_dataset_registry,
    ensure_df,
    execute_merge_plan,
    format_dataset_with_llm,
    format_listing_with_llm,
    format_result_with_llm,
    get_active_data,
    is_empty_df,
    collect_loader_errors,
    extract_loader_artifact_results,
    infer_requested_load_labels,
    merge_messages,
    normalize_loader_artifacts,
    parse_intent,
    register_dataset,
    resolve_selected_dataset_ids,
    register_python_transform_dataset,
    shape_of,
    sha256_text,
    summarize_directory_listing,
    summarize_loaded_dataset,
    summarize_loader_failure,
    summarize_multi_loaded_datasets,
    summarize_multiple_loaded_files,
    tag_messages,
    trim_messages,
    truncate_text,
    available_datasets_lines,
)



# L2 split: node factories are imported from per-file modules under
# ``nodes/``.  Each factory takes a NodeDeps dataclass (defined in its
# module) that holds the closure dependencies the node used to capture
# in the original monolith.
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.viz import (
    VizNodeDeps,
    make_node_viz,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.loader import (
    LoaderNodeDeps,
    make_node_loader,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.merge import (
    MergeNodeDeps,
    make_node_merge,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.wrangling import (
    WranglingNodeDeps,
    make_node_wrangling,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.cleaning import (
    CleaningNodeDeps,
    make_node_cleaning,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.sql import (
    SqlNodeDeps,
    make_node_sql,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.eda import (
    EdaNodeDeps,
    make_node_eda,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.fe import (
    FeNodeDeps,
    make_node_fe,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.h2o import (
    H2oNodeDeps,
    make_node_h2o,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.mlflow import (
    MlflowNodeDeps,
    make_node_mlflow,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.eval import (
    EvalNodeDeps,
    make_node_eval,
)
from ai_data_science_team.multiagents.supervisor_ds_team.nodes.mlflow_log import (
    MlflowLogNodeDeps,
    make_node_mlflow_log,
)

# Bind the closure-derived helpers (used by inline code in the
# orchestrator body).  Each helper is reachable through deps.<name>.
def make_supervisor_ds_team(
    model: Any,
    data_loader_agent,
    data_wrangling_agent,
    data_cleaning_agent,
    eda_tools_agent,
    data_visualization_agent,
    sql_database_agent,
    feature_engineering_agent,
    h2o_ml_agent,
    mlflow_tools_agent,
    model_evaluation_agent,
    workflow_planner_agent=None,
    checkpointer: Optional[Checkpointer] = None,
    temperature: float = 1.0,
):
    """
    Build a supervisor-led data science team using existing sub-agents.

    Args:
        model: LLM (or model name) for the supervisor router.
        workflow_planner_agent: WorkflowPlannerAgent instance (optional planning for multi-step prompts).
        data_loader_agent: DataLoaderToolsAgent instance.
        data_wrangling_agent: DataWranglingAgent instance.
        data_cleaning_agent: DataCleaningAgent instance.
        eda_tools_agent: EDAToolsAgent instance.
        data_visualization_agent: DataVisualizationAgent instance.
        sql_database_agent: SQLDatabaseAgent instance.
        feature_engineering_agent: FeatureEngineeringAgent instance.
        h2o_ml_agent: H2OMLAgent instance.
        model_evaluation_agent: ModelEvaluationAgent instance.
        mlflow_tools_agent: MLflowToolsAgent instance.
        checkpointer: optional LangGraph checkpointer.
        temperature: supervisor routing temperature.
    """

    subagent_names = [
        "Data_Loader_Tools_Agent",
        "Data_Merge_Agent",
        "Data_Wrangling_Agent",
        "Data_Cleaning_Agent",
        "EDA_Tools_Agent",
        "Data_Visualization_Agent",
        "SQL_Database_Agent",
        "Feature_Engineering_Agent",
        "H2O_ML_Agent",
        "Model_Evaluation_Agent",
        "MLflow_Logging_Agent",
        "MLflow_Tools_Agent",
    ]

    def _openai_requires_responses(model_name: str | None) -> bool:
        model_name = model_name.strip().lower() if isinstance(model_name, str) else ""
        if not model_name:
            return False
        if "codex" in model_name:
            return True
        return model_name in {"gpt-5.1-codex-mini"}

    if isinstance(model, str):
        llm_kwargs: dict[str, object] = {"model": model, "temperature": temperature}
        if _openai_requires_responses(model):
            llm_kwargs["use_responses_api"] = True
            llm_kwargs["output_version"] = "responses/v1"
        llm = ChatOpenAI(**llm_kwargs)  # type: ignore[arg-type]
    else:
        llm = model
        # Best-effort: allow callers to pass an already-configured LLM
        try:
            llm.temperature = temperature
        except Exception:
            pass

    route_options = build_route_options(subagent_names)
    supervisor_chain = build_supervisor_chain(llm, route_options, subagent_names)

    _get_last_human = _get_last_human_text

    def _suggest_next_worker(
        state: SupervisorDSState, clean_msgs: Sequence[BaseMessage]
    ):
        """
        Disabled LLM hinting to keep routing deterministic.
        """
        return None

    def supervisor_node(state: SupervisorDSState):
        logger.info("---SUPERVISOR---")
        clean_msgs = _clean_messages(state.get("messages", []))
        # Hydrate cached datasets from artifacts for stateless reuse across calls.
        hydrated: dict[str, Any] = {}
        artifacts = state.get("artifacts") or {}
        data_cleaned = state.get("data_cleaned")
        if data_cleaned is None and isinstance(artifacts.get("data_cleaning"), dict):
            data_cleaned = artifacts.get("data_cleaning")
            hydrated["data_cleaned"] = data_cleaned
        data_wrangled = state.get("data_wrangled")
        if data_wrangled is None and isinstance(artifacts.get("data_wrangling"), dict):
            data_wrangled = artifacts.get("data_wrangling")
            hydrated["data_wrangled"] = data_wrangled
        data_sql = state.get("data_sql")
        sql_art = artifacts.get("sql") if isinstance(artifacts, dict) else None
        if (
            data_sql is None
            and isinstance(sql_art, dict)
            and sql_art.get("data_sql") is not None
        ):
            data_sql = sql_art.get("data_sql")
            hydrated["data_sql"] = data_sql
        feature_data = state.get("feature_data")
        fe_art = (
            artifacts.get("feature_engineering") if isinstance(artifacts, dict) else None
        )
        if (
            feature_data is None
            and isinstance(fe_art, dict)
            and fe_art.get("data_engineered") is not None
        ):
            feature_data = fe_art.get("data_engineered")
            hydrated["feature_data"] = feature_data

        if hydrated:
            state = {**state, **hydrated}  # type: ignore[typeddict-item]
        base_update = hydrated
        # Ensure every message has an ID so per-request step tracking is reliable even
        # when upstream callers don't set message IDs (e.g., Streamlit chat history).
        try:
            clean_msgs = add_messages([], clean_msgs)  # type: ignore[arg-type,assignment]
        except Exception:
            pass
        cfg = (state.get("artifacts") or {}).get("config") or {}
        use_llm_intent_parser = (
            bool(cfg.get("use_llm_intent_parser")) if isinstance(cfg, dict) else False
        )
        intents = parse_intent(clean_msgs, use_llm=use_llm_intent_parser, llm=llm)
        proactive_mode = (
            bool(cfg.get("proactive_workflow_mode")) if isinstance(cfg, dict) else False
        )

        # Track per-user-request steps (within the current user message) to support
        # deterministic sequencing for multi-step prompts.
        last_human_msg = None
        for m in reversed(clean_msgs or []):
            role = getattr(m, "role", getattr(m, "type", None))
            if role in ("human", "user"):
                last_human_msg = m
                break
        current_request_id = (
            getattr(last_human_msg, "id", None) if last_human_msg else None
        )

        handled_request_id = state.get("handled_request_id")
        handled_steps: dict[str, bool] = dict(state.get("handled_steps") or {})
        attempted_steps: dict[str, bool] = dict(state.get("attempted_steps") or {})
        is_new_request = (
            current_request_id is not None and current_request_id != handled_request_id
        )
        if is_new_request:
            handled_request_id = current_request_id
            handled_steps = {}
            attempted_steps = {}
            # Reset workflow plan per user request
            state_plan_req = None
            state_plan = None
        else:
            state_plan_req = state.get("workflow_plan_request_id")
            state_plan = state.get("workflow_plan")

        # Infer active dataset if not explicitly tracked yet
        active_data_key = state.get("active_data_key")
        if active_data_key is None:
            if state.get("data_cleaned") is not None:
                active_data_key = "data_cleaned"
            elif state.get("data_wrangled") is not None:
                active_data_key = "data_wrangled"
            elif state.get("data_sql") is not None:
                active_data_key = "data_sql"
            elif state.get("feature_data") is not None:
                active_data_key = "feature_data"
            elif state.get("data_raw") is not None:
                active_data_key = "data_raw"

        datasets, active_dataset_id = _ensure_dataset_registry(state)
        state_with_datasets: dict = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "active_data_key": active_data_key,
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }

        # Handle explicit dataset switching requests (no agent needed).
        last_human_text = _get_last_human(clean_msgs)
        requested_dataset_id = None
        try:
            import re

            lower = (last_human_text or "").lower()
            wants_switch = any(
                k in lower
                for k in (
                    "use dataset",
                    "switch dataset",
                    "set dataset",
                    "use the dataset",
                    "switch to dataset",
                )
            )
            if wants_switch and isinstance(datasets, dict) and datasets:
                reobj = re.search(r"\\bdataset\\b\\s*[:#]?\\s*([a-zA-Z0-9_\\-]+)", lower)
                token = (reobj.group(1) if reobj else "").strip()
                if token.isdigit():
                    ordered = sorted(
                        datasets.items(),
                        key=lambda kv: float(kv[1].get("created_ts") or 0.0)
                        if isinstance(kv[1], dict)
                        else 0.0,
                        reverse=True,
                    )
                    idx = int(token) - 1
                    if 0 <= idx < len(ordered):
                        requested_dataset_id = ordered[idx][0]
                elif token and token in datasets:
                    requested_dataset_id = token

            if requested_dataset_id is None and isinstance(datasets, dict) and datasets:
                # Convenience switching by stage
                stage_hint = None
                if "use sql" in lower or "use sql results" in lower:
                    stage_hint = "sql"
                elif "use cleaned" in lower or "use clean" in lower:
                    stage_hint = "cleaned"
                elif "use wrangled" in lower or "use wrangle" in lower:
                    stage_hint = "wrangled"
                elif "use features" in lower or "use feature" in lower:
                    stage_hint = "feature"
                elif "use raw" in lower:
                    stage_hint = "raw"
                if stage_hint:
                    candidates = [
                        (float(e.get("created_ts") or 0.0), did)
                        for did, e in datasets.items()
                        if isinstance(e, dict) and e.get("stage") == stage_hint
                    ]
                    if candidates:
                        candidates.sort(reverse=True)
                        requested_dataset_id = candidates[0][1]
        except Exception:
            requested_dataset_id = None

        if requested_dataset_id and requested_dataset_id != active_dataset_id:
            selected = (
                datasets.get(requested_dataset_id)
                if isinstance(datasets, dict)
                else None
            )
            label = (
                selected.get("label")
                if isinstance(selected, dict)
                else requested_dataset_id
            )
            msg = AIMessage(
                content=f"Switched active dataset to `{label}` (`{requested_dataset_id}`).",
                name="supervisor",
            )
            return {
                "messages": [msg],
                "next": "FINISH",
                **base_update,
                "active_data_key": active_data_key,
                "datasets": datasets,
                "active_dataset_id": requested_dataset_id,
                "handled_request_id": handled_request_id,
                "handled_steps": handled_steps,
                "attempted_steps": attempted_steps,
                "workflow_plan_request_id": state_plan_req,
                "workflow_plan": state_plan,
            }

        data_ready = (
            _get_active_data(
                state_with_datasets,  # type: ignore[arg-type]
                [
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                    "feature_data",
                ],
            )
            is not None
        )
        last_worker = state.get("last_worker")

        def _loader_loaded_dataset(loader_artifacts: Any) -> bool:
            """
            Determine whether the loader actually loaded a dataset (vs listing a directory).
            This matters because node_loader intentionally preserves previous data_raw when no load occurred.
            """
            if not loader_artifacts:
                return False
            if isinstance(loader_artifacts, dict):
                # Single load_file artifact shape: {"status":"ok","data":{...},...}
                if (
                    loader_artifacts.get("status") == "ok"
                    and loader_artifacts.get("data") is not None
                ):
                    return True
                for key, val in loader_artifacts.items():
                    tool_name = str(key)
                    if tool_name.startswith("load_file") and isinstance(val, dict):
                        if val.get("status") == "ok" and val.get("data") is not None:
                            return True
                    if tool_name.startswith("load_directory") and isinstance(val, dict):
                        for _fname, info in val.items():
                            if (
                                isinstance(info, dict)
                                and info.get("status") == "ok"
                                and info.get("data") is not None
                            ):
                                return True
            return False

        def _loader_listed_directory(loader_artifacts: Any) -> bool:
            if not loader_artifacts:
                return False
            if isinstance(loader_artifacts, list):
                return True
            if isinstance(loader_artifacts, dict):
                for key in loader_artifacts.keys():
                    tool_name = str(key)
                    if tool_name.startswith("list_directory") or tool_name.startswith(
                        "search_files_by_pattern"
                    ):
                        return True
            return False

        # Mark completed steps for this request based on the last worker.
        if not is_new_request and last_worker:
            if last_worker == "Data_Loader_Tools_Agent":
                loader_art = (state.get("artifacts") or {}).get("data_loader")
                if _loader_loaded_dataset(loader_art):
                    handled_steps["load"] = True
                if _loader_listed_directory(loader_art):
                    handled_steps["list_files"] = True
            elif (
                last_worker == "Data_Merge_Agent"
                and (state.get("artifacts") or {}).get("merge") is not None
            ):
                handled_steps["merge"] = True
            elif (
                last_worker == "SQL_Database_Agent"
                and state.get("data_sql") is not None
            ):
                handled_steps["sql"] = True
            elif (
                last_worker == "Data_Wrangling_Agent"
                and state.get("data_wrangled") is not None
            ):
                handled_steps["wrangle"] = True
            elif (
                last_worker == "Data_Cleaning_Agent"
                and state.get("data_cleaned") is not None
            ):
                handled_steps["clean"] = True
            elif (
                last_worker == "EDA_Tools_Agent"
                and state.get("eda_artifacts") is not None
            ):
                handled_steps["eda"] = True
            elif (
                last_worker == "Data_Visualization_Agent"
                and state.get("viz_graph") is not None
            ):
                handled_steps["viz"] = True
            elif (
                last_worker == "Feature_Engineering_Agent"
                and state.get("feature_data") is not None
            ):
                handled_steps["feature"] = True
            elif last_worker == "H2O_ML_Agent" and state.get("model_info") is not None:
                handled_steps["model"] = True
            elif (
                last_worker == "Model_Evaluation_Agent"
                and state.get("eval_artifacts") is not None
            ):
                handled_steps["evaluate"] = True
            elif (
                last_worker == "MLflow_Logging_Agent"
                and state.get("mlflow_artifacts") is not None
            ):
                handled_steps["mlflow_log"] = True
            elif (
                last_worker == "MLflow_Tools_Agent"
                and state.get("mlflow_artifacts") is not None
            ):
                handled_steps["mlflow_tools"] = True

        step_to_worker = {
            "list_files": "Data_Loader_Tools_Agent",
            "load": "Data_Loader_Tools_Agent",
            "merge": "Data_Merge_Agent",
            "sql": "SQL_Database_Agent",
            "wrangle": "Data_Wrangling_Agent",
            "clean": "Data_Cleaning_Agent",
            "eda": "EDA_Tools_Agent",
            "viz": "Data_Visualization_Agent",
            "feature": "Feature_Engineering_Agent",
            "model": "H2O_ML_Agent",
            "evaluate": "Model_Evaluation_Agent",
            "mlflow_log": "MLflow_Logging_Agent",
            "mlflow_tools": "MLflow_Tools_Agent",
        }

        # Use the workflow planner for multi-step prompts when available.
        wants_steps_count = sum(
            1
            for k in (
                "list_files",
                "load",
                "merge",
                "sql",
                "wrangle",
                "clean",
                "eda",
                "preview",
                "viz",
                "feature",
                "model",
                "evaluate",
                "mlflow_log",
                "mlflow_tools",
                "workflow",
            )
            if intents.get(k)
        )
        use_planner = bool(
            proactive_mode
            or intents.get("workflow")
            or intents.get("model")
            or intents.get("evaluate")
            or intents.get("mlflow_log")
            or intents.get("mlflow_tools")
            or wants_steps_count >= 3
        )

        planned_steps: list[str] | None = None
        plan_questions: list[str] = []
        plan_notes: list[str] = []
        planner_messages: list[BaseMessage] = []
        planned_target: Optional[str] = state.get("target_variable")
        if (
            use_planner
            and workflow_planner_agent is not None
            and current_request_id is not None
        ):
            if state_plan_req == current_request_id and isinstance(state_plan, dict):
                planned_steps = (
                    state_plan.get("steps")
                    if isinstance(state_plan.get("steps"), list)
                    else None
                )
                plan_questions = (
                    state_plan.get("questions")
                    if isinstance(state_plan.get("questions"), list)
                    else []
                )
                plan_notes = (
                    state_plan.get("notes")
                    if isinstance(state_plan.get("notes"), list)
                    else []
                )
            else:
                # Provide a minimal context snapshot to help planning.
                context = {
                    "data_ready": bool(data_ready),
                    "active_data_key": active_data_key,
                    "has_data_raw": state.get("data_raw") is not None,
                    "has_data_cleaned": state.get("data_cleaned") is not None,
                    "has_data_wrangled": state.get("data_wrangled") is not None,
                    "has_feature_data": state.get("feature_data") is not None,
                    "has_sql": state.get("data_sql") is not None,
                    "has_model_info": state.get("model_info") is not None,
                    "proactive_workflow_mode": proactive_mode,
                }
                try:
                    workflow_planner_agent.invoke_messages(
                        messages=clean_msgs,
                        context=context,
                    )
                    plan = workflow_planner_agent.response or {}
                except Exception:
                    plan = {}
                planned_steps = (
                    plan.get("steps") if isinstance(plan.get("steps"), list) else None
                )
                plan_questions = (
                    plan.get("questions")
                    if isinstance(plan.get("questions"), list)
                    else []
                )
                plan_notes = (
                    plan.get("notes") if isinstance(plan.get("notes"), list) else []
                )
                planned_target = plan.get("target_variable") or planned_target
                state_plan_req = current_request_id
                state_plan = {
                    "steps": planned_steps or [],
                    "target_variable": planned_target,
                    "questions": plan_questions,
                    "notes": plan_notes,
                }
                if planned_steps:
                    pretty_steps = " → ".join(str(s) for s in planned_steps)
                    note_text = (
                        "\n".join(f"- {n}" for n in plan_notes) if plan_notes else ""
                    )
                    plan_msg_text: str = f"Planned workflow: {pretty_steps}"
                    if note_text:
                        plan_msg_text = plan_msg_text + "\n\nNotes:\n" + note_text
                    planner_messages = [
                        AIMessage(content=plan_msg_text, name="workflow_planner_agent")
                    ]

            # If the planner needs user input, ask and stop.
            if plan_questions and not (planned_steps and len(planned_steps) > 0):
                question_text = "\n".join(f"- {q}" for q in plan_questions)
                note_text = (
                    "\n".join(f"- {n}" for n in plan_notes) if plan_notes else ""
                )
                ask_msg_text: str = "To run the workflow, I need:\n" + question_text
                if note_text:
                    ask_msg_text = ask_msg_text + "\n\nNotes:\n" + note_text
                return {
                    "messages": [AIMessage(content=ask_msg_text, name="workflow_planner_agent")],
                    "next": "FINISH",
                    "active_data_key": active_data_key,
                    "datasets": datasets,
                    "active_dataset_id": active_dataset_id,
                    "handled_request_id": handled_request_id,
                    "handled_steps": handled_steps,
                    "attempted_steps": attempted_steps,
                    "workflow_plan_request_id": state_plan_req,
                    "workflow_plan": state_plan,
                }

        recognized_intent = any(
            [
                intents.get("list_files"),
                intents.get("load_only"),
                intents.get("load"),
                intents.get("merge"),
                intents.get("sql"),
                intents.get("wrangle"),
                intents.get("clean"),
                intents.get("eda"),
                intents.get("preview"),
                intents.get("viz"),
                intents.get("feature"),
                intents.get("model"),
                intents.get("evaluate"),
                intents.get("mlflow"),
                intents.get("mlflow_log"),
                intents.get("mlflow_tools"),
                intents.get("workflow"),
            ]
        )
        recognized_intent = bool(planned_steps) or recognized_intent

        # Deterministic, step-aware routing for common data science workflows.
        if recognized_intent:
            steps: list[str] = []

            # If we have a planner-derived step list, trust it.
            if planned_steps:
                steps = [str(s) for s in planned_steps if isinstance(s, str)]
            else:
                if intents.get("list_files"):
                    steps.append("list_files")

                # If the user asked to load a file, do that first.
                if intents.get("load") or intents.get("load_only"):
                    steps.append("load")

                # SQL can also be a data acquisition step.
                if intents.get("sql"):
                    steps.append("sql")

                # If the user requested data-dependent work but no data is present, attempt a load first.
                needs_data = any(
                    [
                        intents.get("merge"),
                        intents.get("wrangle"),
                        intents.get("clean"),
                        intents.get("eda"),
                        intents.get("preview"),
                        intents.get("viz"),
                        intents.get("feature"),
                        intents.get("model"),
                        intents.get("evaluate"),
                    ]
                )
                if (
                    not data_ready
                    and needs_data
                    and not (
                        intents.get("load")
                        or intents.get("load_only")
                        or intents.get("sql")
                    )
                ):
                    steps.insert(0, "load")

                # Transformations
                if intents.get("merge"):
                    steps.append("merge")
                if intents.get("wrangle"):
                    steps.append("wrangle")
                if intents.get("clean"):
                    steps.append("clean")

                # EDA / preview: if the user is explicitly loading, prefer the loader preview and avoid an extra EDA pass.
                wants_preview_via_eda = intents.get("preview") and not (
                    intents.get("load") or intents.get("load_only")
                )
                if intents.get("eda") or wants_preview_via_eda:
                    steps.append("eda")

                # Visualization
                if intents.get("viz"):
                    steps.append("viz")

                # Feature engineering and modeling
                if intents.get("feature"):
                    steps.append("feature")
                if intents.get("model"):
                    steps.append("model")
                if intents.get("evaluate"):
                    steps.append("evaluate")

                # MLflow logging and tools (inspection/UI)
                if intents.get("mlflow_log"):
                    steps.append("mlflow_log")
                if intents.get("mlflow_tools"):
                    steps.append("mlflow_tools")

            if not steps:
                logger.info("  recognized intent but no actionable steps -> fallback router")
            else:
                for step in steps:
                    if handled_steps.get(step):
                        continue
                    worker = step_to_worker.get(step)
                    if not worker:
                        continue

                    # Prevent infinite loops: don't attempt the same step twice within one user request
                    # unless it was actually completed.
                    if attempted_steps.get(step) and not handled_steps.get(step):
                        logger.info(f"  step '{step}' already attempted -> FINISH")
                        return {
                            **(
                                {"messages": planner_messages}
                                if planner_messages
                                else {}
                            ),
                            "next": "FINISH",
                            "active_data_key": active_data_key,
                            "datasets": datasets,
                            "active_dataset_id": active_dataset_id,
                            "handled_request_id": handled_request_id,
                            "handled_steps": handled_steps,
                            "attempted_steps": attempted_steps,
                            "workflow_plan_request_id": state_plan_req,
                            "workflow_plan": state_plan,
                            "target_variable": planned_target,
                        }

                    # Guard data-dependent steps.
                    if (
                        step
                        in (
                            "merge",
                            "wrangle",
                            "clean",
                            "eda",
                            "viz",
                            "feature",
                            "model",
                            "evaluate",
                        )
                        and not data_ready
                    ):
                        logger.info(
                            f"  step '{step}' requires data but none is ready -> Data_Loader_Tools_Agent"
                        )
                        attempted_steps["load"] = True
                        return {
                            **(
                                {"messages": planner_messages}
                                if planner_messages
                                else {}
                            ),
                            "next": "Data_Loader_Tools_Agent",
                            **base_update,
                            "active_data_key": active_data_key,
                            "datasets": datasets,
                            "active_dataset_id": active_dataset_id,
                            "handled_request_id": handled_request_id,
                            "handled_steps": handled_steps,
                            "attempted_steps": attempted_steps,
                            "workflow_plan_request_id": state_plan_req,
                            "workflow_plan": state_plan,
                            "target_variable": planned_target,
                        }

                    logger.info(f"  next_step='{step}' -> {worker}")
                    attempted_steps[step] = True
                    return {
                        **({"messages": planner_messages} if planner_messages else {}),
                        "next": worker,
                        **base_update,
                        "active_data_key": active_data_key,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                        "handled_request_id": handled_request_id,
                        "handled_steps": handled_steps,
                        "attempted_steps": attempted_steps,
                        "workflow_plan_request_id": state_plan_req,
                        "workflow_plan": state_plan,
                        "target_variable": planned_target,
                    }

                logger.info("  all requested steps handled -> FINISH")
                return {
                    **({"messages": planner_messages} if planner_messages else {}),
                    "next": "FINISH",
                    **base_update,
                    "active_data_key": active_data_key,
                    "datasets": datasets,
                    "active_dataset_id": active_dataset_id,
                    "handled_request_id": handled_request_id,
                    "handled_steps": handled_steps,
                    "attempted_steps": attempted_steps,
                    "workflow_plan_request_id": state_plan_req,
                    "workflow_plan": state_plan,
                    "target_variable": planned_target,
                }

        result = supervisor_chain.invoke(
            {"messages": clean_msgs, "last_worker": state.get("last_worker")}
        )
        next_worker = result.get("next")
        logger.info(
            f"  data_ready={data_ready}, last_worker={last_worker}, router_next={next_worker}"
        )

        # Intent-aware override when data is present
        if data_ready:
            if next_worker == "Data_Loader_Tools_Agent":
                if intents["viz"]:
                    next_worker = "Data_Visualization_Agent"
                elif intents["eda"]:
                    next_worker = "EDA_Tools_Agent"
                elif intents["clean"] or intents["wrangle"]:
                    next_worker = "Data_Wrangling_Agent"
                elif intents["feature"]:
                    next_worker = "Feature_Engineering_Agent"
                elif intents["model"]:
                    next_worker = "H2O_ML_Agent"
                elif not any(
                    [
                        intents.get("viz"),
                        intents.get("eda"),
                        intents.get("clean"),
                        intents.get("wrangle"),
                        intents.get("sql"),
                        intents.get("feature"),
                        intents.get("model"),
                        intents.get("mlflow"),
                    ]
                ):
                    next_worker = "FINISH"
                else:
                    next_worker = "Data_Wrangling_Agent"

        # Keep active_data_key stable unless a worker changes it.
        return {
            "next": next_worker,
            **base_update,
            "active_data_key": active_data_key,
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "handled_request_id": handled_request_id,
            "handled_steps": handled_steps,
            "attempted_steps": attempted_steps,
            "workflow_plan_request_id": state_plan_req,
            "workflow_plan": state_plan,
            "target_variable": planned_target,
        }

    def _format_listing_with_llm(rows: list, last_human: str):
        return format_listing_with_llm(llm, rows, last_human)

    def _format_dataset_with_llm(
        df_dict: dict, last_human: str, max_rows: int = 10, max_cols: int = 6
    ):
        return format_dataset_with_llm(llm, df_dict, last_human, max_rows, max_cols)

    def _format_result_with_llm(
        agent_name: str,
        df_dict: Optional[dict],
        last_human: str,
        extra_text: str = "",
        max_rows: int = 6,
        max_cols: int = 6,
    ):
        return format_result_with_llm(
            llm,
            agent_name,
            df_dict,
            last_human,
            extra_text,
            max_rows,
            max_cols,
        )

    _append_error_message = append_error_message
    _ensure_df = ensure_df
    _ensure_dataset_registry = ensure_dataset_registry
    _get_active_data = get_active_data
    _is_empty_df = is_empty_df
    _merge_messages = merge_messages
    _register_dataset = register_dataset
    _shape = shape_of
    _sha256_text = sha256_text
    _tag_messages = tag_messages
    _trim_messages = trim_messages
    _truncate_text = truncate_text

    node_loader = make_node_loader(
        LoaderNodeDeps(
            data_loader_agent=data_loader_agent,
            ensure_dataset_registry=ensure_dataset_registry,
            format_listing_with_llm=format_listing_with_llm,
            format_result_with_llm=format_result_with_llm,
            _get_last_human_text=_get_last_human_text,
            merge_messages=merge_messages,
            register_dataset=register_dataset,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_merge = make_node_merge(
        MergeNodeDeps(
            ensure_dataset_registry=ensure_dataset_registry,
            ensure_df=ensure_df,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            register_dataset=register_dataset,
            sha256_text=sha256_text,
            tag_messages=tag_messages,
            truncate_text=truncate_text,
        )
    )

    node_wrangling = make_node_wrangling(
        WranglingNodeDeps(
            data_wrangling_agent=data_wrangling_agent,
            ensure_dataset_registry=ensure_dataset_registry,
            ensure_df=ensure_df,
            format_result_with_llm=format_result_with_llm,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_cleaning = make_node_cleaning(
        CleaningNodeDeps(
            data_cleaning_agent=data_cleaning_agent,
            ensure_dataset_registry=ensure_dataset_registry,
            ensure_df=ensure_df,
            format_result_with_llm=format_result_with_llm,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_sql = make_node_sql(
        SqlNodeDeps(
            sql_database_agent=sql_database_agent,
            append_error_message=append_error_message,
            ensure_dataset_registry=ensure_dataset_registry,
            format_result_with_llm=format_result_with_llm,
            _get_last_human_text=_get_last_human_text,
            merge_messages=merge_messages,
            register_dataset=register_dataset,
            sha256_text=sha256_text,
            tag_messages=tag_messages,
            truncate_text=truncate_text,
            llm=llm,
        )
    )

    node_eda = make_node_eda(
        EdaNodeDeps(
            eda_tools_agent=eda_tools_agent,
            ensure_df=ensure_df,
            format_result_with_llm=format_result_with_llm,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_viz = make_node_viz(
        VizNodeDeps(
            data_visualization_agent=data_visualization_agent,
            ensure_df=ensure_df,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
        )
    )

    node_fe = make_node_fe(
        FeNodeDeps(
            feature_engineering_agent=feature_engineering_agent,
            ensure_dataset_registry=ensure_dataset_registry,
            ensure_df=ensure_df,
            format_result_with_llm=format_result_with_llm,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_h2o = make_node_h2o(
        H2oNodeDeps(
            h2o_ml_agent=h2o_ml_agent,
            append_error_message=append_error_message,
            ensure_dataset_registry=ensure_dataset_registry,
            ensure_df=ensure_df,
            format_result_with_llm=format_result_with_llm,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            register_dataset=register_dataset,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_mlflow = make_node_mlflow(
        MlflowNodeDeps(
            mlflow_tools_agent=mlflow_tools_agent,
            ensure_df=ensure_df,
            format_result_with_llm=format_result_with_llm,
            get_active_data=get_active_data,
            _get_last_human_text=_get_last_human_text,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
            llm=llm,
        )
    )

    node_eval = make_node_eval(
        EvalNodeDeps(
            model_evaluation_agent=model_evaluation_agent,
            ensure_df=ensure_df,
            get_active_data=get_active_data,
            is_empty_df=is_empty_df,
            merge_messages=merge_messages,
            tag_messages=tag_messages,
        )
    )

    node_mlflow_log = make_node_mlflow_log(
        MlflowLogNodeDeps(
            mlflow_tools_agent=mlflow_tools_agent,
            ensure_df=ensure_df,
            get_active_data=get_active_data,
            is_empty_df=is_empty_df,
            tag_messages=tag_messages,
        )
    )

    workflow = StateGraph(SupervisorDSState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("Data_Loader_Tools_Agent", node_loader)
    workflow.add_node("Data_Merge_Agent", node_merge)
    workflow.add_node("Data_Wrangling_Agent", node_wrangling)
    workflow.add_node("Data_Cleaning_Agent", node_cleaning)
    workflow.add_node("EDA_Tools_Agent", node_eda)
    workflow.add_node("Data_Visualization_Agent", node_viz)
    workflow.add_node("SQL_Database_Agent", node_sql)
    workflow.add_node("Feature_Engineering_Agent", node_fe)
    workflow.add_node("H2O_ML_Agent", node_h2o)
    workflow.add_node("Model_Evaluation_Agent", node_eval)
    workflow.add_node("MLflow_Logging_Agent", node_mlflow_log)
    workflow.add_node("MLflow_Tools_Agent", node_mlflow)

    workflow.set_entry_point("supervisor")

    # After any worker, return to supervisor
    for node in subagent_names:
        workflow.add_edge(node, "supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state.get("next"),
        {name: name for name in subagent_names} | {"FINISH": END},  # type: ignore[arg-type]
    )

    app = workflow.compile(checkpointer=checkpointer, name="supervisor_ds_team")
    return app



from ai_data_science_team.multiagents.supervisor_ds_team._class import SupervisorDSTeam

__all__ = ['make_supervisor_ds_team', 'SupervisorDSTeam']
