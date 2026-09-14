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
}

export interface ContactCard {
  name: string;
  department: string;
  position: string;
  phone: string | null;
  email: string | null;
}

export interface CallSheetContacts {
  head_of_day: ContactCard | null;
  department_heads: ContactCard[];
  nearest_hospital: string | null;
}

export interface CallSheet {
  id?: string;
  production_title?: string;
  shoot_date: string;
  day_number: number;
  day_count: number;
  unit_name: string;
  current_revision: CallSheetRevision | null;
  contacts?: CallSheetContacts | null;
}

/* Create payloads (backend/app/schemas). */

export interface ScheduleItemCreate {
  order_index: number;
  scene_number: string;
  int_ext: "INT" | "EXT";
  day_night: "DAY" | "NIGHT";
  set_description: string;
  page_count_eighths: number;
}

export interface RevisionCreate {
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
}

export interface Production {
  id: string;
  name: string;
  working_title: string | null;
  production_company: string | null;
  status: "prep" | "shooting" | "wrapped" | string;
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
}
