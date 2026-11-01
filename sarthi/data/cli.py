"""Data CLI: uv run python -m sarthi.data.cli <subcommand>. Add subcommands via SUBCOMMANDS."""
import argparse
import json
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from sarthi.core.hashing import sha256_file
from sarthi.core.models import PRODUCT_LINES
from sarthi.core.registry import load_registry
from sarthi.core.store import Store
from sarthi.data.parse_docs import parse_source
from sarthi.data import case_facts, case_issues, cases, literature, policy_index, rule_cards, stats
from sarthi.data import fetch
from sarthi.data.fetch import FetchError, fetch_source, raw_dir, record_source

DEFAULT_REGISTRY = Path("sources.yaml")


def data_dir() -> Path:
    return Path(os.environ.get("SARTHI_DATA_DIR", "data"))


_OPENED: list[Store] = []


def open_store() -> Store:
    """Open the store. Stores opened here are closed by main(); DAG tasks use `with open_store()`."""
    s = Store(data_dir() / "bima_sarthi.duckdb")
    s.init()
    _OPENED.append(s)
    return s


def _find(specs, source_id):
    for s in specs:
        if s.id == source_id:
            return s
    ids = ", ".join(s.id for s in specs)
    raise CliError(f"unknown source id '{source_id}'. Known ids: {ids}")


class CliError(Exception):
    pass


MANUAL = "use the manual path in docs/runbooks/03-manual-downloads.md"


def cmd_fetch_discover(args, specs) -> int:
    chosen = [_find(specs, args.id)] if args.id else specs
    store = open_store()
    today = date.today().isoformat()
    rows, failures = [], 0
    for spec in chosen:
        d = fetch.discover_source(spec, store, replace=args.replace,
                                  allow_offsite=args.allow_offsite)
        rows.append(d)
        if d.sha256 is None:
            failures += 1
        if d.sha256 and args.write_urls:
            if not d.official and not args.allow_offsite:
                failures += 1
                d.note += (f"; NOT written: off-site url ({d.domain} is not a publisher domain); "
                           "check it, then rerun with --allow-offsite")
            elif urlparse(spec.url).path.lower().endswith(".pdf") and not args.replace:
                d.note += "; yaml url is already a PDF, left unchanged (use --replace)"
            elif fetch.write_back_url(args.registry, spec.id, d.url, today):
                d.note += "; url written to sources.yaml"
    print(f"{'id':<38} {'score':>5} {'official':<8} {'domain':<28} {'sha256':<64}  chosen url")
    for d in rows:
        print(f"{d.source_id:<38} {d.score:>5.2f} {'yes' if d.official else 'off-site' if d.url else '-':<8} "
              f"{d.domain or '-':<28} {d.sha256 or '-':<64}  {d.url or '-'}")
    for d in rows:
        if d.note != "downloaded":
            tail = f" - {MANUAL}" if d.sha256 is None and not d.note.startswith(("stored", "best")) else ""
            print(f"NOTE {d.source_id}: {d.note}{tail}")
    print(f"{len(rows)} source(s); {failures} without a stored PDF")
    return 0 if failures == 0 else 1


def cmd_fetch(args) -> int:
    specs = load_registry(args.registry)
    if args.discover:
        return cmd_fetch_discover(args, specs)
    if not (args.all or args.id):
        raise CliError("give --all, --id ID or --discover")
    chosen = specs if args.all else [_find(specs, args.id)]
    store = open_store()
    failures = 0
    for spec in chosen:
        try:
            src = fetch_source(spec, store, mode=args.mode)
            path = next(raw_dir(store).glob(f"{src.sha256}.*"))
            print(f"OK   {spec.id}: {path.name} ({path.stat().st_size} bytes)")
        except FetchError as e:
            failures += 1
            print(f"FAIL {spec.id}: {e}")
    n = store.con.execute("SELECT count(*) FROM source").fetchone()[0]
    print(f"{n} source rows; {failures} failure(s)")
    return 0 if failures == 0 else 1


def cmd_register_local(args) -> int:
    spec = _find(load_registry(args.registry), args.id)
    path = Path(args.path)
    if not path.is_file():
        raise CliError(f"no such file: {path}")
    store = open_store()
    sha = sha256_file(path)
    ext = path.suffix.lower().lstrip(".") or "bin"
    dest = raw_dir(store) / f"{sha}.{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(path, dest)
    record_source(spec, store, sha)
    print(f"registered {spec.id}: {dest.name} ({dest.stat().st_size} bytes)")
    return 0


