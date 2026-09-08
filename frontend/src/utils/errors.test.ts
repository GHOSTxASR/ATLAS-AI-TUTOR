import { describe, expect, it } from "vitest";

import { getErrorCode, getErrorMessage, getErrorStatus } from "./errors";

/** An axios-shaped rejection carrying Atlas's error envelope. */
const apiError = (message: string, code = "VALIDATION_ERROR", status = 422) => ({
  message: "Request failed with status code " + status,
  response: { status, data: { data: null, error: { code, message }, meta: null } },
});

describe("getErrorMessage", () => {
  it("prefers the API's own explanation over the generic fallback", () => {
    expect(getErrorMessage(apiError("File exceeds the 50MB upload limit."), "Upload failed.")).toBe(
      "File exceeds the 50MB upload limit.",
    );
  });

  it("prefers the API's explanation over the transport's message", () => {
    // The axios message ("Request failed with status code 422") is useless to
    // a reader; the envelope says what actually happened.
    const err = apiError("That file is not a valid ZIP archive.");
    expect(getErrorMessage(err, "Import failed.")).not.toContain("status code");
  });

  it("prefers the caller's fallback over transport boilerplate", () => {
    // Once the server has answered, "Request failed with status code 500" is
    // strictly less informative than the sentence the call site wrote for
    // this specific action.
    const err = {
      message: "Request failed with status code 500",
      response: { status: 500, data: { data: null, error: null, meta: null } },
    };
    expect(getErrorMessage(err, "Failed to create memory.")).toBe("Failed to create memory.");
  });

  it("still surfaces the transport message when the request never landed", () => {
    // No `response` at all -- the server was unreachable, and "Network Error"
    // is the most useful thing anyone can say.
    expect(getErrorMessage({ message: "Network Error" }, "Could not connect.")).toBe(
      "Network Error",
    );
  });

  it("falls back to Error.message when there is no envelope", () => {
    expect(getErrorMessage(new Error("Network Error"), "Could not connect.")).toBe("Network Error");
  });

  it("uses the caller's fallback when the error says nothing useful", () => {
    expect(getErrorMessage({}, "Failed to create node.")).toBe("Failed to create node.");
    expect(getErrorMessage(null, "Failed to create node.")).toBe("Failed to create node.");
    expect(getErrorMessage(undefined, "Failed to create node.")).toBe("Failed to create node.");
    expect(getErrorMessage("a bare string", "Failed to create node.")).toBe("Failed to create node.");
  });

  it("ignores blank messages rather than showing an empty error", () => {
    expect(getErrorMessage(apiError("   "), "Something went wrong.")).toBe("Something went wrong.");
    expect(getErrorMessage(new Error(""), "Something went wrong.")).toBe("Something went wrong.");
    expect(getErrorMessage({ message: "   " }, "Something went wrong.")).toBe(
      "Something went wrong.",
    );
  });

  it("survives a partially-shaped response without throwing", () => {
    expect(getErrorMessage({ response: {} }, "fallback")).toBe("fallback");
    expect(getErrorMessage({ response: { data: {} } }, "fallback")).toBe("fallback");
    expect(getErrorMessage({ response: { data: { error: null } } }, "fallback")).toBe("fallback");
    expect(getErrorMessage({ response: { data: { error: { message: 42 } } } }, "fallback")).toBe(
      "fallback",
    );
  });
});

describe("getErrorStatus", () => {
  it("reads the status so a 404 can be treated as an empty state", () => {
    expect(getErrorStatus(apiError("No active roadmap", "NOT_FOUND", 404))).toBe(404);
  });

  it("is undefined when the failure never reached the server", () => {
    expect(getErrorStatus(new Error("Network Error"))).toBeUndefined();
    expect(getErrorStatus({})).toBeUndefined();
    expect(getErrorStatus(null)).toBeUndefined();
  });
});

describe("getErrorCode", () => {
  it("exposes the machine-readable code", () => {
    expect(getErrorCode(apiError("No key configured", "PROVIDER_NOT_CONFIGURED", 503))).toBe(
      "PROVIDER_NOT_CONFIGURED",
    );
  });

  it("is undefined when there is no envelope", () => {
    expect(getErrorCode(new Error("boom"))).toBeUndefined();
  });
});
