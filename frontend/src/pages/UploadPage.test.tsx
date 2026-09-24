import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { UploadPage } from "@/pages/UploadPage";

const user = {
  user_id: "user-1",
  email: "candidate@example.com",
  name: "Jordan Candidate",
  created_at: "2026-01-01T00:00:00Z",
};

function renderUploadPage() {
  return render(
    <MemoryRouter>
      <UploadPage user={user} onSignOut={() => {}} />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("UploadPage file validation", () => {
  it("rejects unsupported file types before creating a preview", () => {
    const { container } = renderUploadPage();
    const input = container.querySelector<HTMLInputElement>("#resume-file");

    expect(input).not.toBeNull();
    expect(input?.accept).toContain(".pdf,.docx");

    fireEvent.change(input!, {
      target: {
        files: [new File(["not a resume"], "resume.txt", { type: "text/plain" })],
      },
    });

    expect(screen.getByRole("alert").textContent).toBe(
      "Choose a PDF or DOCX file.",
    );
    expect(screen.queryByText("not a resume")).toBeNull();
  });

  it("rejects files larger than 5 MB", () => {
    const { container } = renderUploadPage();
    const input = container.querySelector<HTMLInputElement>("#resume-file");
    const oversizedPdf = new File(
      [new Uint8Array(5 * 1024 * 1024 + 1)],
      "resume.pdf",
      { type: "application/pdf" },
    );

    fireEvent.change(input!, { target: { files: [oversizedPdf] } });

    expect(screen.getByRole("alert").textContent).toBe(
      "That file is over 5 MB. Please upload a smaller file.",
    );
    expect(screen.queryByText("resume.pdf")).toBeNull();
  });
});
