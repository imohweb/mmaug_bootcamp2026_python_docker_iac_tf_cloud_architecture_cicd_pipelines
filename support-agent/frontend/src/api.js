export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const response = await fetch(path, {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new ApiError(response.status, payload.error || `Request failed (HTTP ${response.status})`);
  }
  return payload;
}

export const STATUS_LABELS = {
  awaiting_approval: "With a specialist",
  responded: "Answered",
};

export function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "";
}
