/**
 * Shapes of the public call-sheet API (backend/app/schemas/call_sheet.py).
 * Kept by hand until the backend publishes an OpenAPI-generated client;
 * only the fields the viewer reads are typed.
 */

export type IntExt = "INT" | "EXT" | "INT/EXT";
export type DayNight = "DAY" | "NIGHT" | "DAWN" | "DUSK";

export interface ScheduleItem {
  id?: string;
  order_index: number;
  scene_number: string;
  int_ext: IntExt | string;
  day_night: DayNight | string;
  set_description: string;
  location_id?: string | null;
  page_count_eighths: number;
}

export interface CallSheetRevision {
  id?: string;
  revision_letter: string;
  is_current?: boolean;
  general_crew_call: string | null;
  shooting_call: string | null;
  sunrise: string | null;
  sunset: string | null;
  weather_forecast: string | null;
  safety_notes: string | null;
  created_at?: string;
  head_of_day_crew_member_id?: string | null;
  schedule_items: ScheduleItem[];
  crew_calls?: CrewCallEntry[];
  cast_calls?: CastCallEntry[];
}

/** How many subscribed phones a notification attempt reached (FR-16). Since
 * FR-78, delivery runs in a background task after publish/cancel responds,
 * so this no longer rides that response — it shows up on a HistoryEntry once
 * the background task commits. */
export interface NotificationSummary {
  attempted: number;
  delivered: number;
  failed: { crew_member_name: string; reason: string }[];
}

export interface ContactCard {
  name: string;
  department: string;
  position: string;
  phone: string | null;
  email: string | null;
  photo_url: string | null;
}

export interface CallSheetContacts {
  head_of_day: ContactCard | null;
  department_heads: ContactCard[];
  nearest_hospital: string | null;
}

export interface PersonalSheet {
  name: string;
  department: string;
  position: string;
  personal_call: string | null;
  pickup_time?: string | null;
  note?: string | null;
  call_before?: string | null;
  pickup_before?: string | null;
  note_changed?: boolean;
  revision_letter?: string | null;
  confirmed_at?: string | null;
  is_cast?: boolean;
  works_today?: boolean;
  makeup_hair_time?: string | null;
  on_set_time?: string | null;
  since_letter?: string | null;
  changes_since?: RevisionChange[] | null;
  department_head: ContactCard | null;
}

export interface CallSheet {
  id?: string;
  production_title?: string;
  /** "published" normally; "cancelled" when the day is off (FR-34). */
  status?: "draft" | "published" | "superseded" | "cancelled" | string;
  shoot_date: string;
  day_number: number;
  day_count: number;
  unit_name: string;
  current_revision: CallSheetRevision | null;
  contacts?: CallSheetContacts | null;
  personal_calls?: PersonalCallRow[];
  cast_calls?: CastCallRow[];
  /** FR-35: where the day happens, in schedule order. */
  locations?: SheetLocation[];
  /** FR-43: on the AD's days list only. */
  opened?: { seen: number; confirmed?: number; total: number; first_location_name: string | null } | null;
  /** FR-65: what actually happened; authenticated reads only, never on the crew's sheet. */
  actuals?: Actuals | null;
  /** FR-23: what the current revision replaced and what changed; absent on a sheet with only REV A. */
  previous_revision?: RevisionSummary | null;
  changes?: RevisionChange[];
}

export interface RevisionSummary {
  revision_letter: string;
  created_at: string;
}

export interface RevisionChange {
  /** Open-ended on purpose: a sheet rendered by an older bundle falls back to `label` for a field it does not know. */
  field: string;
  label: string;
  before: string | null;
  after: string | null;
  scenes?: string[];
  other_call_sheet_id?: string | null;
  other_day_number?: number | null;
  other_date?: string | null;
}

/* Create payloads (backend/app/schemas). */

export interface ScheduleItemCreate {
  order_index: number;
  scene_number: string;
  int_ext: "INT" | "EXT";
  day_night: "DAY" | "NIGHT";
  set_description: string;
  location_id?: string | null;
  page_count_eighths: number;
}

export interface CrewCallEntry {
  id?: string;
  crew_member_id: string;
  call_time: string | null;
  pickup_time: string | null;
  note: string | null;
}

export interface PersonalCallRow {
  crew_member_id: string;
  name: string;
  department: string;
  position: string;
  call_time: string | null;
  pickup_time: string | null;
  note: string | null;
}

export interface RevisionCreate {
  expected_revision_id?: string | null;
  crew_calls?: CrewCallEntry[];
  /** FR-33: omitted = copy the previous revision's cast calls forward; [] = clear. */
  cast_calls?: CastCallEntry[];
  head_of_day_crew_member_id?: string | null;
  general_crew_call: string | null;
  shooting_call: string | null;
  sunrise: string | null;
  sunset: string | null;
  weather_forecast: string | null;
  safety_notes: string | null;
  created_by: string | null;
  schedule_items: ScheduleItemCreate[];
}

export interface CallSheetCreate {
  shoot_date: string;
  day_number: number;
  day_count: number;
  unit_name: string;
  initial_revision: RevisionCreate;
  /** FR-56: a planned day — kept as status "draft" on the server, invisible to the crew until published. */
  draft?: boolean;
}

export type Permission = "production:read" | "production:manage_members" | "production:edit" | "day:publish" | "crew:edit";
export type ProductionRole = "owner" | "editor" | "viewer";

