import type { WorkflowChainRuleset } from "../../api/workflowChainRules";

export const workflowChainRulesFixture: WorkflowChainRuleset = {
  version: "1.0.0",
  agents: [
    {
      key: "DataLoaderToolsAgent",
      label: "Data Loader",
      kind: "data",
      color: "#10b981",
      aliases: ["Data Loader", "loader"],
      safe_next: ["DataCleaningAgent", "EDAToolsAgent"],
      conditional_next: ["H2OMLAgent"],
    },
    {
      key: "DataCleaningAgent",
      label: "Data Cleaning",
      kind: "data",
      color: "#10b981",
      aliases: ["Data Cleaning", "clean"],
      safe_next: ["FeatureEngineeringAgent"],
      conditional_next: ["H2OMLAgent"],
    },
    {
      key: "EDAToolsAgent",
      label: "EDA",
      kind: "analysis",
      color: "#0ea5e9",
      aliases: ["EDA", "eda"],
      safe_next: [],
      conditional_next: ["DataCleaningAgent", "H2OMLAgent"],
    },
    {
      key: "DataVisualizationAgent",
      label: "Visualization",
      kind: "analysis",
      color: "#06b6d4",
      aliases: ["Visualization", "viz"],
      safe_next: [],
      conditional_next: [],
    },
    {
      key: "FeatureEngineeringAgent",
      label: "Feature Engineering",
      kind: "ml",
      color: "#6366f1",
      aliases: ["Feature Engineering", "feature"],
      safe_next: ["H2OMLAgent"],
      conditional_next: [],
    },
    {
      key: "H2OMLAgent",
      label: "H2O ML",
      kind: "ml",
      color: "#6366f1",
      aliases: ["H2O ML", "model"],
      safe_next: [],
      conditional_next: [],
    },
  ],
  requirements: {
    H2OMLAgent: {
      target_variable: true,
    },
  },
};
