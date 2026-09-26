/**
 * Client-side validation that MIRRORS the server's rules (backend/app/domain.py)
 * for fast feedback. It never replaces them: the server re-validates and its
 * field-level 400 errors are shown the same way. tests/validation.test.ts checks
 * these numbers against the OpenAPI schema so the mirror cannot silently rot.
 */
import type { ComplaintCreate } from "./api/types";

export const LIMITS = {
  text: { min: 10, max: 2000 },
  location: { min: 3, max: 200 },
  reporter_contact: { max: 200 },
} as const;

export type FormErrors = Partial<Record<keyof ComplaintCreate, string>>;

export function validateComplaint(v: { text: string; location: string; reporter_contact: string }): FormErrors {
  const e: FormErrors = {};
  const text = v.text.trim();
  const location = v.location.trim();
  if (text.length < LIMITS.text.min) e.text = `Please describe the problem in at least ${LIMITS.text.min} characters.`;
  else if (text.length > LIMITS.text.max) e.text = `Please keep it under ${LIMITS.text.max} characters.`;
  if (location.length < LIMITS.location.min) e.location = `Location needs at least ${LIMITS.location.min} characters.`;
  else if (location.length > LIMITS.location.max) e.location = `Location must be under ${LIMITS.location.max} characters.`;
  if (v.reporter_contact.trim().length > LIMITS.reporter_contact.max)
    e.reporter_contact = `Contact must be under ${LIMITS.reporter_contact.max} characters.`;
  return e;
}
