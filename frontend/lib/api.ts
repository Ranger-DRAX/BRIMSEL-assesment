/**
 * Typed API client for Little English Buddy backend.
 *
 * Implements:
 * - Credentials included for HttpOnly cookie authentication
 * - Unique client request_id generation
 * - Revision tracking and 409 conflict handling
 * - Network error detection and retry support
 * - Strict typing matching OpenAPI schemas
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "";

export interface ActivityChoice {
  id: string;
  text: string;
}

export interface ActivityPayload {
  activity_id: string;
  instance_id: string;
  activity_type: string;
  prompt: string;
  choices: ActivityChoice[] | null;
  skill: string;
  level: string;
}

export interface ChatRequest {
  request_id: string;
  expected_revision: number;
  message?: string | null;
  action?: string | null;
  activity_instance_id?: string | null;
  answer_option_id?: string | null;
}

export interface ChatResponse {
  request_id: string;
  revision: number;
  reply: string;
  mode: "learning" | "conversation" | "engagement" | "support";
  level: "L1" | "L2" | "L3";
  suggested_replies: string[];
  activity: ActivityPayload | null;
  source: "groq" | "mock" | "curriculum" | "fallback";
  fallback_reason: string | null;
}

export interface SessionResponse {
  nickname: string | null;
  level: "L1" | "L2" | "L3";
  mode: string;
  recent_messages: Array<{ role: "user" | "assistant"; content: string }>;
  active_activity: ActivityPayload | null;
  revision: number;
  promotion_available: boolean;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  resyncRequired?: boolean;

  constructor(status: number, detail: string, resyncRequired = false) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.resyncRequired = resyncRequired;
  }
}

/**
 * Generate a cryptographically random UUID v4.
 */
export function generateRequestId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Fetch current session state.
 * Returns null if no active session or 401.
 */
export async function getSession(): Promise<SessionResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/session`, {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });

    if (res.status === 401) {
      return null;
    }

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new ApiError(res.status, errorData.detail || "Failed to load session");
    }

    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, "Network error: Unable to reach server");
  }
}

/**
 * Create a new session and profile with an HttpOnly cookie.
 */
export async function createSession(
  nickname?: string,
  startingLevel: string = "L1"
): Promise<SessionResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/session`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        nickname: nickname?.trim() || null,
        starting_level: startingLevel,
      }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new ApiError(res.status, errorData.detail || "Failed to create session");
    }

    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, "Network error: Unable to connect to server");
  }
}

/**
 * Submit a chat turn to the backend.
 */
export async function sendChatMessage(params: {
  message?: string | null;
  action?: string | null;
  activityInstanceId?: string | null;
  answerOptionId?: string | null;
  expectedRevision: number;
  requestId?: string;
}): Promise<ChatResponse> {
  const requestId = params.requestId || generateRequestId();

  const payload: ChatRequest = {
    request_id: requestId,
    expected_revision: params.expectedRevision,
    message: params.message?.trim() || null,
    action: params.action || null,
    activity_instance_id: params.activityInstanceId || null,
    answer_option_id: params.answerOptionId || null,
  };

  try {
    const res = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(409, err.detail || "State conflict. Please resync.", true);
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(res.status, err.detail || `Server error (${res.status})`);
    }

    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, "Network error: message could not be sent");
  }
}

/**
 * Reset learning progress and chat history.
 */
export async function resetSession(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/session/reset`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.detail || "Failed to reset session");
  }
}

/**
 * Delete session, profile data, and clear authentication cookie.
 */
export async function deleteSession(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/session`, {
    method: "DELETE",
    credentials: "include",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.detail || "Failed to delete session");
  }
}
