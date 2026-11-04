/** An ISO date (YYYY-MM-DD) in the product's Indian format, DD/MM/YYYY. Anything else is returned unchanged. */
export const isoToDisplay = (iso: string | null | undefined): string =>
  typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso.split("-").reverse().join("/") : (iso ?? "");
