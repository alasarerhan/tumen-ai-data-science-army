import type { Edge, Node } from "reactflow";
import {
  flowToSpec,
  isValidCronExpression,
  specToFlow,
  specToYaml,
  validateWorkflowSpec,
  yamlToSpec,
  type WorkflowNodeData,
} from "./workflowDesigner";

describe("workflowDesigner utils", () => {
  it("converts flow graph to spec and back", () => {
    const nodes: Node<WorkflowNodeData>[] = [
      {
        id: "n1",
        type: "workflowNode",
        position: { x: 10, y: 20 },
        data: { label: "Load", kind: "eda", status: "idle" },
      },
      {
        id: "n2",
        type: "workflowNode",
        position: { x: 120, y: 20 },
        data: { label: "Train", kind: "ml", status: "running" },
      },
    ];

    const edges: Edge[] = [{ id: "e1", source: "n1", target: "n2" }];

    const spec = flowToSpec({
      name: "Pipeline",
      description: "Demo",
      cron: "0 8 * * 1-5",
      nodes,
      edges,
    });

    expect(spec.graph.nodes).toHaveLength(2);
    expect(spec.graph.edges).toHaveLength(1);

    const restored = specToFlow(spec);
    expect(restored.nodes[0].data.label).toBe("Load");
    expect(restored.edges[0].source).toBe("n1");
    expect(restored.cron).toBe("0 8 * * 1-5");
  });

  it("serializes and parses yaml", () => {
    const spec = {
      version: "1.0.0",
      name: "YAML Test",
      graph: {
        nodes: [{ id: "n1", label: "Node", kind: "eda", position: { x: 0, y: 0 } }],
        edges: [],
      },
    };

    const yaml = specToYaml(spec as any);
    const parsed = yamlToSpec(yaml);

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
        nodes: [{ id: "n1", label: "Node", kind: "eda", position: { x: 0, y: 0 } }],
        edges: [{ id: "e1", source: "n1", target: "missing" }],
      },
    };

    expect(() => validateWorkflowSpec(invalid as any)).toThrow("references unknown node");
  });
});
