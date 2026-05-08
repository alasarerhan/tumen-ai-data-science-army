import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { WorkflowDesignMessage } from "./WorkflowDesignMessage";
import { workflowChainRulesFixture } from "../../test/fixtures/workflowChainRules";

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../../hooks/useWorkflowChainRules", () => ({
  useWorkflowChainRules: () => ({
    data: {
      ruleset: workflowChainRulesFixture,
    },
  }),
}));

describe("WorkflowDesignMessage", () => {
  it("disables approval for invalid chains", () => {
    render(
      <WorkflowDesignMessage
        workflowSpec={{
          name: "Invalid Workflow",
          steps: [
            { id: "viz", agent: "Visualization", instruction: "Plot the dataset." },
            { id: "model", agent: "H2O ML", instruction: "Train a model.", depends_on: ["viz"] },
          ],
        }}
        onApprove={vi.fn()}
        onModify={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText(/invalid workflow chain/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve & run/i })).toBeDisabled();
  });

  it("shows advisory warnings and still allows approval", () => {
    const onApprove = vi.fn();

    render(
      <WorkflowDesignMessage
        workflowSpec={{
          name: "Advisory Workflow",
          steps: [
            { id: "eda", agent: "EDA", instruction: "Profile the data." },
            { id: "clean", agent: "Data Cleaning", instruction: "Clean the data.", depends_on: ["eda"] },
          ],
        }}
        onApprove={onApprove}
        onModify={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText(/workflow warnings/i)).toBeInTheDocument();
    const approveButton = screen.getByRole("button", { name: /approve & run/i });
    expect(approveButton).toBeEnabled();

    fireEvent.click(approveButton);
    expect(onApprove).toHaveBeenCalledOnce();
  });
});
