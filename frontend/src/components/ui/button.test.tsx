import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/button";

afterEach(cleanup);

describe("Button", () => {
  it("renders and handles a click", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Start analysis</Button>);

    const button = screen.getByRole("button", { name: "Start analysis" });
    fireEvent.click(button);

    expect(button).not.toBeNull();
    expect(onClick).toHaveBeenCalledOnce();
  });
});
