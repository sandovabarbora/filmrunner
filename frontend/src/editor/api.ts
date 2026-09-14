/**
 * Thin client for the FilmRunner API used by the editor. Every call needs
 * the bearer token from the Connect screen (temporary until FR-12).
 */

import type { CallSheetCreate, CallSheetCreated, CallSheetRevision, ContactCreate, Contact, CrewMember, CrewMemberCreate, Member, Production, ProductionRole, RevisionCreate } from "../types";

export interface Connection {
  apiBase: string;
  token: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(conn: Connection, method: string, path: string, body?: unknown): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${conn.apiBase.replace(/\/$/, "")}${path}`, {
      method,
      headers: { authorization: `Bearer ${conn.token}`, "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(10_000),
    });
  } catch (err) {
    throw new ApiError(0, err instanceof Error ? err.message : "network error");
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const data = (await resp.json()) as { detail?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* body was not JSON; keep the status text */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  listProductions: (c: Connection) => request<Production[]>(c, "GET", "/api/v1/productions"),
  createProduction: (c: Connection, name: string) =>
    request<Production>(c, "POST", "/api/v1/productions", { name, status: "prep" }),
  createCallSheet: (c: Connection, productionId: string, payload: CallSheetCreate) =>
    request<CallSheetCreated>(c, "POST", `/api/v1/productions/${productionId}/call-sheets`, payload),
  publishRevision: (c: Connection, callSheetId: string, payload: RevisionCreate) =>
    request<CallSheetRevision>(c, "POST", `/api/v1/call-sheets/${callSheetId}/revisions`, payload),
  listCallSheets: (c: Connection, productionId: string) =>
    request<CallSheetCreated[]>(c, "GET", `/api/v1/productions/${productionId}/call-sheets`),
  getCallSheet: (c: Connection, callSheetId: string) =>
    request<CallSheetCreated>(c, "GET", `/api/v1/call-sheets/${callSheetId}`),
  listCrew: (c: Connection, productionId: string) =>
    request<CrewMember[]>(c, "GET", `/api/v1/productions/${productionId}/crew-members`),
  createContact: (c: Connection, payload: ContactCreate) => request<Contact>(c, "POST", "/api/v1/contacts", payload),
  createCrewMember: (c: Connection, productionId: string, payload: CrewMemberCreate) =>
    request<CrewMember>(c, "POST", `/api/v1/productions/${productionId}/crew-members`, payload),
  updateCrewMember: (c: Connection, productionId: string, memberId: string, patch: Partial<CrewMemberCreate>) =>
    request<CrewMember>(c, "PATCH", `/api/v1/productions/${productionId}/crew-members/${memberId}`, patch),
  removeCrewMember: (c: Connection, productionId: string, memberId: string) =>
    request<void>(c, "DELETE", `/api/v1/productions/${productionId}/crew-members/${memberId}`),
  updateContact: (c: Connection, contactId: string, patch: Partial<ContactCreate>) =>
    request<Contact>(c, "PATCH", `/api/v1/contacts/${contactId}`, patch),
  listMembers: (c: Connection, productionId: string) => request<Member[]>(c, "GET", `/api/v1/productions/${productionId}/members`),
  addMember: (c: Connection, productionId: string, email: string, role: ProductionRole) =>
    request<Member>(c, "POST", `/api/v1/productions/${productionId}/members`, { email, role }),
  removeMember: (c: Connection, productionId: string, memberId: string) =>
    request<void>(c, "DELETE", `/api/v1/productions/${productionId}/members/${memberId}`),
};

const CONNECTION_KEY = "filmrunner.editor.connection";

export function loadConnection(): Connection | null {
  try {
    const raw = localStorage.getItem(CONNECTION_KEY);
    return raw ? (JSON.parse(raw) as Connection) : null;
  } catch {
    return null;
  }
}

export function saveConnection(conn: Connection | null): void {
  try {
    if (conn) localStorage.setItem(CONNECTION_KEY, JSON.stringify(conn));
    else localStorage.removeItem(CONNECTION_KEY);
  } catch {
    /* private mode: the AD reconnects next time, nothing else breaks */
  }
}
