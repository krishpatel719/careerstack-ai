import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AUTH_EXPIRED_EVENT,
  api,
  getJobMap,
  setToken,
} from "@/lib/api";

function jsonResponse(body: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("api error formatting", () => {
  it.each([
    {
      name: "plain text details",
      detail: "  The analysis could not be completed.  ",
      expected: "The analysis could not be completed.",
    },
    {
      name: "field validation details",
      detail: [
        { loc: ["body", "target_role"], msg: "Field required" },
        { loc: ["body", "location"], message: "Must not be blank" },
      ],
      expected: "Target role: Field required Location: Must not be blank",
    },
    {
      name: "nested service details",
      detail: { message: "Resume parsing is temporarily unavailable." },
      expected: "Resume parsing is temporarily unavailable.",
    },
  ])("formats $name", async ({ detail, expected }) => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ detail }, 422),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api("/api/test-error")).rejects.toMatchObject({
      message: expected,
      status: 422,
    });
  });

  it("uses a stable fallback when no usable detail is supplied", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({}, 500)),
    );

    await expect(api("/api/test-error")).rejects.toMatchObject({
      message: "Something went wrong. Please try again.",
      status: 500,
    });
  });
});

describe("job map API", () => {
  it("encodes only supplied map filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ jobs: [], meta: { count: 0 }, notice: "Approved sources" }, 200),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getJobMap({ role: "frontend developer", location: "Ahmedabad", remote: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/job-map?role=frontend+developer&location=Ahmedabad&remote=true",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
  });
});

describe("session expiration cleanup", () => {
  it("clears CareerStack session data and announces an authenticated 401", async () => {
    setToken("expired-token");
    sessionStorage.setItem("careerstack_analysis", '{"score":81}');
    sessionStorage.setItem("careerstack_preferences", '{"theme":"dark"}');
    sessionStorage.setItem("unrelated", "keep-me");

    const expiredListener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, expiredListener);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "Session expired" }, 401),
      ),
    );

    await expect(api("/api/protected")).rejects.toMatchObject({
      message: "Session expired",
      status: 401,
    });

    expect(localStorage.getItem("careerstack_token")).toBeNull();
    expect(sessionStorage.getItem("careerstack_analysis")).toBeNull();
    expect(sessionStorage.getItem("careerstack_preferences")).toBeNull();
    expect(sessionStorage.getItem("unrelated")).toBe("keep-me");
    expect(expiredListener).toHaveBeenCalledOnce();
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "/api/protected",
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );
  });
});
