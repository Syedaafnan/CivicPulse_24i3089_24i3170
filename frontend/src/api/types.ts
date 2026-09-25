/** Friendly aliases over the types generated from the backend's OpenAPI schema (schema.d.ts). */
import type { components, paths } from "./schema";

type S = components["schemas"];

export type Complaint = S["ComplaintOut"];
export type ComplaintCreate = S["ComplaintCreate"];
export type ComplaintPage = S["ComplaintPage"];
export type Stats = S["StatsOut"];
export type Providers = S["ProvidersOut"];
export type Enums = S["EnumsOut"];
export type Category = S["Category"];
export type Priority = S["Priority"];
export type Status = S["Status"];
export type FieldError = S["FieldError"];

export type ListQuery = NonNullable<paths["/api/complaints"]["get"]["parameters"]["query"]>;
