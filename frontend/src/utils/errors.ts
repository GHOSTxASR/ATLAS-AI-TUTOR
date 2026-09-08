/**
 * Reading an error that came back from the API.
 *
 * Twenty-seven call sites used to catch `err: any` and each pick the message
 * apart themselves, in one of two ways. Pages reached for the backend's
 * envelope:
 *
 *     err?.response?.data?.error?.message || "Failed to create node."
 *
 * while the stores only ever looked at `err.message`, so they showed their own
 * generic fallback even when the server had explained exactly what went wrong.
 * Both are the same question asked twice, and `any` meant TypeScript could not
 * tell either of them they were wrong.
 *
 * These narrow from `unknown` once, in one place, and try the backend's
 * message *before* falling back — so the store call sites now surface the real
 * reason rather than swallowing it.
 */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * The message to show a user for a failed request.
 *
 * Prefers the API's own explanation, then any `Error.message`, then the
 * caller's fallback. Deliberately structural rather than `axios.isAxiosError`:
 * it works for anything thrown, and does not care which HTTP client is in use.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (isRecord(err)) {
    const response = err.response;
    const reachedTheServer = isRecord(response);

    if (reachedTheServer && isRecord(response.data)) {
      const envelope = response.data.error;
      if (isRecord(envelope) && typeof envelope.message === "string") {
        const message = envelope.message.trim();
        if (message) return message;
      }
    }

    // `err.message` is only worth showing when the request never got a
    // response -- there it is the real reason ("Network Error"). Once the
    // server has replied, the transport's message is boilerplate ("Request
    // failed with status code 422"), and the caller's fallback, written for
    // this specific action, tells the reader more.
    if (!reachedTheServer && typeof err.message === "string") {
      const message = err.message.trim();
      if (message) return message;
    }
  }
  return fallback;
}

/**
 * The HTTP status of a failed request, if it had one.
 *
 * For the handful of places that treat a specific status as an ordinary
 * outcome rather than a failure — a 404 for "this profile has no roadmap yet"
 * is an empty state, not an error.
 */
export function getErrorStatus(err: unknown): number | undefined {
  if (isRecord(err)) {
    const response = err.response;
    if (isRecord(response) && typeof response.status === "number") {
      return response.status;
    }
  }
  return undefined;
}

/**
 * The API's machine-readable error code, if the response carried one.
 *
 * Codes such as `PROVIDER_NOT_CONFIGURED` let the interface offer the right
 * next step instead of only restating the message.
 */
export function getErrorCode(err: unknown): string | undefined {
  if (isRecord(err)) {
    const response = err.response;
    if (isRecord(response) && isRecord(response.data)) {
      const envelope = response.data.error;
      if (isRecord(envelope) && typeof envelope.code === "string") {
        return envelope.code;
      }
    }
  }
  return undefined;
}