export interface DashboardItem {
  kind: "unconfirmed" | "unpublished";
  production_id: string;
  production_name: string;
  call_sheet_id: string;
  shoot_date: string;
  day_number: number;
  revision_letter: string | null;
  crew_call: string | null;
  total: number;
  confirmed: number;
  not_opened: number;
}

export interface OnTrackProduction {
  production_id: string;
  production_name: string;
  next_call_sheet_id: string | null;
  next_shoot_date: string | null;
  crew_call: string | null;
}

export interface Dashboard {
  items: DashboardItem[];
  on_track: OnTrackProduction[];
}

export interface Production {
  id: string;
  name: string;
  working_title: string | null;
  production_company: string | null;
  status: "prep" | "shooting" | "wrapped" | string;
  my_role?: ProductionRole | null;
  permissions?: Permission[];
}

export interface Member {
  id: string;
  production_id: string;
  email: string;
  user_id: string | null;
  role: ProductionRole;
  invited_by: string | null;
}

export interface CallSheetCreated extends CallSheet {
  id: string;
  production_id: string;
}

export interface ContactCreate {
  name: string;
  phone: string | null;
  email: string | null;
}

export interface Contact extends ContactCreate {
  id: string;
  photo_url: string | null;
}

/** FR-45: a contact the caller may reuse, with where they last worked so two same names are told apart. */
export interface ContactMatch extends Contact {
  last_production_name: string | null;
  last_position: string | null;
}

export interface CrewMemberCreate {
  contact_id: string;
  department: string;
  position: string;
  standard_call_time: string | null;
  is_head_of_department: boolean;
}

export interface CrewMember extends CrewMemberCreate {
  id: string;
  production_id: string;
  contact: Contact;
  /** FR-206: null for a read-only member; a personal link can confirm on its owner's behalf. */
  personal_token: string | null;
}

export interface LocationCreate {
  name: string;
  address: string | null;
  parking_notes: string | null;
  nearest_hospital: string | null;
}

export interface LocationUpdate {
  name?: string;
  address?: string | null;
  parking_notes?: string | null;
  nearest_hospital?: string | null;
}

export interface Location extends LocationCreate {
  id: string;
  production_id: string;
  geo_lat: number | null;
  geo_lng: number | null;
  geocoded_display_name: string | null;
}

export interface SunTimes {
  sunrise: string | null;
  sunset: string | null;
}

export interface LocationSuggestion {
  suggestion: string | null;
}

/** FR-32: one link per person for the whole shoot — where it opens and the other days. */
export interface CrewDayRef {
  call_sheet_id: string;
  shoot_date: string;
  day_number: number;
  day_count: number;
  unit_name: string;
  revision_letter: string | null;
  status?: string;
  general_crew_call?: string | null;
  first_location_name?: string | null;
}

export interface CrewNextDay {
  production_name: string;
  crew_member_name: string;
  call_sheet_id: string | null;
  days: CrewDayRef[];
}

/* FR-33: cast. */
export type CastStatus = "W" | "SW" | "WF" | "SWF" | "H" | "R";

export interface CastMemberCreate {
  contact_id: string;
  character_name: string;
  standard_pickup_time: string | null;
}

export interface CastMember extends CastMemberCreate {
  id: string;
  production_id: string;
  contact: Contact;
  /** FR-206: null for a read-only member; a personal link can confirm on its owner's behalf. */
  personal_token: string | null;
}

export interface CastCallEntry {
  cast_member_id: string;
  status_code: CastStatus;
  pickup_time: string | null;
  call_time: string | null;
  makeup_hair_time: string | null;
  on_set_time: string | null;
}

export interface CastCallRow extends CastCallEntry {
  name: string;
  character_name: string;
}

export interface SheetLocation {
  id: string;
  name: string;
  address: string | null;
  parking_notes: string | null;
  nearest_hospital: string | null;
  geo_lat: number | null;
  geo_lng: number | null;
  scene_numbers: string[];
}

/* FR-36: who has seen the current revision. */
export interface SeenEntry {
  crew_member_id: string;
  name: string;
  department: string;
  position: string;
  phone: string | null;
  /** FR-206: null for a read-only member; a personal link can confirm on its owner's behalf. */
  personal_token: string | null;
  seen_at: string | null;
  confirmed_at?: string | null;
  is_cast?: boolean;
  subscribed: boolean;
}

export interface SeenReport {
  revision_letter: string;
  seen: SeenEntry[];
  not_seen: SeenEntry[];
}

/** FR-50: one line of the day's publish history. */
export interface HistoryEntry {
  revision_letter: string;
  created_at: string;
  created_by: string;
  changes: RevisionChange[];
  opened: number;
  /** null: no delivery attempt on record yet for this revision (FR-78). */
  notifications?: NotificationSummary | null;
}

/** FR-57: candidates out of an old call sheet PDF; the AD confirms in the crew preview. */
export interface ExtractedContact {
  name: string;
  department: string | null;
  position: string | null;
  phone: string | null;
  email: string | null;
  warnings: string[];
}

export interface CallSheetPdfExtraction {
  contacts: ExtractedContact[];
  method: "claude" | "heuristics" | string;
  pages: number;
  warnings: string[];
}

export interface Actuals {
  first_shot: string | null;
  lunch_out: string | null;
  lunch_in: string | null;
  wrap: string | null;
  note: string | null;
}
