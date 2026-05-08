import type { Edge, Node } from "reactflow";
import YAML from "yaml";
import cronstrue from "cronstrue";
import {
  inspectWorkflowSpec,
  validateWorkflowSpecWithRules,
  type WorkflowValidationIssue,
} from "./workflowChainValidator";
import type { WorkflowChainRuleset } from "../api/workflowChainRules";

export interface WorkflowNodeData {
  label: string;
  kind: string;
  agent?: string;
  status?: "idle" | "running" | "success" | "error";
}

export interface WorkflowSpecDocument {
  version: string;
  name: string;
  description?: string;
  schedule?: {
    cron?: string;
    timezone?: string;
  };
  graph: {
    nodes: Array<{
      id: string;
      label: string;
      kind: string;
      agent?: string;
      position: { x: number; y: number };
      status?: string;
    }>;
    edges: Array<{ id: string; source: string; target: string }>;
  };
  target_variable?: string;
}

export function isValidCronExpression(expression: string): boolean {
  const value = expression.trim();
  if (!value) return false;
  try {
    cronstrue.toString(value, { throwExceptionOnParseError: true });
    return true;
  } catch {
    return false;
  }
}

export function inspectWorkflowGraphSpec(
  spec: WorkflowSpecDocument,
  ruleset?: WorkflowChainRuleset,
): {
  warnings: WorkflowValidationIssue[];
  errors: WorkflowValidationIssue[];
} {
  return inspectWorkflowSpec(spec, ruleset);
}

export function validateWorkflowSpec(spec: WorkflowSpecDocument, ruleset?: WorkflowChainRuleset): WorkflowSpecDocument {
  if (!spec.name || !spec.name.trim()) {
    throw new Error("Workflow name is required");
  }
  if (!spec.graph || !Array.isArray(spec.graph.nodes) || !Array.isArray(spec.graph.edges)) {
    throw new Error("Invalid workflow spec. Expected graph.nodes and graph.edges");
  }
  if (spec.graph.nodes.length === 0) {
    throw new Error("Workflow must contain at least one node");
  }

  const nodeIds = new Set<string>();
  for (const node of spec.graph.nodes) {
    if (!node.id || !node.label || !node.kind) {
      throw new Error("Each node must include id, label, and kind");
    }
    if (nodeIds.has(node.id)) {
      throw new Error(`Duplicate node id detected: ${node.id}`);
    }
    nodeIds.add(node.id);
  }

  for (const edge of spec.graph.edges) {
    if (!edge.id || !edge.source || !edge.target) {
      throw new Error("Each edge must include id, source, and target");
    }
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      throw new Error(`Edge ${edge.id} references unknown node`);
    }
  }

  const cron = spec.schedule?.cron;
  if (cron && !isValidCronExpression(cron)) {
    throw new Error("Invalid cron expression");
  }

  return validateWorkflowSpecWithRules(spec, ruleset);
}

export function flowToSpec(params: {
  name: string;
  description?: string;
  cron?: string;
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
}, ruleset?: WorkflowChainRuleset): WorkflowSpecDocument {
  const spec: WorkflowSpecDocument = {
    version: "1.0.0",
    name: params.name,
    description: params.description,
    schedule: {
      cron: params.cron,
      timezone: "UTC",
    },
    graph: {
      nodes: params.nodes.map((node) => ({
        id: node.id,
        label: node.data.label,
        kind: node.data.kind,
        agent: node.data.agent,
        position: node.position,
        status: node.data.status,
      })),
      edges: params.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
      })),
    },
  };
  return validateWorkflowSpec(spec, ruleset);
}

export function specToFlow(spec: WorkflowSpecDocument, ruleset?: WorkflowChainRuleset): {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  cron: string;
  name: string;
  description: string;
} {
  const validated = validateWorkflowSpec(spec, ruleset);
  return {
    name: validated.name,
    description: validated.description ?? "",
    cron: validated.schedule?.cron ?? "0 8 * * 1-5",
    nodes: validated.graph.nodes.map((node) => ({
      id: node.id,
      type: "workflowNode",
      position: node.position,
      data: {
        label: node.label,
        kind: node.kind,
        agent: node.agent,
        status: (node.status as WorkflowNodeData["status"]) ?? "idle",
      },
    })),
    edges: validated.graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: false,
    })),
  };
}

export function specToYaml(spec: WorkflowSpecDocument): string {
  return YAML.stringify(spec);
}

export function yamlToSpec(yaml: string, ruleset?: WorkflowChainRuleset): WorkflowSpecDocument {
  const parsed = YAML.parse(yaml) as WorkflowSpecDocument;

  if (!parsed?.graph?.nodes || !parsed?.graph?.edges || !parsed?.name) {
    throw new Error("Invalid workflow yaml. Expected fields: name, graph.nodes, graph.edges");
  }

  return validateWorkflowSpec(parsed, ruleset);
}

