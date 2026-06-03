import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";
import RouteErrorBoundary from "./RouteErrorBoundary";
import { reportClientError } from "../../lib/error-reporting";

vi.mock("../../lib/error-reporting", () => ({
  reportClientError: vi.fn().mockResolvedValue(undefined),
}));

function CrashRoute() {
  throw new Error("Route exploded");
  return null;
}

describe("RouteErrorBoundary", () => {
  it("renders route failures and reports them", async () => {
    const router = createMemoryRouter(
      [
        {
          path: "/",
          Component: CrashRoute,
          errorElement: <RouteErrorBoundary />,
        },
      ],
      {
        initialEntries: ["/"],
      },
    );

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("Route crashed")).toBeInTheDocument();
    expect(screen.getByText("Route exploded")).toBeInTheDocument();

    await waitFor(() => {
      expect(reportClientError).toHaveBeenCalled();
    });
  });
});
