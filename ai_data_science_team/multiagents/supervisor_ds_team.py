from __future__ import annotations

from typing import Sequence, Optional, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from IPython.display import Markdown
from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, END
from langgraph.types import Checkpointer
from langgraph.graph.message import add_messages

from ai_data_science_team.multiagents.supervisor import (
    SupervisorDSState,
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
        print("---SUPERVISOR---")
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
                print("  recognized intent but no actionable steps -> fallback router")
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
                        print(f"  step '{step}' already attempted -> FINISH")
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
                        print(
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

                    print(f"  next_step='{step}' -> {worker}")
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

                print("  all requested steps handled -> FINISH")
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
        print(
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

    def node_loader(state: SupervisorDSState):
        print("---DATA LOADER---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        cfg = (state.get("artifacts") or {}).get("config") or {}
        debug = bool(cfg.get("debug")) if isinstance(cfg, dict) else False
        if debug:
            print(f"  loader last_human={last_human!r}")

        # DataLoaderToolsAgent is tool-driven; the latest user request is already in messages.
        data_loader_agent.invoke_messages(messages=before_msgs)
        response = data_loader_agent.response or {}
        merged = _merge_messages(before_msgs, response)

        loader_artifacts = response.get("data_loader_artifacts")
        if debug:
            try:
                print(f"  loader response_keys={sorted(list(response.keys()))}")
                if isinstance(loader_artifacts, dict):
                    print(
                        f"  loader artifacts_keys={list(loader_artifacts.keys())[:25]}"
                    )
                else:
                    print(f"  loader artifacts_type={type(loader_artifacts)}")
            except Exception:
                pass

        previous_data_raw = state.get("data_raw")
        data_raw = previous_data_raw
        active_data_key = state.get("active_data_key")

        dir_listing = None
        loaded_dataset = None
        loaded_dataset_label = None
        multiple_loaded_files = None
        multiple_loaded_datasets: list[tuple[str, Any]] | None = None
        fallback_loaded_dataset = False
        multi_file_load = False

        artifacts_map = normalize_loader_artifacts(loader_artifacts)
        if debug:
            try:
                print(f"  loader artifacts_map_keys={list(artifacts_map.keys())[:25]}")
            except Exception:
                pass

        (
            dir_listing,
            loaded_dataset,
            loaded_dataset_label,
            multiple_loaded_files,
            multiple_loaded_datasets,
            load_file_ok_items,
        ) = extract_loader_artifact_results(artifacts_map)

        if debug:
            try:
                print(f"  loader load_file_ok_items={len(load_file_ok_items)}")
                for name, data in load_file_ok_items[:3]:
                    print(
                        f"    - ok {name}: data_type={type(data)} shape={_shape(data)}"
                    )
            except Exception:
                pass

        # Fallback: if tool artifacts didn't yield usable data, load file paths directly from the user text.
        if (
            loaded_dataset is None
            and not multiple_loaded_datasets
            and not load_file_ok_items
            and isinstance(last_human, str)
            and last_human.strip()
        ):
            try:
                import re
                import pandas as pd

                from ai_data_science_team.tools.data_loader import (
                    auto_load_file,
                    DEFAULT_MAX_ROWS,
                )

                last_human_lower = last_human.lower()
                if any(
                    w in last_human_lower for w in ("load", "read", "import", "open")
                ):
                    requested = re.findall(
                        r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
                        last_human,
                        flags=re.IGNORECASE,
                    )
                    requested = [r.strip() for r in requested if str(r).strip()]
                    seen_req: set[str] = set()
                    requested_unique: list[str] = []
                    for r in requested:
                        if r in seen_req:
                            continue
                        seen_req.add(r)
                        requested_unique.append(r)

                    ok_items: list[tuple[str, Any]] = []  # type: ignore[no-redef]
                    errs: list[str] = []
                    for fp in requested_unique:
                        df_or_error = auto_load_file(fp, max_rows=DEFAULT_MAX_ROWS)
                        if isinstance(df_or_error, pd.DataFrame):
                            ok_items.append((fp, df_or_error.to_dict()))
                        else:
                            errs.append(f"{fp}: {df_or_error}")

                    if ok_items:
                        multi_file_load = len(ok_items) > 1
                        multiple_loaded_files = [fp for fp, _ in ok_items]
                        multiple_loaded_datasets = ok_items
                        loaded_dataset_label, loaded_dataset = ok_items[-1]
                        fallback_loaded_dataset = True
                        dir_listing = None
                        if debug:
                            print(
                                f"  loader deterministic_fallback_loaded={len(ok_items)} last={loaded_dataset_label!r}"
                            )
                    if errs and debug:
                        print(f"  loader deterministic_fallback_errors={errs[:3]}")

                    if errs:
                        marker = {
                            "status": "error",
                            "data": None,
                            "error": "; ".join(errs[:3]),
                        }
                        if isinstance(loader_artifacts, dict):
                            loader_artifacts = {
                                **loader_artifacts,
                                "load_file_deterministic_fallback": marker,
                            }
                        elif loader_artifacts is None:
                            loader_artifacts = {
                                "load_file_deterministic_fallback": marker
                            }
            except Exception:
                pass

        # If multiple load_file calls succeeded, keep them all and default the active dataset to the last one.
        if (
            loaded_dataset is None
            and not multiple_loaded_datasets
            and len(load_file_ok_items) > 1
        ):
            labels = infer_requested_load_labels(last_human or "", load_file_ok_items)

            multi_file_load = True
            multiple_loaded_files = labels
            multiple_loaded_datasets = [
                (lbl, data) for lbl, (_name, data) in zip(labels, load_file_ok_items)
            ]
            loaded_dataset_label, loaded_dataset = multiple_loaded_datasets[-1]
        elif (
            loaded_dataset is None
            and not multiple_loaded_datasets
            and len(load_file_ok_items) == 1
        ):
            loaded_dataset_label, loaded_dataset = load_file_ok_items[0]

        # If the tool returned only a directory listing but the user requested a specific file to load,
        # attempt to load it deterministically (avoids "listing loop" regressions across turns).
        if loaded_dataset is None and dir_listing is not None:
            try:
                import re
                import os
                from pathlib import Path
                import pandas as pd

                from ai_data_science_team.tools.data_loader import (
                    auto_load_file,
                    DEFAULT_MAX_ROWS,
                )

                last_human_text = _get_last_human(before_msgs) or ""
                last_human_lower = last_human_text.lower()

                if any(
                    w in last_human_lower for w in ("load", "read", "import", "open")
                ):
                    m = re.search(
                        r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
                        last_human_text,
                        flags=re.IGNORECASE,
                    )
                    requested_single: str = (m.group(1) if m else "").strip()
                    if requested_single:
                        p = Path(requested_single).expanduser()
                        if not p.is_absolute():
                            p = (Path(os.getcwd()) / p).resolve()
                        else:
                            p = p.resolve()

                        def _load_path(fp: str) -> Optional[dict]:
                            df_or_error = auto_load_file(fp, max_rows=DEFAULT_MAX_ROWS)
                            if isinstance(df_or_error, pd.DataFrame):
                                return df_or_error.to_dict()
                            return None

                        loaded = _load_path(str(p)) if p.is_file() else None

                        # If the path isn't directly valid, try to match by basename from listing outputs.
                        if loaded is None:
                            basename = Path(requested_single).name
                            candidate_paths: list[str] = []
                            if isinstance(dir_listing, list):
                                for item in dir_listing:
                                    if isinstance(item, dict):
                                        fp = (
                                            item.get("file_path")
                                            or item.get("absolute_path")
                                            or item.get("path")
                                            or item.get("filepath")
                                        )
                                        if isinstance(fp, str):
                                            candidate_paths.append(fp)
                                    elif isinstance(item, str):
                                        candidate_paths.append(item)
                            elif isinstance(dir_listing, dict):
                                for item in dir_listing.values():
                                    if isinstance(item, dict):
                                        fp = (
                                            item.get("file_path")
                                            or item.get("absolute_path")
                                            or item.get("path")
                                            or item.get("filepath")
                                        )
                                        if isinstance(fp, str):
                                            candidate_paths.append(fp)
                                    elif isinstance(item, str):
                                        candidate_paths.append(item)
                            for fp in candidate_paths:
                                try:
                                    resolved = Path(fp).expanduser().resolve()
                                except Exception:
                                    continue
                                if resolved.is_file() and resolved.name == basename:
                                    loaded = _load_path(str(resolved))
                                    if loaded is not None:
                                        loaded_dataset_label = str(resolved)
                                        break

                        if loaded is not None:
                            loaded_dataset = loaded
                            loaded_dataset_label = loaded_dataset_label or str(p)
                            dir_listing = None
                            fallback_loaded_dataset = True
            except Exception:
                pass

        if loaded_dataset is not None:
            data_raw = loaded_dataset
            active_data_key = "data_raw"
            # Prefer dataset summary over any incidental listings
            dir_listing = None
            if fallback_loaded_dataset:
                # The loader agent likely produced a listing-oriented AI message; suppress it.
                merged["messages"] = []
                # Store a lightweight marker so the supervisor can mark the load step as completed.
                marker = {
                    "status": "ok",
                    "data": {"file_path": str(loaded_dataset_label) if loaded_dataset_label is not None else None},  # type: ignore[dict-item]
                    "error": None,
                }
                if isinstance(loader_artifacts, dict):
                    loader_artifacts = {
                        **loader_artifacts,
                        "load_file_fallback": marker,
                    }
                else:
                    loader_artifacts = {"load_file_fallback": marker}

        print(
            f"  loader data_raw shape={_shape(data_raw)} active_data_key={active_data_key}"
        )

        datasets, active_dataset_id = _ensure_dataset_registry(state)
        # Register newly loaded datasets in the dataset registry.
        if multi_file_load and multiple_loaded_datasets:
            try:
                import os
                from ai_data_science_team.tools.data_loader import (
                    resolve_existing_file_path,
                )

                state_for_register = {
                    **state,
                    "datasets": datasets,
                    "active_dataset_id": active_dataset_id,
                }
                to_register = list(multiple_loaded_datasets)[-DATASET_REGISTRY_MAX:]
                for idx, (fname, data) in enumerate(to_register):
                    source = str(fname)
                    try:
                        resolved_path, _matches = resolve_existing_file_path(source)
                        if resolved_path is not None:
                            source = str(resolved_path)
                    except Exception:
                        source = str(fname)

                    label = os.path.basename(source) or str(fname)
                    provenance = {
                        "source_type": "file",
                        "source": source or str(fname),
                        "original_name": os.path.basename(str(fname)) or str(fname),
                        "user_request": last_human,
                        "multi_load": True,
                    }
                    make_active = idx == (len(to_register) - 1)
                    datasets, active_dataset_id, _did = _register_dataset(
                        state_for_register,  # type: ignore[arg-type]
                        data=data,
                        stage="raw",
                        label=str(label),
                        created_by="Data_Loader_Tools_Agent",
                        provenance=provenance,
                        parent_id=None,
                        make_active=make_active,
                    )
                    state_for_register = {
                        **state_for_register,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    }
            except Exception:
                # Never fail the load step due to registry bookkeeping.
                pass
        elif loaded_dataset is not None:
            try:
                import os

                # Best-effort: capture the file path from the user request for reproducibility.
                source = loaded_dataset_label
                try:
                    import re
                    from ai_data_science_team.tools.data_loader import (
                        resolve_existing_file_path,
                    )

                    if not (
                        isinstance(source, str)
                        and ("." in source and os.path.sep in source)
                    ):
                        m = re.search(
                            r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
                            last_human or "",
                            flags=re.IGNORECASE,
                        )
                        requested_src: str = (m.group(1) if m else "").strip()
                        if requested_src:
                            resolved_path, _matches = resolve_existing_file_path(
                                requested_src
                            )
                            if resolved_path is not None:
                                source = str(resolved_path)
                            else:
                                source = requested_src
                    # Also normalize/absolutize an existing-looking path label.
                    if isinstance(source, str) and source.strip():
                        resolved_path, _matches = resolve_existing_file_path(source)
                        if resolved_path is not None:
                            source = str(resolved_path)
                except Exception:
                    pass

                label = source or loaded_dataset_label or "data_raw"
                if isinstance(label, str):
                    label = os.path.basename(label) or label
                provenance = {
                    "source_type": "file",
                    "source": source or loaded_dataset_label,
                    "original_name": os.path.basename(
                        str(source or loaded_dataset_label or "")
                    )
                    or None,
                    "user_request": last_human,
                    "fallback_loader": bool(fallback_loaded_dataset),
                }
                datasets, active_dataset_id, _did = _register_dataset(
                    {  # type: ignore[arg-type]
                        **state,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    },
                    data=data_raw,
                    stage="raw",
                    label=str(label),
                    created_by="Data_Loader_Tools_Agent",
                    provenance=provenance,
                    parent_id=None,
                    make_active=True,
                )
            except Exception:
                # Never fail the load step due to registry bookkeeping.
                pass
        elif multiple_loaded_datasets:
            # Keep the already-loaded datasets available for explicit selection, but do not auto-switch.
            try:
                state_for_register = {
                    **state,
                    "datasets": datasets,
                    "active_dataset_id": active_dataset_id,
                }
                # Register only the most recent N to avoid unbounded growth.
                for fname, data in list(multiple_loaded_datasets)[
                    -DATASET_REGISTRY_MAX:
                ]:
                    datasets, active_dataset_id, _did = _register_dataset(
                        state_for_register,  # type: ignore[arg-type]
                        data=data,
                        stage="raw",
                        label=str(fname),
                        created_by="Data_Loader_Tools_Agent",
                        provenance={
                            "source_type": "directory_load",
                            "source": fname,
                            "user_request": last_human,
                        },
                        parent_id=None,
                        make_active=False,
                    )
                    state_for_register = {
                        **state_for_register,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    }
            except Exception:
                pass

        # Add a lightweight AI summary message so supervisor can progress
        summary_msg = None
        if multi_file_load and multiple_loaded_datasets:
            try:
                import os
                import pandas as pd

                lines = []
                for fname, data in multiple_loaded_datasets:
                    label = os.path.basename(str(fname)) or str(fname)
                    shape_txt = ""
                    try:
                        df = pd.DataFrame(data)
                        shape_txt = f" ({df.shape[0]} rows × {df.shape[1]} cols)"
                    except Exception:
                        pass
                    lines.append(f"- {label}{shape_txt}")

                active_label = os.path.basename(str(loaded_dataset_label)) or str(
                    loaded_dataset_label or ""
                )
                preview_txt = ""
                try:
                    df_active = (
                        pd.DataFrame(data_raw) if isinstance(data_raw, dict) else None
                    )
                    if df_active is not None:
                        preview_df = df_active.head(5)
                        max_cols = 10
                        if preview_df.shape[1] > max_cols:
                            preview_df = preview_df.iloc[:, :max_cols]
                        preview_txt = (
                            "\n\nPreview (first 5 rows):\n\n"
                            + preview_df.to_markdown(index=False)
                        )
                except Exception:
                    pass

                summary_msg = AIMessage(
                    content=(
                        f"Loaded {len(multiple_loaded_datasets)} datasets:\n\n"
                        + "\n".join(lines)
                        + (
                            f"\n\nActive dataset: {active_label}."
                            if active_label
                            else ""
                        )
                        + preview_txt
                        + "\n\nUse the sidebar dataset selector to switch the active dataset, or use Pipeline Studio to merge them."
                    ),
                    name="data_loader_agent",
                )
            except Exception:
                summary_msg = AIMessage(
                    content=(
                        f"Loaded {len(multiple_loaded_datasets)} datasets. "
                        "Use the sidebar dataset selector to switch the active dataset, or use Pipeline Studio to merge them."
                    ),
                    name="data_loader_agent",
                )
            summary_msg = summarize_multi_loaded_datasets(
                multiple_loaded_datasets,
                loaded_dataset_label,
                data_raw,
            )
        elif multiple_loaded_files:
            summary_msg = summarize_multiple_loaded_files(multiple_loaded_files)
        elif dir_listing is not None:
            try:
                # dir_listing could be list/dict; extract filenames
                names = []
                rows = []
                if isinstance(dir_listing, list):
                    for item in dir_listing:
                        if isinstance(item, dict):
                            if "filename" in item:
                                names.append(item.get("filename"))
                                rows.append(
                                    {
                                        "filename": item.get("filename"),
                                        "type": item.get("type"),
                                        "path": item.get("path")
                                        or item.get("filepath"),
                                    }
                                )
                                continue
                            if "file_path" in item:
                                fp = item.get("file_path")
                                import os

                                fn = (
                                    os.path.basename(fp)
                                    if isinstance(fp, str)
                                    else str(fp)
                                )
                                names.append(fn)
                                rows.append(
                                    {"filename": fn, "type": "file", "path": fp}
                                )
                                continue
                            if "absolute_path" in item or "name" in item:
                                ap = item.get("absolute_path")
                                import os

                                fn = item.get("name") or (
                                    os.path.basename(ap)
                                    if isinstance(ap, str)
                                    else str(ap)
                                )
                                names.append(fn)
                                rows.append(
                                    {
                                        "filename": fn,
                                        "type": item.get("type"),
                                        "path": ap,
                                    }
                                )
                                continue

                        names.append(str(item))
                        rows.append({"filename": str(item)})
                elif isinstance(dir_listing, dict):
                    # maybe mapping index->filename
                    for v in dir_listing.values():
                        if isinstance(v, dict):
                            if "filename" in v:
                                names.append(str(v.get("filename")))
                                rows.append(
                                    {
                                        "filename": v.get("filename"),
                                        "type": v.get("type"),
                                        "path": v.get("path") or v.get("filepath"),
                                    }
                                )
                            elif "file_path" in v:
                                fp = v.get("file_path")
                                import os

                                fn = (
                                    os.path.basename(fp)
                                    if isinstance(fp, str)
                                    else str(fp)
                                )
                                names.append(fn)
                                rows.append(
                                    {"filename": fn, "type": "file", "path": fp}
                                )
                            elif "absolute_path" in v or "name" in v:
                                ap = v.get("absolute_path")
                                import os

                                fn = v.get("name") or (
                                    os.path.basename(ap)
                                    if isinstance(ap, str)
                                    else str(ap)
                                )
                                names.append(fn)
                                rows.append(
                                    {"filename": fn, "type": v.get("type"), "path": ap}
                                )
                            else:
                                names.append(str(v))
                                rows.append({"filename": str(v)})
                        else:
                            names.append(str(v))
                            rows.append({"filename": str(v)})

                last_human = _get_last_human(before_msgs).lower()
                wants_csv_only = "csv" in last_human and (
                    "list" in last_human or "files" in last_human
                )
                if wants_csv_only and rows:
                    rows = [
                        r
                        for r in rows
                        if str(r.get("filename", "")).lower().endswith(".csv")
                    ]
                    names = [r.get("filename") for r in rows if r.get("filename")]
                    if not rows:
                        summary_msg = AIMessage(
                            content="No CSV files found in that directory.",
                            name="data_loader_agent",
                        )
                        dir_listing = None

                if summary_msg is None:
                    msg_text = (
                        "Found files: " + ", ".join(names)
                        if names
                        else "Found directory contents."
                    )
                    table_text = ""
                    if rows:
                        import pandas as pd

                        df_listing = pd.DataFrame(rows)
                        table_cols = [
                            c
                            for c in ["filename", "type", "path"]
                            if c in df_listing.columns
                        ]
                        table_text = df_listing[table_cols].to_markdown(index=False)
                    # If the user asked for a table or better formatting, try a tiny LLM summary
                    llm_text = (
                        _format_listing_with_llm(rows, last_human) if rows else None
                    )
                    if llm_text:
                        summary_msg = AIMessage(
                            content=llm_text, name="data_loader_agent"
                        )
                    elif table_text:
                        summary_msg = AIMessage(
                            content=f"{msg_text}\n\n{table_text}",
                            name="data_loader_agent",
                        )
                    else:
                        summary_msg = AIMessage(
                            content=msg_text, name="data_loader_agent"
                        )
            except Exception:
                summary_msg = AIMessage(
                    content="Listed directory contents.", name="data_loader_agent"
                )
            summary_msg, dir_listing = summarize_directory_listing(
                dir_listing,
                (_get_last_human(before_msgs) or "").lower(),
                _format_listing_with_llm,
            )
        elif loaded_dataset is not None and isinstance(data_raw, dict):
            summary_msg = summarize_loaded_dataset(
                data_raw,
                (_get_last_human(before_msgs) or "").lower(),
                _format_result_with_llm,
            )
        elif loader_artifacts is not None:
            summary_msg = summarize_loader_failure(loader_artifacts)

        if summary_msg:
            merged["messages"] = merged.get("messages", []) + [summary_msg]

        loader_errors = collect_loader_errors(loader_artifacts)
        if loader_errors:
            merged["messages"] = merged.get("messages", []) + [
                AIMessage(
                    content="Data loading error(s):\n" + "\n".join(loader_errors),
                    name="data_loader_agent",
                )
            ]

        merged["messages"] = _tag_messages(merged.get("messages"), "data_loader_agent")

        # If the dataset changed, clear downstream artifacts to avoid stale plots/models.
        downstream_resets = {}
        if loaded_dataset is not None:
            downstream_resets = {
                "data_wrangled": None,
                "data_cleaned": None,
                "eda_artifacts": None,
                "viz_graph": None,
                "feature_data": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }

        return {
            **merged,
            "data_raw": data_raw,
            "active_data_key": active_data_key,
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "data_loader": loader_artifacts,
                "data_loader_details": {"errors": loader_errors} if loader_errors else {},
            },
            "last_worker": "Data_Loader_Tools_Agent",
            **downstream_resets,
        }

    def node_merge(state: SupervisorDSState):
        print("---DATA MERGE---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        datasets, active_dataset_id = _ensure_dataset_registry(state)
        state_with_datasets = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }

        cfg = (state.get("artifacts") or {}).get("config") or {}
        merge_cfg = cfg.get("merge") if isinstance(cfg, dict) else None
        merge_cfg = merge_cfg if isinstance(merge_cfg, dict) else {}
        selected_ids = resolve_selected_dataset_ids(
            datasets,
            active_dataset_id,
            merge_cfg,
            last_human,
        )

        if len(selected_ids) < 2:
            available = available_datasets_lines(datasets)
            msg = (
                "To merge datasets, mention 2+ dataset IDs in your request (or use Pipeline Studio to create a merge node).\n\n"
                + ("Available datasets:\n" + "\n".join(available) if available else "")
            ).strip()
            return {
                "messages": [AIMessage(content=msg, name="data_merge_agent")],
                "last_worker": "Data_Merge_Agent",
            }

        dfs = []
        for did in selected_ids:
            entry = datasets.get(did)
            df = _ensure_df(entry.get("data") if isinstance(entry, dict) else None)
            if _is_empty_df(df):
                return {
                    "messages": [
                        AIMessage(
                            content=f"Dataset `{did}` is empty/unavailable; load it again before merging.",
                            name="data_merge_agent",
                        )
                    ],
                    "last_worker": "Data_Merge_Agent",
                }
            dfs.append(df)

        merge_plan = execute_merge_plan(dfs, merge_cfg, last_human)
        if not merge_plan.get("ok"):
            return {
                "messages": [
                    AIMessage(
                        content=str(merge_plan.get("error_message") or "Merge failed."),
                        name="data_merge_agent",
                    )
                ],
                "last_worker": "Data_Merge_Agent",
            }

        op = str(merge_plan.get("operation") or "join")
        merged_df = merge_plan["merged_df"]
        merge_meta: dict[str, Any] = {
            "dataset_ids": selected_ids,
            **dict(merge_plan.get("merge_meta") or {}),
        }
        merge_code = str(merge_plan.get("merge_code") or "")
        merge_code_hash = _sha256_text(merge_code)

        merged_data = merged_df
        try:
            import pandas as pd

            if isinstance(merged_df, pd.DataFrame):
                merged_data = merged_df.to_dict()
        except Exception:
            merged_data = merged_df

        datasets, active_dataset_id, merged_id = _register_dataset(
            state_with_datasets,  # type: ignore[arg-type]
            data=merged_data,
            stage="wrangled",
            label="data_merged",
            created_by="Data_Merge_Agent",
            provenance={
                "source_type": "agent",
                "user_request": last_human,
                "transform": {
                    "kind": "python_merge",
                    "merge": merge_meta,
                    "merge_code": _truncate_text(merge_code, 12000),
                    "code_sha256": merge_code_hash,
                },
            },
            parent_ids=selected_ids,
            make_active=True,
        )

        msg_lines = [
            f"Merged {len(selected_ids)} datasets ({op}).",
            f"Result shape: {getattr(merged_df, 'shape', None)}.",
            f"Active dataset id: `{merged_id}`.",
        ]
        merged = {
            "messages": [
                AIMessage(
                    content=" ".join([m for m in msg_lines if m]),
                    name="data_merge_agent",
                )
            ]
        }
        merged["messages"] = _tag_messages(merged.get("messages"), "data_merge_agent")
        downstream_resets = {
            "data_cleaned": None,
            "eda_artifacts": None,
            "viz_graph": None,
            "feature_data": None,
            "model_info": None,
            "mlflow_artifacts": None,
        }
        return {
            **merged,
            "data_wrangled": merged_data,
            "active_data_key": "data_wrangled",
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "merge": {
                    "dataset_ids": selected_ids,
                    "operation": op,
                    "active_dataset_id": merged_id,
                    "merge_config": merge_cfg,
                },
            },
            "last_worker": "Data_Merge_Agent",
            **downstream_resets,
        }

    def node_wrangling(state: SupervisorDSState):
        print("---DATA WRANGLING---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        datasets, active_dataset_id = _ensure_dataset_registry(state)
        state_with_datasets = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }
        active_df = _ensure_df(
            _get_active_data(
                state_with_datasets,  # type: ignore[arg-type]
                [
                    "data_raw",
                    "data_sql",
                    "data_wrangled",
                    "data_cleaned",
                    "feature_data",
                ],
            )
        )
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available to wrangle. Load a file (or run a SQL query) first.",
                        name="data_wrangling_agent",
                    )
                ],
                "last_worker": "Data_Wrangling_Agent",
            }
        data_wrangling_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
        )
        response = data_wrangling_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(
            merged.get("messages"), "data_wrangling_agent"
        )
        append_agent_feedback(
            merged,
            agent_name="data_wrangling_agent",
            summary_data=response.get("data_wrangled"),
            last_human=_get_last_human(before_msgs),
            format_result_with_llm=_format_result_with_llm,
            extra_text="Wrangling steps completed.",
            error_text=response.get("data_wrangler_error"),
            error_log_path=response.get("data_wrangler_error_log_path"),
            error_prefix="Data wrangling error",
        )
        data_wrangled = response.get("data_wrangled")
        if data_wrangled is not None:
            try:
                datasets, active_dataset_id, _did = register_python_transform_dataset(
                    state_with_datasets=state_with_datasets,  # type: ignore[arg-type]
                    data=data_wrangled,
                    stage="wrangled",
                    label="data_wrangled",
                    created_by="Data_Wrangling_Agent",
                    user_request=last_human,
                    function_code=response.get("data_wrangler_function"),
                    function_name=response.get("data_wrangler_function_name"),
                    function_path=response.get("data_wrangler_function_path"),
                    recommended_steps=response.get("recommended_steps"),
                    parent_id=active_dataset_id,
                    error_text=response.get("data_wrangler_error"),
                    error_log_path=response.get("data_wrangler_error_log_path"),
                    summary=response.get("data_wrangling_summary"),
                )
            except Exception:
                pass
        downstream_resets = (
            {
                "data_cleaned": None,
                "eda_artifacts": None,
                "viz_graph": None,
                "feature_data": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }
            if data_wrangled is not None
            else {}
        )
        return {
            **merged,
            "data_wrangled": data_wrangled,
            "active_data_key": "data_wrangled"
            if data_wrangled is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "data_wrangling": data_wrangled,
                "data_wrangling_details": {
                    "data_wrangler_function": response.get("data_wrangler_function"),
                    "data_wrangler_function_path": response.get(
                        "data_wrangler_function_path"
                    ),
                    "data_wrangler_function_name": response.get(
                        "data_wrangler_function_name"
                    ),
                    "data_wrangler_error": response.get("data_wrangler_error"),
                    "data_wrangler_error_log_path": response.get(
                        "data_wrangler_error_log_path"
                    ),
                    "data_wrangling_summary": response.get("data_wrangling_summary"),
                    "recommended_steps": response.get("recommended_steps"),
                },
            },
            "last_worker": "Data_Wrangling_Agent",
            **downstream_resets,
        }

    def node_cleaning(state: SupervisorDSState):
        print("---DATA CLEANING---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        datasets, active_dataset_id = _ensure_dataset_registry(state)
        state_with_datasets = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }
        active_df = _ensure_df(
            _get_active_data(
                state_with_datasets,  # type: ignore[arg-type]
                [
                    "data_wrangled",
                    "data_raw",
                    "data_sql",
                    "data_cleaned",
                    "feature_data",
                ],
            )
        )
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available to clean. Load a file (or run a SQL query) first.",
                        name="data_cleaning_agent",
                    )
                ],
                "last_worker": "Data_Cleaning_Agent",
            }
        data_cleaning_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
        )
        response = data_cleaning_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(
            merged.get("messages"), "data_cleaning_agent"
        )
        append_agent_feedback(
            merged,
            agent_name="data_cleaning_agent",
            summary_data=response.get("data_cleaned"),
            last_human=_get_last_human(before_msgs),
            format_result_with_llm=_format_result_with_llm,
            extra_text="Cleaning/imputation completed.",
            error_text=response.get("data_cleaner_error"),
            error_log_path=response.get("data_cleaner_error_log_path"),
            error_prefix="Data cleaning error",
        )
        data_cleaned = response.get("data_cleaned")
        if data_cleaned is not None:
            try:
                datasets, active_dataset_id, _did = register_python_transform_dataset(
                    state_with_datasets=state_with_datasets,  # type: ignore[arg-type]
                    data=data_cleaned,
                    stage="cleaned",
                    label="data_cleaned",
                    created_by="Data_Cleaning_Agent",
                    user_request=last_human,
                    function_code=response.get("data_cleaner_function"),
                    function_name=response.get("data_cleaner_function_name"),
                    function_path=response.get("data_cleaner_function_path"),
                    recommended_steps=response.get("recommended_steps"),
                    parent_id=active_dataset_id,
                    error_text=response.get("data_cleaner_error"),
                    error_log_path=response.get("data_cleaner_error_log_path"),
                    summary=response.get("data_cleaning_summary"),
                )
            except Exception:
                pass
        downstream_resets = (
            {
                "eda_artifacts": None,
                "viz_graph": None,
                "feature_data": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }
            if data_cleaned is not None
            else {}
        )
        return {
            **merged,
            "data_cleaned": data_cleaned,
            "active_data_key": "data_cleaned"
            if data_cleaned is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "data_cleaning": data_cleaned,
                "data_cleaning_details": {
                    "data_cleaner_function": response.get("data_cleaner_function"),
                    "data_cleaner_function_path": response.get(
                        "data_cleaner_function_path"
                    ),
                    "data_cleaner_function_name": response.get(
                        "data_cleaner_function_name"
                    ),
                    "data_cleaner_error": response.get("data_cleaner_error"),
                    "data_cleaner_error_log_path": response.get(
                        "data_cleaner_error_log_path"
                    ),
                    "data_cleaning_summary": response.get("data_cleaning_summary"),
                    "recommended_steps": response.get("recommended_steps"),
                },
            },
            "last_worker": "Data_Cleaning_Agent",
            **downstream_resets,
        }

    def node_sql(state: SupervisorDSState):
        print("---SQL DATABASE---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        datasets, active_dataset_id = _ensure_dataset_registry(state)
        sql_database_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
        )
        response = sql_database_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(merged.get("messages"), "sql_database_agent")
        summary_text = _format_result_with_llm(
            "sql_database_agent",
            response.get("data_sql"),
            _get_last_human(before_msgs),
            extra_text=response.get("sql_query_code", ""),
        )
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="sql_database_agent")
            )
        _append_error_message(
            merged,
            "sql_database_agent",
            response.get("sql_database_error"),
            response.get("sql_database_error_log_path"),
            prefix="SQL error",
        )
        data_sql = response.get("data_sql")
        if data_sql is not None:
            try:
                sql_code_full = response.get("sql_query_code")
                sql_code_hash = _sha256_text(sql_code_full)
                sql_code = _truncate_text(sql_code_full, 12000)
                sql_fn_full = response.get("sql_database_function")
                sql_fn_hash = _sha256_text(sql_fn_full)
                sql_fn = _truncate_text(sql_fn_full, 6000)
                datasets, active_dataset_id, _did = _register_dataset(
                    {
                        **state,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    },
                    data=data_sql,
                    stage="sql",
                    label="data_sql",
                    created_by="SQL_Database_Agent",
                    provenance={
                        "source_type": "sql",
                        "user_request": last_human,
                        "transform": {
                            "kind": "sql_query",
                            "sql_query_code": sql_code,
                            "sql_sha256": sql_code_hash,
                            "sql_database_function": sql_fn,
                            "sql_database_function_sha256": sql_fn_hash,
                            "sql_database_function_path": response.get(
                                "sql_database_function_path"
                            ),
                            "sql_database_function_name": response.get(
                                "sql_database_function_name"
                            ),
                        },
                    },
                    parent_id=None,
                    make_active=True,
                )
            except Exception:
                pass
        return {
            **merged,
            "data_sql": data_sql,
            "active_data_key": "data_sql"
            if data_sql is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "sql": {
                    "sql_query_code": response.get("sql_query_code"),
                    "sql_database_function": response.get("sql_database_function"),
                    "sql_database_function_path": response.get(
                        "sql_database_function_path"
                    ),
                    "sql_database_function_name": response.get(
                        "sql_database_function_name"
                    ),
                    "sql_database_error": response.get("sql_database_error"),
                    "sql_database_error_log_path": response.get(
                        "sql_database_error_log_path"
                    ),
                    "recommended_steps": response.get("recommended_steps"),
                    "data_sql": data_sql,
                },
            },
            "last_worker": "SQL_Database_Agent",
        }

    def node_eda(state: SupervisorDSState):
        print("---EDA TOOLS---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs).lower()
        feature_df = _ensure_df(state.get("feature_data"))
        wants_feature_engineered_report = (
            ("feature-engineered" in last_human or "feature engineered" in last_human)
            and (
                "data" in last_human
                or "dataset" in last_human
                or "features" in last_human
            )
        ) or ("engineered features" in last_human)
        active_df = _ensure_df(
            _get_active_data(
                state,
                [
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                    "feature_data",
                ],
            )
        )
        # If the user explicitly references feature-engineered data, prefer it for EDA/reporting.
        if wants_feature_engineered_report and not _is_empty_df(feature_df):
            active_df = feature_df
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for EDA. Load a file (or run a SQL query) first.",
                        name="eda_tools_agent",
                    )
                ],
                "last_worker": "EDA_Tools_Agent",
            }
        eda_tools_agent.invoke_messages(
            messages=before_msgs,
            data_raw=active_df,
        )
        response = eda_tools_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(merged.get("messages"), "eda_tools_agent")
        print(
            f"  eda artifacts keys={response.get('eda_artifacts') and list(response.get('eda_artifacts').keys()) if isinstance(response.get('eda_artifacts'), dict) else None}"
        )
        summary_text = _format_result_with_llm(
            "eda_tools_agent",
            response.get("eda_artifacts", {}).get("describe_dataset")
            if isinstance(response.get("eda_artifacts"), dict)
            else None,
            _get_last_human(before_msgs),
            extra_text="EDA summary.",
        )
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="eda_tools_agent")
            )
        eda_artifacts = response.get("eda_artifacts")
        return {
            **merged,
            "eda_artifacts": eda_artifacts,
            "artifacts": {
                **state.get("artifacts", {}),
                "eda": eda_artifacts,
            },
            "last_worker": "EDA_Tools_Agent",
        }

    def node_viz(state: SupervisorDSState):
        print("---DATA VISUALIZATION---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        active_df = _ensure_df(
            _get_active_data(
                state,
                [
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                    "feature_data",
                ],
            )
        )
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available to plot. Load a file (or run a SQL query) first.",
                        name="data_visualization_agent",
                    )
                ],
                "last_worker": "Data_Visualization_Agent",
            }
        data_visualization_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
        )
        response = data_visualization_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(
            merged.get("messages"), "data_visualization_agent"
        )
        plotly_graph = response.get("plotly_graph")
        viz_error = response.get("data_visualization_error")
        viz_error_path = response.get("data_visualization_error_log_path")
        viz_warning = response.get("data_visualization_warning")
        try:
            from ai_data_science_team.utils.plotly import plotly_from_dict

            fig = plotly_from_dict(plotly_graph) if plotly_graph else None
            trace_types = (
                sorted(
                    {
                        getattr(t, "type", None)
                        for t in getattr(fig, "data", [])
                        if getattr(t, "type", None)
                    }
                )
                if fig is not None
                else []
            )
            title = None
            if fig is not None:
                try:
                    title = getattr(getattr(fig.layout, "title", None), "text", None)
                except Exception:
                    title = None
            viz_summary = (
                response.get("data_visualization_summary") or "Visualization generated."
            )
            if trace_types:
                viz_summary = f"{viz_summary} Trace types: {', '.join(trace_types)}."
            if title:
                viz_summary = f"{viz_summary} Title: {title}."
            merged["messages"].append(
                AIMessage(content=viz_summary, name="data_visualization_agent")
            )
        except Exception:
            pass
        if isinstance(viz_error, str) and viz_error:
            err_bits = [viz_error]
            if isinstance(viz_error_path, str) and viz_error_path:
                err_bits.append(f"Log: {viz_error_path}")
            merged["messages"].append(
                AIMessage(
                    content="Visualization error:\n" + "\n".join(err_bits),
                    name="data_visualization_agent",
                )
            )
        if isinstance(viz_warning, str) and viz_warning:
            merged["messages"].append(
                AIMessage(
                    content="Visualization warning:\n" + viz_warning,
                    name="data_visualization_agent",
                )
            )
        return {
            **merged,
            "viz_graph": plotly_graph,
            "artifacts": {
                **state.get("artifacts", {}),
                "viz": {
                    "plotly_graph": plotly_graph,
                    "data_visualization_function": response.get(
                        "data_visualization_function"
                    ),
                    "error": viz_error,
                    "error_log_path": viz_error_path,
                    "warning": viz_warning,
                },
            },
            "last_worker": "Data_Visualization_Agent",
        }

    def node_fe(state: SupervisorDSState):
        print("---FEATURE ENGINEERING---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        datasets, active_dataset_id = _ensure_dataset_registry(state)
        state_with_datasets = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }
        active_df = _ensure_df(
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
        )
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for feature engineering. Load a file (or run a SQL query) first.",
                        name="feature_engineering_agent",
                    )
                ],
                "last_worker": "Feature_Engineering_Agent",
            }
        feature_engineering_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
            target_variable=state.get("target_variable"),
        )
        response = feature_engineering_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(
            merged.get("messages"), "feature_engineering_agent"
        )
        append_agent_feedback(
            merged,
            agent_name="feature_engineering_agent",
            summary_data=response.get("data_engineered"),
            last_human=_get_last_human(before_msgs),
            format_result_with_llm=_format_result_with_llm,
            extra_text="Feature engineering completed.",
            error_text=response.get("feature_engineer_error"),
            error_log_path=response.get("feature_engineer_error_log_path"),
            error_prefix="Feature engineering error",
        )
        feature_data = response.get("data_engineered")
        if feature_data is not None:
            try:
                datasets, active_dataset_id, _did = register_python_transform_dataset(
                    state_with_datasets=state_with_datasets,  # type: ignore[arg-type]
                    data=feature_data,
                    stage="feature",
                    label="feature_data",
                    created_by="Feature_Engineering_Agent",
                    user_request=last_human,
                    function_code=response.get("feature_engineer_function"),
                    function_name=response.get("feature_engineer_function_name"),
                    function_path=response.get("feature_engineer_function_path"),
                    recommended_steps=response.get("recommended_steps"),
                    parent_id=active_dataset_id,
                    error_text=response.get("feature_engineer_error"),
                    error_log_path=response.get("feature_engineer_error_log_path"),
                    summary=response.get("feature_engineering_summary"),
                )
            except Exception:
                pass
        downstream_resets = (
            {
                "eda_artifacts": None,
                "viz_graph": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }
            if feature_data is not None
            else {}
        )
        return {
            **merged,
            "feature_data": feature_data,
            "active_data_key": "feature_data"
            if feature_data is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "feature_engineering": response,
                "feature_engineering_details": {
                    "feature_engineer_function": response.get(
                        "feature_engineer_function"
                    ),
                    "feature_engineer_function_path": response.get(
                        "feature_engineer_function_path"
                    ),
                    "feature_engineer_function_name": response.get(
                        "feature_engineer_function_name"
                    ),
                    "feature_engineer_error": response.get("feature_engineer_error"),
                    "feature_engineer_error_log_path": response.get(
                        "feature_engineer_error_log_path"
                    ),
                    "feature_engineering_summary": response.get(
                        "feature_engineering_summary"
                    ),
                    "recommended_steps": response.get("recommended_steps"),
                },
            },
            "last_worker": "Feature_Engineering_Agent",
            **downstream_resets,
        }

    def node_h2o(state: SupervisorDSState):
        print("---H2O ML---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = _get_last_human(before_msgs)
        # Respect the supervisor's active dataset selection (dataset registry / active_dataset_id),
        # falling back to known state keys when the registry is absent.
        active_df = _ensure_df(
            _get_active_data(
                state,
                [
                    "feature_data",
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                ],
            )
        )
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for modeling. Load data and (optionally) engineer features first.",
                        name="h2o_ml_agent",
                    )
                ],
                "last_worker": "H2O_ML_Agent",
            }

        # If user asks for prediction/scoring, use an existing model in the H2O cluster
        # instead of retraining AutoML.
        if isinstance(last_human, str) and any(
            w in last_human.lower()
            for w in ("predict", "prediction", "score", "scoring", "inference")
        ):
            import re

            def _extract_run_id(text: str) -> str | None:
                t = text or ""
                m = re.search(r"\b([0-9a-f]{32})\b", t, flags=re.IGNORECASE)
                return m.group(1) if m else None

            def _extract_model_id(text: str) -> str | None:
                t = text or ""
                # Prefer backticked/quoted ids
                m = re.search(r"(?:`|\"|')(?P<mid>[^`\"']+)(?:`|\"|')", t)
                if m and m.group("mid"):
                    mid = m.group("mid").strip()
                    if len(mid) >= 8:
                        return mid
                # Common H2O AutoML id patterns
                m = re.search(r"\b([A-Za-z0-9_]+AutoML_[A-Za-z0-9_]+)\b", t)
                if m and m.group(1):
                    return m.group(1).strip()
                m = re.search(r"\b([A-Za-z0-9_]+_AutoML_[A-Za-z0-9_]+_model_\d+)\b", t)
                if m and m.group(1):
                    return m.group(1).strip()
                return None

            model_id = _extract_model_id(last_human)
            h2o_art = (state.get("artifacts") or {}).get("h2o")
            h2o_art = h2o_art if isinstance(h2o_art, dict) else {}
            cfg = (state.get("artifacts") or {}).get("config") or {}
            cfg = cfg if isinstance(cfg, dict) else {}
            run_id = _extract_run_id(last_human) or h2o_art.get("mlflow_run_id")
            wants_mlflow = "mlflow" in (last_human or "").lower() or bool(run_id)
            if not model_id:
                model_id = h2o_art.get("best_model_id") or None
            if not model_id and isinstance(h2o_art.get("h2o_train_result"), dict):
                model_id = h2o_art["h2o_train_result"].get("best_model_id")

            # Optional: score via MLflow (preferred when available), so predictions work across restarts.
            if wants_mlflow:
                # If no explicit run_id, try newest run in the configured experiment.
                if not (isinstance(run_id, str) and run_id.strip()):
                    try:
                        import mlflow
                        from mlflow.tracking import MlflowClient

                        tracking_uri = cfg.get("mlflow_tracking_uri")
                        if isinstance(tracking_uri, str) and tracking_uri.strip():
                            mlflow.set_tracking_uri(tracking_uri.strip())
                        exp_name = cfg.get("mlflow_experiment_name") or "H2O AutoML"
                        client = MlflowClient()
                        exp = client.get_experiment_by_name(str(exp_name))
                        if exp is not None:
                            runs = client.search_runs(
                                experiment_ids=[exp.experiment_id],
                                order_by=["attributes.start_time DESC"],
                                max_results=25,
                            )

                            def _run_has_model_artifact(rid: str) -> bool:
                                try:
                                    return bool(
                                        client.list_artifacts(rid, path="model")
                                    )
                                except Exception:
                                    return False

                            # Prefer the newest run that actually contains a logged model.
                            for r in runs or []:
                                rid = getattr(getattr(r, "info", None), "run_id", None)
                                if (
                                    isinstance(rid, str)
                                    and rid
                                    and _run_has_model_artifact(rid)
                                ):
                                    run_id = rid
                                    break
                    except Exception:
                        pass

                if isinstance(run_id, str) and run_id.strip():
                    # Best-effort: drop target column if present so we score only features.
                    target = state.get("target_variable")
                    target = (
                        target
                        if isinstance(target, str) and target in active_df.columns
                        else None
                    )
                    x_df = active_df.drop(columns=[target]) if target else active_df
                    try:
                        import mlflow
                        import pandas as pd
                        import h2o
                        from mlflow.tracking import MlflowClient

                        tracking_uri = cfg.get("mlflow_tracking_uri")
                        if isinstance(tracking_uri, str) and tracking_uri.strip():
                            mlflow.set_tracking_uri(tracking_uri.strip())

                        model_uri = f"runs:/{run_id.strip()}/model"
                        # Validate this run actually has a model logged; otherwise provide a helpful message.
                        try:
                            client = MlflowClient()
                            has_model = any(
                                getattr(item, "path", None) == "model"
                                for item in client.list_artifacts(
                                    run_id.strip(), path=""
                                )
                            )
                        except Exception:
                            has_model = True
                        if not has_model:
                            return {
                                "messages": [
                                    AIMessage(
                                        content=(
                                            f"MLflow run `{run_id}` does not contain a logged model at artifact path `model/`.\n\n"
                                            "This usually means you logged workflow artifacts (tables/json) but did not log a model. "
                                            "Train with MLflow enabled (H2O training logs to `model/`), or provide a run id that contains a model."
                                        ),
                                        name="h2o_ml_agent",
                                    )
                                ],
                                "last_worker": "H2O_ML_Agent",
                            }
                        # Prefer mlflow.h2o flavor for stable scoring (handles H2O models and
                        # lets us coerce categorical columns to match training).
                        h2o.init()
                        try:
                            model = mlflow.h2o.load_model(model_uri)
                        except Exception:
                            model = mlflow.pyfunc.load_model(model_uri)

                        if hasattr(model, "predict") and not hasattr(
                            model, "_model_json"
                        ):
                            # Likely a pyfunc wrapper; predict directly.
                            raw_preds = model.predict(x_df)
                            if isinstance(raw_preds, pd.DataFrame):
                                preds_df = raw_preds
                            elif isinstance(raw_preds, pd.Series):
                                preds_df = raw_preds.to_frame(name="prediction")
                            else:
                                preds_df = pd.DataFrame({"prediction": list(raw_preds)})
                        else:
                            frame = h2o.H2OFrame(x_df)
                            # Coerce expected categorical columns to factor.
                            try:
                                out_json = getattr(model, "_model_json", {}) or {}
                                output = (
                                    out_json.get("output")
                                    if isinstance(out_json, dict)
                                    else {}
                                )
                                names = (
                                    output.get("names")
                                    if isinstance(output, dict)
                                    else None
                                )
                                domains = (
                                    output.get("domains")
                                    if isinstance(output, dict)
                                    else None
                                )
                                if isinstance(names, list) and isinstance(
                                    domains, list
                                ):
                                    for col, dom in zip(names, domains):
                                        if dom is None:
                                            continue
                                        if col in frame.columns:
                                            try:
                                                frame[col] = frame[col].asfactor()
                                            except Exception:
                                                pass
                            except Exception:
                                pass

                            preds_h2o = model.predict(frame)
                            preds_df = preds_h2o.as_data_frame(use_pandas=True)

                        try:
                            preds_df.insert(0, "row_id", range(len(preds_df)))
                            if target:
                                preds_df.insert(
                                    1,
                                    f"actual_{target}",
                                    active_df[target].reset_index(drop=True),
                                )
                        except Exception:
                            pass

                        preds_data = preds_df.to_dict()
                    except Exception as e:
                        return {
                            "messages": [
                                AIMessage(
                                    content=(
                                        f"Failed to score with MLflow run `{run_id}`: {e}\n\n"
                                        f"Tried model URI: `runs:/{run_id}/model`.\n\n"
                                        "Tip: scoring must use the same feature schema as training. "
                                        "If you trained on engineered features, set the active dataset to that feature dataset before scoring."
                                    ),
                                    name="h2o_ml_agent",
                                )
                            ],
                            "last_worker": "H2O_ML_Agent",
                        }

                    datasets, active_dataset_id = _ensure_dataset_registry(state)
                    try:
                        label = f"predictions_mlflow_{run_id}"[:80]
                        datasets, active_dataset_id, pred_id = _register_dataset(
                            {
                                **state,
                                "datasets": datasets,
                                "active_dataset_id": active_dataset_id,
                            },
                            data=preds_data,
                            stage="wrangled",
                            label=label,
                            created_by="H2O_ML_Agent",
                            provenance={
                                "source_type": "agent",
                                "user_request": last_human,
                                "transform": {
                                    "kind": "mlflow_predict",
                                    "run_id": run_id,
                                    "model_uri": f"runs:/{run_id.strip()}/model",
                                    "dropped_target": bool(target),
                                },
                            },
                            parent_id=active_dataset_id,
                            make_active=True,
                        )
                    except Exception:
                        pred_id = None

                    try:
                        preview_md = preds_df.head(5).to_markdown(index=False)
                        msg = f"Scored dataset with MLflow run `{run_id}`. Predictions shape: {preds_df.shape}.\n\n{preview_md}"
                    except Exception:
                        msg = f"Scored dataset with MLflow run `{run_id}`."

                    return {
                        "messages": [AIMessage(content=msg, name="h2o_ml_agent")],
                        "data_wrangled": preds_data,
                        "active_data_key": "data_wrangled",
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                        "artifacts": {
                            **state.get("artifacts", {}),
                            "mlflow_predictions": {
                                "run_id": run_id,
                                "predictions_dataset_id": pred_id,
                            },
                        },
                        "last_worker": "H2O_ML_Agent",
                    }
            if not isinstance(model_id, str) or not model_id.strip():
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                "To make predictions, provide an H2O `model_id` (or train a model first). "
                                "Example: `predict with model `XGBoost_grid_...` on the dataset`."
                            ),
                            name="h2o_ml_agent",
                        )
                    ],
                    "last_worker": "H2O_ML_Agent",
                }

            # Best-effort: drop target column if present so we score only features.
            target = state.get("target_variable")
            target = (
                target
                if isinstance(target, str) and target in active_df.columns
                else None
            )
            x_df = active_df.drop(columns=[target]) if target else active_df

            try:
                import h2o

                h2o.init()
                model = h2o.get_model(model_id.strip())
                frame = h2o.H2OFrame(x_df)
                preds_h2o = model.predict(frame)
                preds_df = preds_h2o.as_data_frame(use_pandas=True)
                try:
                    preds_df.insert(0, "row_id", range(len(preds_df)))
                    if target:
                        preds_df.insert(
                            1,
                            f"actual_{target}",
                            active_df[target].reset_index(drop=True),
                        )
                except Exception:
                    pass
                preds_data = preds_df.to_dict()
            except Exception as e:
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                f"Failed to score with model `{model_id}`: {e}\n\n"
                                "Tip: model IDs are only available while the H2O cluster is running. "
                                "If you restarted, retrain or load a saved model."
                            ),
                            name="h2o_ml_agent",
                        )
                    ],
                    "last_worker": "H2O_ML_Agent",
                }

            # Register predictions as a new dataset (tabular output) for downstream viz/EDA.
            datasets, active_dataset_id = _ensure_dataset_registry(state)
            try:
                label = f"predictions_{model_id}"[:80]
                datasets, active_dataset_id, pred_id = _register_dataset(
                    {
                        **state,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    },
                    data=preds_data,
                    stage="wrangled",
                    label=label,
                    created_by="H2O_ML_Agent",
                    provenance={
                        "source_type": "agent",
                        "user_request": last_human,
                        "transform": {
                            "kind": "h2o_predict",
                            "model_id": model_id,
                            "dropped_target": bool(target),
                            "n_rows": int(getattr(x_df, "shape", (0, 0))[0] or 0),
                            "n_cols": int(getattr(x_df, "shape", (0, 0))[1] or 0),
                        },
                    },
                    parent_id=active_dataset_id,
                    make_active=True,
                )
            except Exception:
                pred_id = None

            try:
                preview_md = preds_df.head(5).to_markdown(index=False)
                msg = f"Scored dataset with model `{model_id}`. Predictions shape: {preds_df.shape}.\n\n{preview_md}"
            except Exception:
                msg = f"Scored dataset with model `{model_id}`."

            return {
                "messages": [AIMessage(content=msg, name="h2o_ml_agent")],
                "data_wrangled": preds_data,
                "active_data_key": "data_wrangled",
                "datasets": datasets,
                "active_dataset_id": active_dataset_id,
                "artifacts": {
                    **state.get("artifacts", {}),
                    "h2o_predictions": {
                        "model_id": model_id,
                        "predictions_dataset_id": pred_id,
                    },
                },
                "last_worker": "H2O_ML_Agent",
            }

        h2o_ml_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
            target_variable=state.get("target_variable"),
        )
        response = h2o_ml_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(merged.get("messages"), "h2o_ml_agent")
        summary_text = _format_result_with_llm(
            "h2o_ml_agent",
            response.get("leaderboard"),
            _get_last_human(before_msgs),
            extra_text="H2O AutoML results.",
        )
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="h2o_ml_agent")
            )
        _append_error_message(
            merged,
            "h2o_ml_agent",
            response.get("h2o_train_error"),
            response.get("h2o_train_error_log_path"),
            prefix="Model training error",
        )
        mlflow_run_id = response.get("mlflow_run_id")
        if mlflow_run_id:
            merged["messages"].append(
                AIMessage(
                    content=f"MLflow logging enabled. Run ID: `{mlflow_run_id}`",
                    name="h2o_ml_agent",
                )
            )
            model_uri = response.get("mlflow_model_uri")
            if isinstance(model_uri, str) and model_uri.strip():
                merged["messages"].append(
                    AIMessage(
                        content=f"MLflow model URI: `{model_uri.strip()}`",
                        name="h2o_ml_agent",
                    )
                )
        leaderboard = response.get("leaderboard")
        return {
            **merged,
            "model_info": leaderboard,
            "mlflow_artifacts": response.get("mlflow_model")
            or (
                {
                    "run_id": mlflow_run_id,
                    "model_uri": response.get("mlflow_model_uri"),
                }
                if mlflow_run_id
                else None
            ),
            "artifacts": {
                **state.get("artifacts", {}),
                "h2o": response,
                "h2o_details": {
                    "h2o_train_error": response.get("h2o_train_error"),
                    "h2o_train_error_log_path": response.get(
                        "h2o_train_error_log_path"
                    ),
                    "best_model_id": response.get("best_model_id"),
                    "leaderboard": response.get("leaderboard"),
                    "mlflow_run_id": mlflow_run_id,
                    "mlflow_model_uri": response.get("mlflow_model_uri"),
                },
            },
            "last_worker": "H2O_ML_Agent",
        }

    def node_mlflow(state: SupervisorDSState):
        print("---MLFLOW TOOLS---")
        before_msgs = list(state.get("messages", []) or [])
        mlflow_tools_agent.invoke_messages(
            messages=before_msgs,
        )
        response = mlflow_tools_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(merged.get("messages"), "mlflow_tools_agent")
        summary_text = _format_result_with_llm(
            "mlflow_tools_agent",
            response.get("mlflow_artifacts"),
            _get_last_human(before_msgs),
            extra_text="MLflow artifacts.",
        )
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="mlflow_tools_agent")
            )
        mlflow_artifacts = response.get("mlflow_artifacts")
        return {
            **merged,
            "mlflow_artifacts": mlflow_artifacts,
            "artifacts": {
                **state.get("artifacts", {}),
                "mlflow": mlflow_artifacts,
            },
            "last_worker": "MLflow_Tools_Agent",
        }

    def node_eval(state: SupervisorDSState):
        print("---MODEL EVALUATION---")
        before_msgs = list(state.get("messages", []) or [])
        feature_df = _ensure_df(state.get("feature_data"))
        active_df = (
            feature_df
            if not _is_empty_df(feature_df)
            else _ensure_df(
                _get_active_data(
                    state, ["data_cleaned", "data_wrangled", "data_sql", "data_raw"]
                )
            )
        )
        if _is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for evaluation. Load data and train a model first.",
                        name="model_evaluation_agent",
                    )
                ],
                "last_worker": "Model_Evaluation_Agent",
            }
        h2o_art = (state.get("artifacts") or {}).get("h2o")
        model_artifacts = h2o_art if isinstance(h2o_art, dict) else {}
        model_evaluation_agent.invoke_messages(
            messages=before_msgs,
            data_raw=active_df,
            model_artifacts=model_artifacts,
            target_variable=state.get("target_variable"),
        )
        response = model_evaluation_agent.response or {}
        merged = _merge_messages(before_msgs, response)
        merged["messages"] = _tag_messages(
            merged.get("messages"), "model_evaluation_agent"
        )
        eval_artifacts = response.get("eval_artifacts")
        plotly_graph = response.get("plotly_graph")
        if isinstance(eval_artifacts, dict) and eval_artifacts.get("error"):
            merged["messages"].append(
                AIMessage(
                    content="Model evaluation error:\n" + str(eval_artifacts.get("error")),
                    name="model_evaluation_agent",
                )
            )
        return {
            **merged,
            "eval_artifacts": eval_artifacts,
            "artifacts": {
                **state.get("artifacts", {}),
                "eval": {
                    "eval_artifacts": eval_artifacts,
                    "plotly_graph": plotly_graph,
                },
            },
            "last_worker": "Model_Evaluation_Agent",
        }

    def node_mlflow_log(state: SupervisorDSState):
        print("---MLFLOW LOGGING---")
        before_msgs = list(state.get("messages", []) or [])

        # Pull config from the supervisor artifacts (optional).
        cfg: dict[str, Any] = {}
        try:
            cfg = (state.get("artifacts") or {}).get("config") or {}
        except Exception:
            cfg = {}

        tracking_uri = cfg.get("mlflow_tracking_uri") if isinstance(cfg, dict) else None
        artifact_root = (
            cfg.get("mlflow_artifact_root") if isinstance(cfg, dict) else None
        )
        experiment_name = (
            cfg.get("mlflow_experiment_name") if isinstance(cfg, dict) else None
        )

        # Attempt to reuse an existing run id (from H2O training) if present.
        run_id = None
        h2o_art = (state.get("artifacts") or {}).get("h2o")
        if isinstance(h2o_art, dict):
            run_id = h2o_art.get("mlflow_run_id")
            if not run_id and isinstance(h2o_art.get("h2o_train_result"), dict):
                run_id = h2o_art["h2o_train_result"].get("mlflow_run_id")
            if not run_id and isinstance(h2o_art.get("model_results"), dict):
                run_id = h2o_art["model_results"].get("mlflow_run_id")

        feature_df = _ensure_df(state.get("feature_data"))
        active_df = (
            feature_df
            if not _is_empty_df(feature_df)
            else _ensure_df(
                _get_active_data(
                    state, ["data_cleaned", "data_wrangled", "data_sql", "data_raw"]
                )
            )
        )
        viz_graph = state.get("viz_graph")
        eval_payload = (state.get("artifacts") or {}).get("eval")
        eval_artifacts = state.get("eval_artifacts")
        eval_plot = None
        if isinstance(eval_payload, dict):
            eval_plot = eval_payload.get("plotly_graph")

        logged: dict = {"tables": [], "figures": [], "dicts": [], "metrics": []}
        message_lines: list[str] = []

        try:
            import mlflow
            import json
            from pathlib import Path

            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            if experiment_name:
                # Best-effort: if an artifact root is configured, ensure the experiment exists
                # with that artifact location (applies only when creating new experiments).
                try:
                    from mlflow.tracking import MlflowClient
                    import re

                    if isinstance(artifact_root, str) and artifact_root.strip():
                        root = Path(artifact_root).expanduser().resolve()
                        root.mkdir(parents=True, exist_ok=True)
                        safe_name = re.sub(
                            r"[^A-Za-z0-9._-]+", "_", str(experiment_name)
                        ).strip("_")
                        safe_name = safe_name or "experiment"
                        artifact_location = (root / safe_name).as_uri()
                        client = MlflowClient(tracking_uri=tracking_uri)
                        exp = client.get_experiment_by_name(str(experiment_name))
                        if exp is None:
                            client.create_experiment(
                                name=str(experiment_name),
                                artifact_location=artifact_location,
                            )
                except Exception:
                    pass
                mlflow.set_experiment(experiment_name)

            # Start or resume the run
            with mlflow.start_run(run_id=run_id) as run:
                run_id = run.info.run_id

                # Basic tags/params
                try:
                    mlflow.set_tags(
                        {
                            "app": "supervisor_ds_team",
                            "active_data_key": state.get("active_data_key") or "",
                            "active_dataset_id": state.get("active_dataset_id") or "",
                        }
                    )
                except Exception:
                    pass

                # Log a small dataset preview + schema
                if active_df is not None and not _is_empty_df(active_df):
                    try:
                        mlflow.log_table(
                            active_df.head(200),
                            artifact_file="tables/data_preview.json",
                        )
                        logged["tables"].append("tables/data_preview.json")
                    except Exception:
                        pass
                    try:
                        schema = {
                            "columns": [
                                {"name": str(c), "dtype": str(active_df[c].dtype)}
                                for c in list(active_df.columns)
                            ],
                            "shape": list(active_df.shape),
                        }
                        mlflow.log_dict(schema, artifact_file="tables/schema.json")
                        logged["dicts"].append("tables/schema.json")
                    except Exception:
                        pass

                # Log pipeline (dataset lineage + reproduction script)
                try:
                    from ai_data_science_team.utils.pipeline import (
                        build_pipeline_snapshot,
                    )

                    ds = state.get("datasets")
                    ds = ds if isinstance(ds, dict) else {}
                    pipe = build_pipeline_snapshot(
                        ds, active_dataset_id=state.get("active_dataset_id")
                    )
                    if isinstance(pipe, dict) and pipe.get("lineage"):
                        pipe_spec = dict(pipe)
                        script = pipe_spec.pop("script", None)
                        mlflow.log_dict(
                            pipe_spec, artifact_file="pipeline/pipeline_spec.json"
                        )
                        logged["dicts"].append("pipeline/pipeline_spec.json")
                        if isinstance(script, str) and script.strip():
                            if hasattr(mlflow, "log_text"):
                                mlflow.log_text(
                                    script, artifact_file="pipeline/pipeline_repro.py"
                                )
                                logged["dicts"].append("pipeline/pipeline_repro.py")
                            else:
                                mlflow.log_dict(
                                    {"script": script},
                                    artifact_file="pipeline/pipeline_repro.json",
                                )
                                logged["dicts"].append("pipeline/pipeline_repro.json")
                        try:
                            if pipe.get("pipeline_hash"):
                                mlflow.set_tag(
                                    "pipeline_hash", str(pipe.get("pipeline_hash"))
                                )
                        except Exception:
                            pass
                except Exception:
                    pass

                # Log visualization plot (if any)
                if viz_graph:
                    try:
                        mlflow.log_dict(viz_graph, artifact_file="plots/viz.json")
                        logged["dicts"].append("plots/viz.json")
                    except Exception:
                        pass
                    try:
                        import plotly.io as pio

                        fig = pio.from_json(json.dumps(viz_graph))
                        mlflow.log_figure(fig, artifact_file="plots/viz.html")
                        logged["figures"].append("plots/viz.html")
                    except Exception:
                        pass

                # Log evaluation artifacts + metrics + plot
                if eval_artifacts:
                    try:
                        mlflow.log_dict(
                            eval_artifacts,
                            artifact_file="evaluation/eval_artifacts.json",
                        )
                        logged["dicts"].append("evaluation/eval_artifacts.json")
                    except Exception:
                        pass
                    try:
                        metrics = (
                            eval_artifacts.get("metrics")
                            if isinstance(eval_artifacts, dict)
                            else None
                        )
                        if isinstance(metrics, dict):
                            safe = {}
                            for k, v in metrics.items():
                                try:
                                    safe[str(k)] = float(v)
                                except Exception:
                                    continue
                            if safe:
                                mlflow.log_metrics(safe)
                                logged["metrics"].extend(list(safe.keys()))
                    except Exception:
                        pass
                if eval_plot:
                    try:
                        mlflow.log_dict(
                            eval_plot, artifact_file="evaluation/eval_plot.json"
                        )
                        logged["dicts"].append("evaluation/eval_plot.json")
                    except Exception:
                        pass
                    try:
                        import plotly.io as pio

                        fig = pio.from_json(json.dumps(eval_plot))
                        mlflow.log_figure(
                            fig, artifact_file="evaluation/eval_plot.html"
                        )
                        logged["figures"].append("evaluation/eval_plot.html")
                    except Exception:
                        pass

        except Exception as e:
            message_lines.append(f"MLflow logging failed: {e}")

        if run_id:
            message_lines.append(f"Logged workflow artifacts to MLflow run `{run_id}`.")
        if any(logged.values()):
            message_lines.append(
                "Logged: "
                + ", ".join(
                    [
                        *(
                            [f"{len(logged['tables'])} table(s)"]
                            if logged["tables"]
                            else []
                        ),
                        *(
                            [f"{len(logged['figures'])} figure(s)"]
                            if logged["figures"]
                            else []
                        ),
                        *(
                            [f"{len(logged['dicts'])} json artifact(s)"]
                            if logged["dicts"]
                            else []
                        ),
                        *(
                            [f"{len(logged['metrics'])} metric(s)"]
                            if logged["metrics"]
                            else []
                        ),
                    ]
                )
                + "."
            )
        if not message_lines:
            message_lines.append(
                "No artifacts were available to log yet. Train a model and/or create a chart first."
            )

        msg = "\n".join(message_lines)
        merged = {"messages": [AIMessage(content=msg, name="mlflow_logging_agent")]}
        merged["messages"] = _tag_messages(
            merged.get("messages"), "mlflow_logging_agent"
        )
        return {
            **merged,
            "mlflow_artifacts": {"run_id": run_id, "logged": logged},
            "artifacts": {
                **state.get("artifacts", {}),
                "mlflow_log": {"run_id": run_id, "logged": logged},
            },
            "last_worker": "MLflow_Logging_Agent",
        }

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


