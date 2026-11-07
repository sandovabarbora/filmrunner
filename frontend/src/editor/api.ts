/**
 * Thin client for the FilmRunner API used by the editor. Every call needs
 * the bearer token from the Connect screen (temporary until FR-12).
 */

import type { Dashboard, CallSheetCreate, CallSheetCreated, CallSheetRevision, CastMember, CastMemberCreate, ContactCreate, Contact, ContactMatch, CrewMember, CrewMemberCreate, HistoryEntry, Location, LocationCreate, LocationSuggestion, LocationUpdate, Member, Production, ProductionRole, RevisionCreate, SeenReport, SunTimes, CallSheetPdfExtraction, Actuals } from "../types";

import { currentLang, translate } from "./lang";

export interface Connection {
  apiBase: string;
  token: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** The words the editor uses for a field, so a 422 names what the AD sees rather than the API's name for it. */
const FIELD_LABELS: Record<string, string> = {
  general_crew_call: "Crew call", shooting_call: "Shooting call", sunrise: "Sunrise", sunset: "Sunset", weather_forecast: "Weather",
  safety_notes: "Safety notes", unit_name: "Unit", scene_number: "Scene", set_description: "Set", note: "Note",
  call_time: "Call time", pickup_time: "Pickup time", makeup_hair_time: "Make-up time", on_set_time: "On set time",
  first_shot: "First shot", lunch_out: "Lunch out", lunch_in: "Lunch in", wrap: "Wrap",
  standard_call_time: "Usual call", standard_pickup_time: "Usual pickup", name: "Name", phone: "Phone", email: "Email",
  address: "Address", parking_notes: "Parking notes", nearest_hospital: "Nearest hospital", department: "Department",
  position: "Position", character_name: "Character",
};

type Problem = { loc?: unknown[]; msg?: string; type?: string; ctx?: { max_length?: number } };

function problemText(problem: Problem): string {
  const T = (text: string, vars?: Record<string, string | number>) => translate(currentLang(), text, vars);
  const key = String(problem.loc?.[problem.loc.length - 1] ?? "");
  const field = FIELD_LABELS[key] ? T(FIELD_LABELS[key]) : key;
  const msg = problem.msg ?? "";
  if (msg.includes("must be a time")) return T("{field}: write a time from 00:00 to 23:59, like 06:30.", { field });
  if (problem.type === "string_too_long") return T("{field}: too long, at most {max} characters.", { field, max: problem.ctx?.max_length ?? "?" });
  if (msg.includes("NUL byte")) return T("{field}: contains a character that cannot be saved.", { field });
  return `${field}: ${msg.replace(/^Value error, /, "")}`;
}

/** FastAPI's 422 detail is a list of { loc, msg }; shown raw it would read "HTTP 422". */
function readableDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail) || detail.length === 0) return fallback;
  return (detail as Problem[]).map(problemText).join("; ");
}