def cmd_parse(args) -> int:
    store = open_store()
    if args.all:
        shas = [r[0] for r in store.con.execute(
            "SELECT DISTINCT sha256 FROM source WHERE sha256 IS NOT NULL ORDER BY 1").fetchall()]
    else:
        shas = [args.sha]
    for sha in shas:
        try:
            n = parse_source(sha, store)
        except FileNotFoundError as e:
            print(f"FAIL {sha[:12]}: {e}")
            return 1
        print(f"OK   {sha[:12]}: {n} page(s)")
    return 0


def _add_parse(sub):
    p = sub.add_parser("parse", help="parse raw sources into document_page rows")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--sha")
    p.set_defaults(func=cmd_parse)


def _add_fetch(sub):
    p = sub.add_parser("fetch", help="fetch sources from sources.yaml into the raw store")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true")
    g.add_argument("--id")
    p.add_argument("--mode", choices=["direct", "firecrawl"], default="direct")
    p.add_argument("--discover", action="store_true",
                   help="use Firecrawl to find, rank and download the best PDF per source (all, or --id)")
    p.add_argument("--write-urls", action="store_true",
                   help="with --discover: write each confirmed PDF url into sources.yaml")
    p.add_argument("--allow-offsite", action="store_true",
                   help="with --write-urls: also write a url whose site is not the publisher's")
    p.add_argument("--replace", action="store_true",
                   help="with --discover: overwrite a PDF or url that already works")
    p.set_defaults(func=cmd_fetch)


def _add_register_local(sub):
    p = sub.add_parser("register-local", help="copy a hand-downloaded file into the raw store")
    p.add_argument("path")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_register_local)


SEED_DIR = Path("rules/seed")


def cmd_rules_load(args) -> int:
    n = rule_cards.load_seed(args.dir, open_store())
    print(f"wrote {n} new or changed rule card(s) as draft from {args.dir}; unchanged cards keep their status")
    return 0


def cmd_rules_verify(args) -> int:
    store = open_store()
    rows = rule_cards.verify_all(store)
    print(f"{'rule_id':<20} {'ver':>3} {'status':<9} {'found':<6} {'page_no':>7} {'score':>6}")
    for c, qc in rows:
        page = "-" if qc.page_no is None else qc.page_no
        print(f"{c.rule_id:<20} {c.version:>3} {c.status:<9} {str(qc.found):<6} "
              f"{page!s:>7} {qc.score:>6.1f}")
        for name, pq in rule_cards.verify_params(c, store):
            pp = "-" if pq.page_no is None else pq.page_no
            print(f"{'  param ' + name:<20} {'':>3} {'':<9} {str(pq.found):<6} "
                  f"{pp!s:>7} {pq.score:>6.1f}")
    return 0


def cmd_rules_approve(args) -> int:
    try:
        rule_cards.approve(args.rule_id, args.version, args.by, open_store())
    except (rule_cards.NotVerified, KeyError) as e:
        raise CliError(str(e)) from e
    print(f"approved {args.rule_id} v{args.version} by {args.by}")
    return 0


def cmd_rules_disable(args) -> int:
    try:
        rule_cards.disable(args.rule_id, args.version, args.reason, open_store())
    except KeyError as e:
        raise CliError(str(e)) from e
    print(f"disabled {args.rule_id} v{args.version}")
    return 0


def _add_rules(sub):
    p = sub.add_parser("rules", help="load, verify, approve or disable rule cards")
    rs = p.add_subparsers(dest="rules_command", required=True)
    a = rs.add_parser("load", help="load rules/seed/*.yaml as draft cards")
    a.add_argument("--dir", type=Path, default=SEED_DIR)
    a.set_defaults(func=cmd_rules_load)
    a = rs.add_parser("verify", help="table of quote-verification results (read-only)")
    a.set_defaults(func=cmd_rules_verify)
    a = rs.add_parser("approve", help="approve a card whose quote is found verbatim")
    a.add_argument("rule_id")
    a.add_argument("--version", type=int, required=True)
    a.add_argument("--by", required=True)
    a.set_defaults(func=cmd_rules_approve)
    a = rs.add_parser("disable", help="disable a card with a reason")
    a.add_argument("rule_id")
    a.add_argument("--version", type=int, required=True)
    a.add_argument("--reason", required=True)
    a.set_defaults(func=cmd_rules_disable)


