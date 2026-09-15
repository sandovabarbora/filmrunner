/**
 * Thin client for the FilmRunner API used by the editor. Every call needs
 * the bearer token from the Connect screen (temporary until FR-12).
 */

import type { CallSheetCreate, CallSheetCreated, CallSheetRevision, ContactCreate, Contact, CrewMember, CrewMemberCreate, Location, LocationCreate, LocationSuggestion, LocationUpdate, Member, Production, ProductionRole, RevisionCreate } from "../types";

export interface Connection {
  apiBase: string;
  token: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function detailFromResponse(resp: Response, fallback: string): Promise<string> {
  try {
    const data = (await resp.json()) as { detail?: unknown };
    return typeof data.detail === "string" ? data.detail : fallback;
  } catch {
    return fallback;
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
  uploadContactPhoto: async (c: Connection, contactId: string, photo: Blob): Promise<Contact> => {
    const form = new FormData();
    form.append("file", photo, "avatar.jpg");
    let resp: Response;
    try {
      resp = await fetch(`${c.apiBase.replace(/\/$/, "")}/api/v1/contacts/${contactId}/photo`, {
        method: "POST",
        headers: { authorization: `Bearer ${c.token}` },
        body: form,
        signal: AbortSignal.timeout(20_000),
      });
    } catch (err) {
      throw new ApiError(0, err instanceof Error ? err.message : "network error");
    }
    if (!resp.ok) throw new ApiError(resp.status, await detailFromResponse(resp, `HTTP ${resp.status}`));
    return (await resp.json()) as Contact;
  },
  removeContactPhoto: (c: Connection, contactId: string) => request<Contact>(c, "DELETE", `/api/v1/contacts/${contactId}/photo`),
  listMembers: (c: Connection, productionId: string) => request<Member[]>(c, "GET", `/api/v1/productions/${productionId}/members`),
  addMember: (c: Connection, productionId: string, email: string, role: ProductionRole) =>
    request<Member>(c, "POST", `/api/v1/productions/${productionId}/members`, { email, role }),
  removeMember: (c: Connection, productionId: string, memberId: string) =>
    request<void>(c, "DELETE", `/api/v1/productions/${productionId}/members/${memberId}`),
  listLocations: (c: Connection, productionId: string) => request<Location[]>(c, "GET", `/api/v1/productions/${productionId}/locations`),
  createLocation: (c: Connection, productionId: string, payload: LocationCreate) =>
    request<Location>(c, "POST", `/api/v1/productions/${productionId}/locations`, payload),
  updateLocation: (c: Connection, productionId: string, locationId: string, patch: LocationUpdate) =>
    request<Location>(c, "PATCH", `/api/v1/productions/${productionId}/locations/${locationId}`, patch),
  weatherSuggestion: (c: Connection, productionId: string, locationId: string, shootDate: string) =>
    request<LocationSuggestion>(c, "GET", `/api/v1/productions/${productionId}/locations/${locationId}/weather-suggestion?shoot_date=${encodeURIComponent(shootDate)}`),
  hospitalSuggestion: (c: Connection, productionId: string, locationId: string) =>
    request<LocationSuggestion>(c, "GET", `/api/v1/productions/${productionId}/locations/${locationId}/hospital-suggestion`),
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
