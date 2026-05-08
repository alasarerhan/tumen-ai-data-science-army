import type { Edge, Node } from "reactflow";
import {
  flowToSpec,
  inspectWorkflowGraphSpec,
  isValidCronExpression,
  specToFlow,
  specToYaml,
  validateWorkflowSpec,
  yamlToSpec,
  type WorkflowNodeData,
} from "./workflowDesigner";
import { workflowChainRulesFixture } from "../test/fixtures/workflowChainRules";

describe("workflowDesigner utils", () => {
  it("converts flow graph to spec and back", () => {
    const nodes: Node<WorkflowNodeData>[] = [
      {
        id: "n1",
        type: "workflowNode",
        position: { x: 10, y: 20 },
        data: { label: "Data Loader", kind: "data", agent: "DataLoaderToolsAgent", status: "idle" },
      },
      {
        id: "n2",
        type: "workflowNode",
        position: { x: 120, y: 20 },
        data: { label: "Data Cleaning", kind: "data", agent: "DataCleaningAgent", status: "running" },
      },
    ];

    const edges: Edge[] = [{ id: "e1", source: "n1", target: "n2" }];

    const spec = flowToSpec({
      name: "Pipeline",
      description: "Demo",
      cron: "0 8 * * 1-5",
      nodes,
      edges,
    }, workflowChainRulesFixture);

    expect(spec.graph.nodes).toHaveLength(2);
    expect(spec.graph.edges).toHaveLength(1);

    const restored = specToFlow(spec, workflowChainRulesFixture);
    expect(restored.nodes[0].data.label).toBe("Data Loader");
    expect(restored.edges[0].source).toBe("n1");
    expect(restored.cron).toBe("0 8 * * 1-5");
  });

  it("serializes and parses yaml", () => {
    const spec = {
      version: "1.0.0",
      name: "YAML Test",
      graph: {
        nodes: [{ id: "n1", label: "Data Loader", agent: "DataLoaderToolsAgent", kind: "data", position: { x: 0, y: 0 } }],
        edges: [],
      },
    };

    const yaml = specToYaml(spec as any);
    const parsed = yamlToSpec(yaml, workflowChainRulesFixture);

    expect(parsed.name).toBe("YAML Test");
    expect(parsed.graph.nodes[0].id).toBe("n1");
  });

  it("rejects invalid cron", () => {
    expect(isValidCronExpression("0 8 * * 1-5")).toBe(true);
    expect(isValidCronExpression("not-a-cron")).toBe(false);
  });

  it("rejects dangling edges", () => {
    const invalid = {
      version: "1.0.0",
      name: "Invalid graph",
      graph: {
        nodes: [{ id: "n1", label: "Data Loader", agent: "DataLoaderToolsAgent", kind: "data", position: { x: 0, y: 0 } }],
        edges: [{ id: "e1", source: "n1", target: "missing" }],
      },
    };

    expect(() => validateWorkflowSpec(invalid as any, workflowChainRulesFixture)).toThrow("references unknown node");
  });

  it("warns on advisory chains without rejecting them", () => {
    const advisory = {
      version: "1.0.0",
      name: "EDA to cleaning",
      graph: {
        nodes: [
          { id: "n1", label: "EDA", agent: "EDAToolsAgent", kind: "analysis", position: { x: 0, y: 0 } },
          { id: "n2", label: "Data Cleaning", agent: "DataCleaningAgent", kind: "data", position: { x: 100, y: 0 } },
        ],
        edges: [{ id: "e1", source: "n1", target: "n2" }],
      },
    };

    const result = inspectWorkflowGraphSpec(advisory as any, workflowChainRulesFixture);
    expect(result.errors).toHaveLength(0);
    expect(result.warnings.some((issue) => issue.code === "conditional_edge")).toBe(true);
  });

  it("rejects blocked chains", () => {
    const blocked = {
      version: "1.0.0",
      name: "Bad chain",
      graph: {
        nodes: [
          { id: "n1", label: "Visualization", agent: "DataVisualizationAgent", kind: "analysis", position: { x: 0, y: 0 } },
          { id: "n2", label: "H2O ML", agent: "H2OMLAgent", kind: "ml", position: { x: 100, y: 0 } },
        ],
        edges: [{ id: "e1", source: "n1", target: "n2" }],
      },
    };

    expect(() => validateWorkflowSpec(blocked as any, workflowChainRulesFixture)).toThrow("cannot chain directly");
  });
});