def cmd_policy_build(args) -> int:
    store = open_store()
    n = policy_index.build_index(args.product_id, args.sha, store)
    if args.insurer:
        store.con.execute("UPDATE policy_product SET insurer=? WHERE product_id=?",
                          [args.insurer, args.product_id])
    print(f"indexed {n} clause(s) for {args.product_id}")
    return 0


def cmd_policy_report(args) -> int:
    store = open_store()
    code_rows = policy_index.code_uniformity_report(store, args.reference)
    print("Standard exclusion codes (primary key): text compared with the baseline wording")
    print(f"{'code':<8} {'insurer':<36} result")
    for r in code_rows:
        print(f"{r.code:<8} {r.insurer:<36} {r.status}")
    bad = sum(r.status != "match" for r in code_rows)
    print(f"{len(code_rows)} code comparison(s); {bad} not a match")
    print()
    print("Secondary: numbered clause comparison")
    rows = policy_index.uniformity_report(store, args.reference)
    print(f"{'insurer':<30} {'clause':<10} result")
    for r in rows:
        print(f"{r.insurer:<30} {r.clause_no:<10} {'same' if r.matches_reference else 'DIFFERS'}")
    diff = sum(not r.matches_reference for r in rows)
    print(f"{len(rows)} comparison(s); {diff} differ from the reference")
    return 0


def cmd_snapshot(args) -> int:
    from sarthi.data import snapshot
    try:
        counts = snapshot.make_snapshot(open_store(), args.out)
    except snapshot.SnapshotError as e:
        raise CliError(str(e)) from e
    print(f"snapshot written to {args.out}; rows per table (privacy check):")
    for table, n in counts.items():
        print(f"  {table:<16} {n}")
    return 0


def _add_snapshot(sub):
    p = sub.add_parser("snapshot", help="copy only the public tables into a new store for the Space")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_snapshot)


def _add_policy(sub):
    p = sub.add_parser("policy", help="build the clause index; check wording uniformity")
    ps = p.add_subparsers(dest="policy_command", required=True)
    a = ps.add_parser("build", help="segment a parsed wording into policy_clause rows")
    a.add_argument("--product-id", required=True)
    a.add_argument("--sha", required=True)
    a.add_argument("--insurer")
    a.set_defaults(func=cmd_policy_build)
    a = ps.add_parser("report", help="print the uniformity table")
    a.add_argument("--reference", help="reference product_id (default: first in sort order)")
    a.set_defaults(func=cmd_policy_report)


def _ik(fn):
    try:
        return fn()
    except (cases.IKConfigError, cases.SpendCapExceeded, FetchError) as e:
        raise CliError(str(e)) from e


def cmd_cases_search(args) -> int:
    if args.ground not in cases.QUERIES:
        raise CliError(f"unknown ground '{args.ground}'. Known: {', '.join(cases.QUERIES)}")
    ids = _ik(lambda: cases.search_cases(cases.QUERIES[args.ground], max_results=args.max,
                                         store=open_store()))
    for i in ids:
        print(i)
    print(f"{len(ids)} result(s) for {args.ground}")
    return 0


def cmd_cases_fetch(args) -> int:
    store = open_store()
    for tid in args.tids:
        c = _ik(lambda: cases.fetch_case(tid, store))
        print(f"OK   {c.case_id}: {c.forum} {c.decided_on} insurer={c.insurer} outcome={c.outcome}")
    return 0


def _env_price(var: str, default: float) -> tuple[float, bool]:
    v = os.environ.get(var)
    return (float(v), True) if v else (default, False)


