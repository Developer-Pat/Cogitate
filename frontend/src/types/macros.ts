/**
 * Macro system types.
 *
 * SystemMetaTopic / SystemMacroSet were previously exported from a
 * type-only service stub (legacy name). Relocated here during the
 * legacy-name cleanup; the old file was deleted.
 */

export interface SystemMetaTopic {
  id: number;
  name: string;
  slug: string;
  description: string;
  // THE BUILD FIX (2026-08-25, the tsc -b): the runtime rows carry
  // the namespace + the topic_mappings (the JSON column).
  namespace?: string
  topic_mappings?: Array<{ topic: string; slot_start: string }> | string
}

export interface SystemMacroSet {
  id: number;
  mode_slug: string;
  topic: string;
  name: string;
  description: string;
  is_active: boolean;
}
