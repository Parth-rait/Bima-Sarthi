// `npm run contrast` prints the WCAG AA table for every colour pair in tokens.css and exits 1 on any failure.
import { computeTable, toMarkdown } from "./contrast-lib.mjs";

const rows = computeTable();
console.log(toMarkdown(rows));
const failed = rows.filter((r) => !r.pass);
if (failed.length) {
  console.error(`\n${failed.length} pair(s) below their minimum.`);
  process.exit(1);
}
console.log(`\nAll ${rows.length} pairs pass.`);