def cmd_cases_discover(args) -> int:
    from sarthi.data import discovery
    families = [f.strip() for f in args.families.split(",") if f.strip()]
    sp, sp_set = _env_price("IK_COST_SEARCH_INR", discovery.DEFAULT_SEARCH_INR)
    dp, dp_set = _env_price("IK_COST_DOC_INR", discovery.DEFAULT_DOC_INR)
    try:
        pl = discovery.plan(families, max_results=args.max_results_per_query, search_price=sp, doc_price=dp)
    except ValueError as e:
        raise CliError(str(e)) from e
    cap = float(os.environ.get("IK_CAP_INR", cases.DEFAULT_CAP_INR))
    spent = cases.total_spend_inr()
    if args.dry_run:
        print("DRY RUN: no calls are made, nothing is written")
        print(f"families: {', '.join(pl['families'])}")
        for q in pl["queries"]:
            print(f"  [{q['family']} -> {q['line']}] {q['query']}")
        print(f"{pl['n_queries']} query(ies) x up to {pl['pages_per_query_max']} page(s) "
              f"@ {sp:.2f} INR{'' if sp_set else ' (assumed; IK_COST_SEARCH_INR unset)'}")
        print(f"estimated search cost: at most {pl['est_search_inr_max']:.2f} INR "
              f"(less when a query has fewer hits than --max-results-per-query)")
        if args.fetch:
            print(f"--fetch adds {dp:.2f} INR{'' if dp_set else ' (assumed)'} per health/unsure candidate, "
                  f"bounded by --max-inr {args.max_inr:.2f}")
        print(f"run cap --max-inr {args.max_inr:.2f}; IK spent so far {spent:.2f} of IK_CAP_INR {cap:.2f} "
              f"(headroom {cap - spent:.2f} INR)")
        return 0
    dbp = data_dir() / "bima_sarthi.duckdb"
    try:
        stored = discovery.stored_case_tids(dbp)
    except Exception as e:  # e.g. the DB is locked by a writer
        if args.fetch:
            raise CliError(f"cannot read stored cases ({e}); refusing to --fetch blind") from e
        print(f"warning: cannot read stored cases ({e}); duplicates vs the DB will not be detected")
        stored = set()
    store = open_store() if args.fetch else None
    out = _ik(lambda: discovery.run_discovery(families, max_results=args.max_results_per_query,
                                              max_inr=args.max_inr, run_id=args.run_id, stored_tids=stored,
                                              fetch=args.fetch, store=store))
    r = out["run"]
    print(f"run {r['run_id']}: {len(r['queries'])} query(ies), {r['pages_billed']} page(s) billed, "
          f"{r['unique_new']} new candidate(s)")
    for q in r["queries"]:
        print(f"  {q['family']}: returned {q['returned']}/{q['total_found']} new {q['new']} "
              f"dup(stored {q['stored_duplicates']}, previous {q['previous_duplicates']}, "
              f"run {q['run_duplicates']}) [{q['stopped']}] {q['query'][:70]}")
    d = r["duplicates"]
    print(f"duplicates: stored {d['stored']}, previous runs {d['previous']}, within run {d['within_run']}")
    pc = r["prescreen_counts"]
    print(f"prescreen by label: {pc['by_label']}")
    print(f"product_line_guess: {pc['by_line']}")
    if args.fetch:
        print(f"fetched {r['fetched']} document(s)" + (f"; errors: {r['fetch_errors']}" if r["fetch_errors"] else ""))
    print(f"IK spend this run: {out['spent_this_run']:.2f} INR (run cap {args.max_inr:.2f}); "
          f"IK_CAP_INR headroom: {out['headroom_inr']:.2f} INR of {r['ik_cap_inr']:.2f}")
    if out["stopped"] == "run_cap":
        print(f"STOPPED: --max-inr {args.max_inr:.2f} reached; remaining queries/fetches were not run")
    elif out["stopped"] == "global_cap":
        print("STOPPED: IK_CAP_INR reached; remaining queries/fetches were not run")
    return 0


def cmd_cases_add_local(args) -> int:
    path = Path(args.path)
    if not path.is_file():
        raise CliError(f"no such file: {path}")
    decided = date.fromisoformat(args.decided_on) if args.decided_on else None
    c = cases.add_local(path, args.case_id, open_store(), forum=args.forum, decided_on=decided,
                        outcome=args.outcome)
    print(f"OK   {c.case_id}: insurer={c.insurer} outcome={c.outcome}")
    return 0


def cmd_cases_extract(args) -> int:
    store = open_store()
    ids = list(args.case_ids)
    if args.all_unextracted:
        ids += [r[0] for r in store.con.execute(
            'SELECT case_id FROM "case" WHERE source_sha256 IS NOT NULL AND case_id NOT IN '
            "(SELECT case_id FROM case_fact) ORDER BY 1").fetchall()]
    if not ids:
        raise CliError("give case ids or --all-unextracted")
    for cid in ids:
        try:
            skipped = [] if args.force else case_facts.protected_fields(cid, store)
            rows = case_facts.extract_case(cid, store, force=args.force)
        except KeyError as e:
            raise CliError(str(e)) from e
        n_rev = sum(r.status == "needs_review" for r in rows)
        print(f"OK   {cid}: {len(rows)} fact(s), {n_rev} need review"
              + (f"; skipped {len(skipped)} reviewed field(s): {', '.join(skipped)}" if skipped else ""))
    return 0


