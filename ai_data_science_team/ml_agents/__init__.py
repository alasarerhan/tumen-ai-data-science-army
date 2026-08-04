try:
    from ai_data_science_team.ml_agents.h2o_ml_agent import (  # noqa: F401
        H2OMLAgent,
        make_h2o_ml_agent,
    )
except Exception:  # h2o / IPython not installed
    pass

try:
    from ai_data_science_team.ml_agents.mlflow_tools_agent import (  # noqa: F401
        MLflowToolsAgent,
        make_mlflow_tools_agent,
    )
except Exception:
    pass

try:
    from ai_data_science_team.ml_agents.model_evaluation_agent import (
        ModelEvaluationAgent,  # noqa: F401
    )
except Exception:  # agent_templates / IPython not installed
    pass

from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent  # noqa: F401
from ai_data_science_team.ml_agents.time_series_agents import (  # noqa: F401
    AutoForecastAgent,
    ForecastEvaluationAgent,
    ForecastingModelAgent,
    TimeSeriesEDAAgent,
)