class SupervisorDSTeam:
    """
    OO wrapper for the supervisor-led data science team.

    Mirrors the pattern used by other agents: holds a compiled graph,
    exposes message-first helpers, and keeps the latest response.
    """

    def __init__(
        self,
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
        self._params = {
            "model": model,
            "workflow_planner_agent": workflow_planner_agent,
            "data_loader_agent": data_loader_agent,
            "data_wrangling_agent": data_wrangling_agent,
            "data_cleaning_agent": data_cleaning_agent,
            "eda_tools_agent": eda_tools_agent,
            "data_visualization_agent": data_visualization_agent,
            "sql_database_agent": sql_database_agent,
            "feature_engineering_agent": feature_engineering_agent,
            "h2o_ml_agent": h2o_ml_agent,
            "mlflow_tools_agent": mlflow_tools_agent,
            "model_evaluation_agent": model_evaluation_agent,
            "checkpointer": checkpointer,
            "temperature": temperature,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response: Optional[dict] = None

    def _make_compiled_graph(self):
        self.response = None
        return make_supervisor_ds_team(
            model=self._params["model"],
            workflow_planner_agent=self._params["workflow_planner_agent"],
            data_loader_agent=self._params["data_loader_agent"],
            data_wrangling_agent=self._params["data_wrangling_agent"],
            data_cleaning_agent=self._params["data_cleaning_agent"],
            eda_tools_agent=self._params["eda_tools_agent"],
            data_visualization_agent=self._params["data_visualization_agent"],
            sql_database_agent=self._params["sql_database_agent"],
            feature_engineering_agent=self._params["feature_engineering_agent"],
            h2o_ml_agent=self._params["h2o_ml_agent"],
            mlflow_tools_agent=self._params["mlflow_tools_agent"],
            model_evaluation_agent=self._params["model_evaluation_agent"],
            checkpointer=self._params["checkpointer"],
            temperature=self._params["temperature"],
        )

    def update_params(self, **kwargs):
        """
        Update parameters (e.g., swap sub-agents or model) and rebuild the graph.
        """
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_messages(
        self,
        messages: Sequence[BaseMessage],
        artifacts: Optional[dict] = None,
        **kwargs,
    ):
        """
        Invoke the team with a message list (recommended for supervisor/teams).
        """
        self.response = self._compiled_graph.invoke(
            {"messages": messages, "artifacts": artifacts or {}},
            **kwargs,
        )
        return None

    async def ainvoke_messages(
        self,
        messages: Sequence[BaseMessage],
        artifacts: Optional[dict] = None,
        **kwargs,
    ):
        """
        Async version of invoke_messages.
        """
        self.response = await self._compiled_graph.ainvoke(
            {"messages": messages, "artifacts": artifacts or {}},
            **kwargs,
        )
        return None

    def invoke_agent(
        self, user_instructions: str, artifacts: Optional[dict] = None, **kwargs
    ):
        """
        Convenience wrapper for a single human prompt.
        """
        msg = HumanMessage(content=user_instructions)
        return self.invoke_messages(messages=[msg], artifacts=artifacts, **kwargs)

    async def ainvoke_agent(
        self, user_instructions: str, artifacts: Optional[dict] = None, **kwargs
    ):
        msg = HumanMessage(content=user_instructions)
        return await self.ainvoke_messages(
            messages=[msg], artifacts=artifacts, **kwargs
        )

    def invoke(self, input: dict, **kwargs):
        """
        Generic invoke passthrough (for backward compatibility).
        """
        self.response = self._compiled_graph.invoke(input, **kwargs)
        return self.response

    async def ainvoke(self, input: dict, **kwargs):
        self.response = await self._compiled_graph.ainvoke(input, **kwargs)
        return self.response

    def get_ai_message(self, markdown: bool = False):
        """
        Return the last assistant/ai message.
        """
        if not self.response or "messages" not in self.response:
            return None
        last_ai = None
        for msg in reversed(self.response.get("messages", [])):
            if isinstance(msg, AIMessage) or getattr(msg, "role", None) in (
                "assistant",
                "ai",
            ):
                last_ai = msg
                break
        if last_ai is None:
            return None
        content = getattr(last_ai, "content", "")
        return Markdown(content) if markdown else content

    def get_artifacts(self):
        """
        Return aggregated artifacts dict from the supervisor state.
        """
        if self.response:
            return self.response.get("artifacts")
        return None

    def show(self, xray: int = 0):
        """
        Displays the supervisor team's state graph as a Mermaid diagram.
        """
        try:
            from IPython.display import Image, display

            display(Image(self._compiled_graph.get_graph(xray=xray).draw_mermaid_png()))
        except Exception:
            return None

    def _repr_mimebundle_(self, *args, **kwargs):
        """
        Jupyter/IPython rich display: render the supervisor graph as a Mermaid PNG.
        """
        try:
            png = self._compiled_graph.get_graph(xray=0).draw_mermaid_png()
            return {"image/png": png, "text/plain": repr(self)}
        except Exception:
            return {"text/plain": repr(self)}