def cmd_cases_review(args) -> int:
    store = open_store()
    form = case_facts.build_review_form(args.case_id, store)
    if form is None:
        raise CliError(f"no extracted facts for case '{args.case_id}'")
    if not args.json:
        print(json.dumps(form, indent=1, default=str))
        return 0
    path = Path(args.json)
    if not path.is_file():
        raise CliError(f"no such file: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("the decisions file must be a JSON object of field -> decision")
        n = case_facts.apply_review_form(args.case_id, raw, args.reviewer, store)
    except (ValueError, KeyError) as e:
        raise CliError(str(e)) from e
    print(f"OK   {args.case_id}: {n} fact(s) decided")
    return 0


def cmd_cases_set_outcome(args) -> int:
    store = open_store()
    if store.con.execute('SELECT 1 FROM "case" WHERE case_id=?', [args.case_id]).fetchone() is None:
        raise CliError(f"unknown case '{args.case_id}'")
    store.con.execute('UPDATE "case" SET outcome=? WHERE case_id=?', [args.outcome, args.case_id])
    print(f"OK   {args.case_id}: outcome={args.outcome}")
    return 0


def cmd_cases_set_product_line(args) -> int:
    store = open_store()
    if store.con.execute('SELECT 1 FROM "case" WHERE case_id=?', [args.case_id]).fetchone() is None:
        raise CliError(f"unknown case '{args.case_id}'")
    store.con.execute('UPDATE "case" SET product_line=? WHERE case_id=?',
                      [args.product_line, args.case_id])
    print(f"OK   {args.case_id}: product_line={args.product_line}")
    return 0


def cmd_cases_backfill_product_line(args) -> int:
    counts = case_issues.backfill_product_line(open_store())
    print(" ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def cmd_cases_set_appellant(args) -> int:
    store = open_store()
    row = store.con.execute('SELECT outcome, policyholder_prevailed FROM "case" WHERE case_id=?',
                            [args.case_id]).fetchone()
    if row is None:
        raise CliError(f"unknown case '{args.case_id}'")
    store.con.execute('UPDATE "case" SET appellant=? WHERE case_id=?', [args.appellant, args.case_id])
    derived = case_issues.prevailed_from_outcome(args.appellant, row[0])
    if row[1] is None and derived is not None:
        store.con.execute('UPDATE "case" SET policyholder_prevailed=? WHERE case_id=?',
                          [derived, args.case_id])
    print(f"OK   {args.case_id}: appellant={args.appellant}"
          + (f", policyholder_prevailed={derived} (from outcome {row[0]})"
             if row[1] is None and derived is not None else ""))
    return 0


def cmd_cases_exclude(args) -> int:
    reason = " ".join(args.reason.split())
    if not reason:
        raise CliError("--reason must not be empty")
    store = open_store()
    if store.con.execute('SELECT 1 FROM "case" WHERE case_id=?', [args.case_id]).fetchone() is None:
        raise CliError(f"unknown case '{args.case_id}'")
    store.con.execute('UPDATE "case" SET excluded_reason=? WHERE case_id=?', [reason, args.case_id])
    print(f"OK   {args.case_id}: excluded from evaluation ({reason})")
    return 0


def cmd_cases_backfill_appellant(args) -> int:
    counts = case_issues.backfill_appellant(open_store())
    print(" ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def cmd_issues_draft(args) -> int:
    store = open_store()
    ids = list(args.case_ids)
    if args.all:
        ids += [r[0] for r in store.con.execute(
            'SELECT case_id FROM "case" WHERE source_sha256 IS NOT NULL ORDER BY 1').fetchall()]
    if not ids:
        raise CliError("give case ids or --all")
    for cid in ids:
        try:
            skipped = [] if args.force else case_issues.protected_issues(cid, store)
            rows = case_issues.draft_issues(cid, store, force=args.force)
        except (KeyError, cases.SpendCapExceeded) as e:
            raise CliError(str(e)) from e
        n_rev = sum(r.status == "needs_review" for r in rows)
        print(f"OK   {cid}: {len(rows)} issue row(s), {n_rev} need review"
              + (f"; skipped reviewed: {', '.join(skipped)}" if skipped else ""))
    return 0


def cmd_issues_review(args) -> int:
    store = open_store()
    path = Path(args.json)
    if not path.is_file():
        raise CliError(f"no such file: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("the decisions file must be a JSON object of issue -> decision")
        n = case_issues.apply_review_file(args.case_id, raw, args.reviewer, store)
    except (ValueError, KeyError) as e:
        raise CliError(str(e)) from e
    print(f"OK   {args.case_id}: {n} issue(s) decided")
    return 0


def cmd_issues_sheet(args) -> int:
    n = case_issues.write_review_sheet(open_store(), args.out)
    print(f"OK   {n} case(s) written to {args.out}")
    return 0


OUTCOMES = ("allowed", "partly_allowed", "dismissed")


def _add_cases(sub):
    p = sub.add_parser("cases", help="ingest real judgments (Indian Kanoon or hand-saved)")
    cs = p.add_subparsers(dest="cases_command", required=True)
    a = cs.add_parser("search", help="search Indian Kanoon for one rejection ground (costs money)")
    a.add_argument("--ground", required=True)
    a.add_argument("--max", type=int, default=15)
    a.set_defaults(func=cmd_cases_search)
    a = cs.add_parser("fetch", help="fetch judgments by Indian Kanoon doc id (costs money)")
    a.add_argument("tids", nargs="+")
    a.set_defaults(func=cmd_cases_fetch)
    a = cs.add_parser("discover", help="spend-capped candidate discovery across query families (costs money)")
    a.add_argument("--families", required=True, help="comma-separated family names, 'all', or 'none' (no search; with --fetch, fetch from the log)")
    a.add_argument("--max-results-per-query", type=int, default=60)
    a.add_argument("--max-inr", type=float, default=120.0, help="hard stop for THIS run (search + fetch)")
    a.add_argument("--dry-run", action="store_true", help="print the plan and estimated cost; no calls")
    a.add_argument("--fetch", action="store_true", help="also fetch likely_health/unsure health candidates")
    a.add_argument("--run-id")
    a.set_defaults(func=cmd_cases_discover)
    a = cs.add_parser("add-local", help="register a hand-saved judgment as a case")
    a.add_argument("path")
    a.add_argument("--case-id", required=True)
    a.add_argument("--forum")
    a.add_argument("--decided-on")
    a.add_argument("--outcome", choices=OUTCOMES, help="override the detected outcome")
    a.set_defaults(func=cmd_cases_add_local)
    a = cs.add_parser("review", help="show a case's review form, or apply decisions with --json")
    a.add_argument("case_id")
    a.add_argument("--json", help="decisions file: {field: {action, value, note}}; extracted facts default to accept")
    a.add_argument("--reviewer", default="cli")
    a.set_defaults(func=cmd_cases_review)
    a = cs.add_parser("set-outcome", help="set the human-read outcome of a case")
    a.add_argument("case_id")
    a.add_argument("outcome", choices=OUTCOMES)
    a.set_defaults(func=cmd_cases_set_outcome)
    a = cs.add_parser("extract", help="extract facts from judgments with a model (costs money)")
    a.add_argument("case_ids", nargs="*")
    a.add_argument("--all-unextracted", action="store_true")
    a.add_argument("--force", action="store_true", help="overwrite fields a human already reviewed")
    a.set_defaults(func=cmd_cases_extract)
    a = cs.add_parser("set-product-line", help="set the product line of a case (health, life, motor, ...)")
    a.add_argument("case_id")
    a.add_argument("product_line", choices=PRODUCT_LINES)
    a.set_defaults(func=cmd_cases_set_product_line)
    a = cs.add_parser("backfill-product-line",
                      help="mark cases with a human-reviewed rule issue as health (evidence only)")
    a.set_defaults(func=cmd_cases_backfill_product_line)
    a = cs.add_parser("set-appellant", help="set who appealed (derives policyholder_prevailed if unset)")
    a.add_argument("case_id")
    a.add_argument("appellant", choices=("insurer", "policyholder"))
    a.set_defaults(func=cmd_cases_set_appellant)
    a = cs.add_parser("exclude", help="exclude a case from evaluation (out of scope or duplicate)")
    a.add_argument("case_id")
    a.add_argument("--reason", required=True, help="why the case is excluded")
    a.set_defaults(func=cmd_cases_exclude)
    a = cs.add_parser("backfill-appellant", help="infer appellant / policyholder_prevailed from titles")
    a.set_defaults(func=cmd_cases_backfill_appellant)
    ip = cs.add_parser("issues", help="per-issue holdings: draft with a model, review, sheet")
    isub = ip.add_subparsers(dest="issues_command", required=True)
    a = isub.add_parser("draft", help="draft issue holdings with a model (costs money)")
    a.add_argument("case_ids", nargs="*")
    a.add_argument("--all", action="store_true")
    a.add_argument("--force", action="store_true", help="overwrite issues a human already reviewed")
    a.set_defaults(func=cmd_issues_draft)
    a = isub.add_parser("review", help="apply decisions: {issue: {action, holding, quote, note}}")
    a.add_argument("case_id")
    a.add_argument("--json", required=True)
    a.add_argument("--reviewer", default="cli")
    a.set_defaults(func=cmd_issues_review)
    a = isub.add_parser("sheet", help="write the one-page review sheet")
    a.add_argument("--out", type=Path, default=Path("data/review/issues-review.md"))
    a.set_defaults(func=cmd_issues_sheet)


def cmd_stats_load(args) -> int:
    if not args.csv.is_file():
        raise CliError(f"no such file: {args.csv}")
    try:
        n = stats.load_stats_csv(args.csv, open_store())
    except (stats.StatNotOnPage, ValueError) as e:
        raise CliError(str(e)) from e
    print(f"loaded {n} stat row(s) from {args.csv}")
    return 0


def _add_stats(sub):
    p = sub.add_parser("stats", help="load hand-entered insurer statistics (verified on-page)")
    ss = p.add_subparsers(dest="stats_command", required=True)
    a = ss.add_parser("load", help="load the CSV; every value must appear on its cited page")
    a.add_argument("--csv", type=Path, default=stats.DEFAULT_CSV)
    a.set_defaults(func=cmd_stats_load)


def cmd_literature_search(args) -> int:
    try:
        works = literature.search_literature(args.query, n=args.n)
    except literature.LiteratureError as e:
        raise CliError(str(e)) from e
    print(f"{len(works)} work(s) written to {literature.DEFAULT_OUT}")
    return 0


def _add_literature(sub):
    p = sub.add_parser("literature", help="search OpenAlex and write docs/evidence/literature.md")
    ls = p.add_subparsers(dest="literature_command", required=True)
    a = ls.add_parser("search", help="search OpenAlex")
    a.add_argument("query")
    a.add_argument("--n", type=int, default=20)
    a.set_defaults(func=cmd_literature_search)


def cmd_eval(args) -> int:
    from sarthi.data import evaluate
    run_id = args.run_id or datetime.now().strftime("eval-%Y%m%d-%H%M%S")
    summary = evaluate.run_eval(run_id, args.methods, args.repeats, open_store())
    evaluate.write_report(summary, args.out)
    print(f"run {run_id}: {summary.n_cases} case(s), {summary.n_primary} primary, "
          f"{summary.n_abstention_set} abstention-set, {summary.n_case_level_excluded} excluded "
          f"from case level (winner unknown); report at {args.out}")
    return 0


def _add_eval(sub):
    p = sub.add_parser("eval", help="rules vs model-only baselines against reviewed holdings (finding level) and who prevailed")
    p.add_argument("--methods", nargs="+", choices=["rules", "glimmer_only", "spark_only"],
                   default=["rules", "glimmer_only", "spark_only"])
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--run-id")
    p.add_argument("--out", type=Path, default=Path("docs/eval/report.md"))
    p.set_defaults(func=cmd_eval)


def _append_report(out: Path, lines: list[str]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = out.read_text(encoding="utf-8") if out.exists() else ""
    sep = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    out.write_text(existing + sep + "\n".join(lines) + "\n", encoding="utf-8")


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def cmd_eval_reading(args) -> int:
    from sarthi.app import extract
    r = extract.eval_reading(args.docs, args.truth)
    print(f"reading: n_docs={r.n_docs} field_accuracy={r.field_accuracy} "
          f"flagged_wrong_share={r.flagged_wrong_share}")
    _append_report(args.out, [
        "## Reading accuracy (consented documents)", "",
        f"Measured on n = {r.n_docs} consented document(s); not generalised beyond them. "
        "Aggregate numbers only.", "",
        "| Metric | Value |", "|---|---|",
        f"| Field accuracy | {_pct(r.field_accuracy)} |",
        f"| Wrong fields flagged for confirmation | {_pct(r.flagged_wrong_share)} |"])
    return 0


def clause_hit_rate(store: Store, reference: str | None = None) -> tuple[int, int, int, str]:
    """Hits over lookups across all stored wordings.

    For each product (the reference included) and each clause_no of the reference product,
    a lookup is a hit when policy_index.find_clause(product, clause_no) is not None.
    Returns (hits, lookups, n_products, reference_product_id).
    """
    ids = [r[0] for r in store.con.execute(
        "SELECT product_id FROM policy_product ORDER BY product_id").fetchall()]
    if not ids:
        raise CliError("no indexed wordings: run `policy build` first")
    ref = reference or ids[0]
    ref_nos = [r[0] for r in store.con.execute(
        "SELECT clause_no FROM policy_clause WHERE product_id=? ORDER BY clause_no", [ref]).fetchall()]
    hits = lookups = 0
    for pid in ids:
        for no in ref_nos:
            lookups += 1
            hits += policy_index.find_clause(pid, no, store) is not None
    return hits, lookups, len(ids), ref


def cmd_eval_clauses(args) -> int:
    hits, lookups, n_prod, ref = clause_hit_rate(open_store(), args.reference)
    rate = hits / lookups if lookups else None
    print(f"clause lookup: {hits}/{lookups} hit(s) = {_pct(rate)} (n = {lookups} lookup(s), "
          f"{n_prod} wording(s), reference {ref})")
    _append_report(args.out, [
        "## Clause-lookup hit rate (Arogya Sanjeevani wordings)", "",
        f"Definition: for each of {n_prod} wording(s) and each clause number of the reference "
        f"product ({ref}), a lookup is a hit when `find_clause` returns a clause.", "",
        f"n = {lookups} lookup(s) across {n_prod} wording(s): {hits} hit(s), {_pct(rate)}."])
    return 0


def _add_eval_extras(sub):
    p = sub.add_parser("eval-reading", help="field accuracy of photo reading on consented documents")
    p.add_argument("--docs", type=Path, required=True)
    p.add_argument("--truth", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("docs/eval/report.md"))
    p.set_defaults(func=cmd_eval_reading)
    p = sub.add_parser("eval-clauses", help="clause-lookup hit rate over every stored wording")
    p.add_argument("--reference", help="reference product_id (default: first in sort order)")
    p.add_argument("--out", type=Path, default=Path("docs/eval/report.md"))
    p.set_defaults(func=cmd_eval_clauses)


def cmd_freshness_check(args) -> int:
    from datetime import timedelta

    from sarthi.data import freshness
    since = args.since or (date.today() - timedelta(days=7))
    try:
        alerts = freshness.check_freshness(open_store(), since)
    except freshness.FreshnessError as e:
        raise CliError(str(e)) from e
    for a in alerts:
        print(f"NEW  {a.rule_id}: {a.found_on} {a.found_url} ({a.found_title})")
    print(f"{len(alerts)} new freshness alert(s) since {since}")
    return 0


def _add_freshness(sub):
    p = sub.add_parser("freshness", help="search IRDAI for circulars that may affect approved rules")
    fs = p.add_subparsers(dest="freshness_command", required=True)
    a = fs.add_parser("check", help="raise alerts for new circulars (needs TAVILY_API_KEY)")
    a.add_argument("--since", type=lambda s: date.fromisoformat(s), default=None,
                   help="YYYY-MM-DD (default: 7 days ago)")
    a.set_defaults(func=cmd_freshness_check)


SUBCOMMANDS = [_add_snapshot, _add_fetch, _add_register_local, _add_parse, _add_rules, _add_policy, _add_cases,
               _add_stats, _add_literature, _add_eval, _add_eval_extras,
               _add_freshness]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sarthi.data.cli")
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    sub = ap.add_subparsers(dest="command", required=True)
    for add in SUBCOMMANDS:
        add(sub)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    finally:
        while _OPENED:
            _OPENED.pop().close()


if __name__ == "__main__":
    sys.exit(main())
