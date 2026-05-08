import type { WorkflowChainRuleset } from "../api/workflowChainRules";

export type ValidationSeverity = "warning" | "error";

export interface WorkflowValidationIssue {
  severity: ValidationSeverity;
  code: string;
  message: string;
  nodeId?: string;
  edgeId?: string;
}

const EMPTY_RULESET: WorkflowChainRuleset = {
  version: "0.0.0",
  agents: [],
  requirements: {},
};

type WorkflowGraphNode = {
  id: string;
  label?: string;
  kind?: string;
  agent?: string;
  position?: { x: number; y: number };
  status?: string;
};

type WorkflowGraphEdge = {
  id: string;
  source: string;
  target: string;
};

type WorkflowStep = {
  id: string;
  tool?: string;
  agent?: string;
  instruction?: string;
  depends_on?: string[];
};

export type SupportedWorkflowSpec = {
  name?: string;
  description?: string;
  target_variable?: string;
  graph?: {
    nodes?: WorkflowGraphNode[];
    edges?: WorkflowGraphEdge[];
  };
  steps?: WorkflowStep[];
};

function normalizeName(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function getEffectiveRuleset(ruleset?: WorkflowChainRuleset): WorkflowChainRuleset {
  return ruleset ?? EMPTY_RULESET;
}

function buildRuleMaps(ruleset?: WorkflowChainRuleset) {
  const effectiveRuleset = getEffectiveRuleset(ruleset);
  const allRules = new Map(effectiveRuleset.agents.map((rule) => [rule.key, rule]));
  const aliasMap = new Map<string, string>();
  for (const rule of effectiveRuleset.agents) {
    aliasMap.set(normalizeName(rule.key), rule.key);
    aliasMap.set(normalizeName(rule.label), rule.key);
    for (const alias of rule.aliases) {
      aliasMap.set(normalizeName(alias), rule.key);
    }
  }

  return { allRules, aliasMap, ruleset: effectiveRuleset };
}

export function getWorkflowAgentCatalog(ruleset?: WorkflowChainRuleset) {
  return getEffectiveRuleset(ruleset).agents.map((rule) => ({
    key: rule.key,
    label: rule.label,
    kind: rule.kind,
    color: rule.color,
  }));
}

export function canonicalizeAgent(candidate: string | undefined | null, ruleset?: WorkflowChainRuleset): string | null {
  if (!candidate) return null;
  return buildRuleMaps(ruleset).aliasMap.get(normalizeName(candidate)) ?? null;
}

function normalizeGraph(spec: SupportedWorkflowSpec): {
  nodes: WorkflowGraphNode[];
  edges: WorkflowGraphEdge[];
  targetVariable?: string;
} {
  if (spec.graph?.nodes && spec.graph?.edges) {
    return {
      nodes: spec.graph.nodes,
      edges: spec.graph.edges,
      targetVariable: spec.target_variable,
    };
  }

  const steps = Array.isArray(spec.steps) ? spec.steps : [];
  const nodes: WorkflowGraphNode[] = steps.map((step) => ({
    id: step.id,
    label: step.agent || step.tool || step.id,
    agent: step.agent || step.tool,
    kind: "derived",
  }));
  const edges: WorkflowGraphEdge[] = [];
  for (const step of steps) {
    for (const dependencyId of step.depends_on ?? []) {
      edges.push({
        id: `edge-${dependencyId}-${step.id}`,
        source: dependencyId,
        target: step.id,
      });
    }
  }
  return {
    nodes,
    edges,
    targetVariable: spec.target_variable,
  };
}

export function inspectWorkflowSpec(
  spec: SupportedWorkflowSpec,
  ruleset?: WorkflowChainRuleset,
): {
  warnings: WorkflowValidationIssue[];
  errors: WorkflowValidationIssue[];
} {
  const warnings: WorkflowValidationIssue[] = [];
  const errors: WorkflowValidationIssue[] = [];
  const { allRules, ruleset: effectiveRuleset } = buildRuleMaps(ruleset);
  const shouldValidateChains = effectiveRuleset.agents.length > 0;

  if (!spec.name || !spec.name.trim()) {
    errors.push({ severity: "error", code: "missing_name", message: "Workflow name is required." });
    return { warnings, errors };
  }

  const { nodes, edges, targetVariable } = normalizeGraph(spec);

  if (!Array.isArray(nodes) || !Array.isArray(edges)) {
    errors.push({
      severity: "error",
      code: "invalid_graph",
      message: "Workflow spec must include graph.nodes and graph.edges, or a valid steps array.",
    });
    return { warnings, errors };
  }

  if (nodes.length === 0) {
    errors.push({ severity: "error", code: "empty_nodes", message: "Workflow must contain at least one node." });
    return { warnings, errors };
  }

  const nodeIds = new Set<string>();
  const canonicalByNodeId = new Map<string, string>();

  for (const node of nodes) {
    if (!node.id) {
      errors.push({ severity: "error", code: "missing_node_id", message: "Each node must include an id." });
      continue;
    }
    if (nodeIds.has(node.id)) {
      errors.push({
        severity: "error",
        code: "duplicate_node_id",
        nodeId: node.id,
        message: `Duplicate node id detected: ${node.id}`,
      });
      continue;
    }
    nodeIds.add(node.id);

    const canonical = canonicalizeAgent(node.agent || node.label, effectiveRuleset);
    if (!canonical) {
      if (!shouldValidateChains) {
        continue;
      }
      errors.push({
        severity: "error",
        code: "unknown_agent",
        nodeId: node.id,
        message: `Node "${node.label || node.id}" does not map to a known agent.`,
      });
      continue;
    }
    canonicalByNodeId.set(node.id, canonical);
  }

  const incomingCounts = new Map<string, number>();

  for (const edge of edges) {
    if (!edge.id || !edge.source || !edge.target) {
      errors.push({
        severity: "error",
        code: "invalid_edge",
        edgeId: edge.id,
        message: "Each edge must include id, source, and target.",
      });
      continue;
    }

    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      errors.push({
        severity: "error",
        code: "dangling_edge",
        edgeId: edge.id,
        message: `Edge ${edge.id} references unknown node.`,
      });
      continue;
    }

    incomingCounts.set(edge.target, (incomingCounts.get(edge.target) ?? 0) + 1);

    const sourceCanonical = canonicalByNodeId.get(edge.source);
    const targetCanonical = canonicalByNodeId.get(edge.target);
    if (!sourceCanonical || !targetCanonical) {
      continue;
    }

    const sourceRule = allRules.get(sourceCanonical);
    if (!sourceRule) {
      continue;
    }

    if (sourceRule.safe_next.includes(targetCanonical)) {
      continue;
    }
    if (sourceRule.conditional_next.includes(targetCanonical)) {
      warnings.push({
        severity: "warning",
        code: "conditional_edge",
        edgeId: edge.id,
        nodeId: edge.target,
        message: `${sourceRule.label} -> ${allRules.get(targetCanonical)?.label ?? targetCanonical} is valid, but it is conditional/advisory rather than a guaranteed typed handoff.`,
      });
      continue;
    }

    errors.push({
      severity: "error",
      code: "blocked_edge",
      edgeId: edge.id,
      nodeId: edge.target,
      message: `${sourceRule.label} cannot chain directly into ${allRules.get(targetCanonical)?.label ?? targetCanonical}.`,
    });
  }

  for (const node of nodes) {
    const canonical = canonicalByNodeId.get(node.id);
    if (!canonical) continue;

    const requirement = effectiveRuleset.requirements[canonical];
    if (!requirement) continue;

    const inbound = incomingCounts.get(node.id) ?? 0;
    if (typeof requirement.min_incoming_edges === "number" && inbound < requirement.min_incoming_edges) {
      warnings.push({
        severity: "warning",
        code: "insufficient_inputs",
        nodeId: node.id,
        message: `${allRules.get(canonical)?.label ?? canonical} usually needs at least ${requirement.min_incoming_edges} inbound edges, but this node currently has ${inbound}.`,
      });
    }

    if (requirement.target_variable && !targetVariable) {
      warnings.push({
        severity: "warning",
        code: "missing_target_variable",
        nodeId: node.id,
        message: `${allRules.get(canonical)?.label ?? canonical} usually requires a target variable, but this workflow spec does not define one.`,
      });
    }
  }

  return { warnings, errors };
}

export function validateWorkflowSpecWithRules<T extends SupportedWorkflowSpec>(
  spec: T,
  ruleset?: WorkflowChainRuleset,
): T {
  const { errors } = inspectWorkflowSpec(spec, ruleset);
  if (errors.length > 0) {
    throw new Error(errors.map((issue) => issue.message).join(" "));
  }
  return spec;
}
