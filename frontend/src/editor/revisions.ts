/** Revisions run A to Z; the server refuses a 27th (services/call_sheets.py), so there is no next letter after Z. */
export function nextRevisionLetter(letter: string): string | null {
  return letter >= "A" && letter < "Z" ? String.fromCharCode(letter.charCodeAt(0) + 1) : null;
}
