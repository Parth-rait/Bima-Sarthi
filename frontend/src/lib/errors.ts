import type { ApiError } from "../api";
import type { Key } from "../i18n";

export interface ViewError {
  message: string;
  items: string[];
  fieldErrors: Record<string, string>;
  /** fact keys the server says still need confirming */
  flagged: string[];
  productMissing: boolean;
  canEnterManually: boolean;
  expired: boolean;
}

/** Turn an ApiError into what a screen shows. `label` maps a fact key to its plain-language name. */
export function describeError(e: ApiError, t: (k: Key) => string, label: (k: string) => string): ViewError {
  const base: ViewError = {
    message: e.message,
    items: [],
    fieldErrors: {},
    flagged: [],
    productMissing: false,
    canEnterManually: e.canEnterManually,
    expired: false,
  };
  switch (e.kind) {
    case "expired":
      return { ...base, message: t("expired"), expired: true };
    case "validation":
      return {
        ...base,
        message: t("fixing"),
        fieldErrors: e.fieldErrors,
        items: Object.entries(e.fieldErrors).map(([k, v]) => `${label(k)}: ${v}`),
      };
    case "needs_product_line":
      return { ...base, productMissing: true, flagged: e.needsConfirmation, items: e.needsConfirmation.map(label) };
    case "needs_confirmation":
      return { ...base, flagged: e.needsConfirmation, items: e.needsConfirmation.map(label) };
    default:
      return base;
  }
}
