/** The same rule as the server's ClockTime (backend/app/schemas/fields.py), checked first so the AD is told which field and why. */
const CLOCK = /^([0-9]{1,2})[:.,]([0-9]{2})$/;

export function isClockTime(value: string): boolean {
  const typed = value.trim();
  if (typed === "") return true;
  const match = CLOCK.exec(typed);
  return match !== null && Number(match[1]) <= 23 && Number(match[2]) <= 59;
}

export function firstBadTime(fields: [field: string, value: string][]): { field: string; value: string } | null {
  const bad = fields.find(([, value]) => !isClockTime(value));
  return bad ? { field: bad[0], value: bad[1] } : null;
}