async function detailFromResponse(resp: Response, fallback: string): Promise<string> {
  try {
    const data = (await resp.json()) as { detail?: unknown };
    return readableDetail(data.detail, fallback);
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
  if (!resp.ok) throw new ApiError(resp.status, await detailFromResponse(resp, `HTTP ${resp.status}`));
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
  updateProduction: (c: Connection, productionId: string, patch: { name?: string; status?: string }) =>
    request<Production>(c, "PATCH", `/api/v1/productions/${productionId}`, patch),
  moveScene: (c: Connection, callSheetId: string, body: { scene_number: string; occurrence: number; target_call_sheet_id: string; expected_revision_letter: string; expected_target_revision_letter: string }) =>
    request<CallSheetCreated>(c, "POST", `/api/v1/call-sheets/${callSheetId}/move-scene`, body),
  rescheduleDay: (c: Connection, callSheetId: string, body: { shoot_date: string; expected_revision_letter: string }) =>
    request<CallSheetCreated>(c, "POST", `/api/v1/call-sheets/${callSheetId}/reschedule`, body),
  swapDays: (c: Connection, callSheetId: string, body: { other_call_sheet_id: string; expected_revision_letter: string; expected_other_revision_letter: string }) =>
    request<CallSheetCreated>(c, "POST", `/api/v1/call-sheets/${callSheetId}/swap-with`, body),
  seenReport: (c: Connection, callSheetId: string) =>
    request<SeenReport>(c, "GET", `/api/v1/call-sheets/${callSheetId}/seen`),
  setActuals: (c: Connection, callSheetId: string, actuals: Actuals) =>
    request<CallSheetCreated>(c, "PUT", `/api/v1/call-sheets/${callSheetId}/actuals`, actuals),
  history: (c: Connection, callSheetId: string) =>
    request<HistoryEntry[]>(c, "GET", `/api/v1/call-sheets/${callSheetId}/history`),
  deleteDraftCallSheet: (c: Connection, callSheetId: string) =>
    request<void>(c, "DELETE", `/api/v1/call-sheets/${callSheetId}`),
  cancelCallSheet: (c: Connection, callSheetId: string) =>
    request<CallSheetCreated>(c, "POST", `/api/v1/call-sheets/${callSheetId}/cancel`),
  restoreCallSheet: (c: Connection, callSheetId: string) =>
    request<CallSheetCreated>(c, "POST", `/api/v1/call-sheets/${callSheetId}/restore`),
  dashboard: (c: Connection) => request<Dashboard>(c, "GET", "/api/v1/me/dashboard"),
  listCallSheets: (c: Connection, productionId: string) =>
    request<CallSheetCreated[]>(c, "GET", `/api/v1/productions/${productionId}/call-sheets`),
  getCallSheet: (c: Connection, callSheetId: string) =>
    request<CallSheetCreated>(c, "GET", `/api/v1/call-sheets/${callSheetId}`),
  listCrew: (c: Connection, productionId: string) =>
    request<CrewMember[]>(c, "GET", `/api/v1/productions/${productionId}/crew-members`),
  searchContacts: (c: Connection, q: string) => request<ContactMatch[]>(c, "GET", `/api/v1/contacts?q=${encodeURIComponent(q)}`),
  createContact: (c: Connection, payload: ContactCreate) => request<Contact>(c, "POST", "/api/v1/contacts", payload),
  createCrewMember: (c: Connection, productionId: string, payload: CrewMemberCreate) =>
    request<CrewMember>(c, "POST", `/api/v1/productions/${productionId}/crew-members`, payload),
  updateCrewMember: (c: Connection, productionId: string, memberId: string, patch: Partial<CrewMemberCreate>) =>
    request<CrewMember>(c, "PATCH", `/api/v1/productions/${productionId}/crew-members/${memberId}`, patch),
  removeCrewMember: (c: Connection, productionId: string, memberId: string) =>
    request<void>(c, "DELETE", `/api/v1/productions/${productionId}/crew-members/${memberId}`),
  updateContact: (c: Connection, contactId: string, patch: Partial<ContactCreate>) =>
    request<Contact>(c, "PATCH", `/api/v1/contacts/${contactId}`, patch),
  importCallSheetPdf: async (c: Connection, productionId: string, file: File): Promise<CallSheetPdfExtraction> => {
    const form = new FormData();
    form.append("file", file, file.name);
    let resp: Response;
    try {
      resp = await fetch(`${c.apiBase.replace(/\/$/, "")}/api/v1/productions/${productionId}/import/call-sheet-pdf`, {
        method: "POST", headers: { authorization: `Bearer ${c.token}` }, body: form, signal: AbortSignal.timeout(90_000),
      });
    } catch (err) {
      throw new ApiError(0, err instanceof Error ? err.message : "network error");
    }
    if (!resp.ok) throw new ApiError(resp.status, await detailFromResponse(resp, `HTTP ${resp.status}`));
    return (await resp.json()) as CallSheetPdfExtraction;
  },
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
  deleteLocation: (c: Connection, productionId: string, locationId: string) =>
    request<void>(c, "DELETE", `/api/v1/productions/${productionId}/locations/${locationId}`),
  weatherSuggestion: (c: Connection, productionId: string, locationId: string, shootDate: string) =>
    request<LocationSuggestion>(c, "GET", `/api/v1/productions/${productionId}/locations/${locationId}/weather-suggestion?shoot_date=${encodeURIComponent(shootDate)}`),
  listCast: (c: Connection, productionId: string) =>
    request<CastMember[]>(c, "GET", `/api/v1/productions/${productionId}/cast-members`),
  createCastMember: (c: Connection, productionId: string, payload: CastMemberCreate) =>
    request<CastMember>(c, "POST", `/api/v1/productions/${productionId}/cast-members`, payload),
  updateCastMember: (c: Connection, productionId: string, castMemberId: string, patch: Partial<Pick<CastMemberCreate, "character_name" | "standard_pickup_time">>) =>
    request<CastMember>(c, "PATCH", `/api/v1/productions/${productionId}/cast-members/${castMemberId}`, patch),
  deleteCastMember: (c: Connection, productionId: string, castMemberId: string) =>
    request<void>(c, "DELETE", `/api/v1/productions/${productionId}/cast-members/${castMemberId}`),
  sunTimes: (c: Connection, productionId: string, locationId: string, shootDate: string) =>
    request<SunTimes>(c, "GET", `/api/v1/productions/${productionId}/locations/${locationId}/sun?shoot_date=${encodeURIComponent(shootDate)}`),
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
