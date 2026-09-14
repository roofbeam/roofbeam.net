#!/usr/bin/env python3
"""costs/page.json → costs/index.html — the upkeep page.

    tools/costs.py build     # render costs/index.html from the record
    tools/costs.py check     # reconcile the split without writing anything

The expense tracker is a TAX record: it counts every deductible business
expense, which is the right question for Schedule C and the wrong question
for "what does it cost to keep this running." This page answers the second
one, and shows its work — every row the tracker holds is either upkeep or
explicitly excluded with a reason, and the two totals add back to the
tracker's own. `build` refuses to render if they don't, because a
transparency page that quietly drops a line item is worse than no page.

The head comes from tools/share.py, the same generator the toys and musings
use, so this page gets its canonical link, OG card and JSON-LD for free and
`share.py verify` checks it in the same pass.
"""

import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import share  # noqa: E402  — the single source for share metadata

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORD = ROOT / "costs" / "page.json"
OUT = ROOT / "costs" / "index.html"

CENT = 0.005  # float money: anything under half a cent is a rounding artefact


def money(v):
    return "not recorded" if v is None else f"${v:,.2f}"


def totals(d):
    upkeep = sum(r["paid_2026"] for r in d["upkeep"] if r["paid_2026"] is not None)
    excluded = sum(r["amount"] for r in d["excluded"])
    return upkeep, excluded


def reconcile(d):
    """The tracker's total must equal upkeep + excluded. If it doesn't, some
    row is being counted twice or not at all — say which way and by how much."""
    upkeep, excluded = totals(d)
    drift = round(d["tracker_total"] - (upkeep + excluded), 2)
    return upkeep, excluded, drift


def rows(items, amount_key, note_key):
    out = []
    for r in items:
        amt = money(r.get(amount_key))
        note = html.escape(r[note_key])
        conf = r.get("confidence")
        tag = f'<span class="conf">{html.escape(conf)}</span>' if conf else ""
        what = f'<div class="what">{html.escape(r["what"])}</div>' if r.get("what") else ""
        out.append(
            f'      <li>\n'
            f'        <div class="row">\n'
            f'          <div class="left"><span class="vendor">{html.escape(r["vendor"])}</span>{tag}{what}</div>\n'
            f'          <div class="amt">{amt}</div>\n'
            f'        </div>\n'
            f'        <p class="note">{note}</p>\n'
            f'      </li>'
        )
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">

<!-- share metadata — generated from costs/page.json by tools/share.py.
     Do not hand-edit: change the record, re-run `tools/share.py cards`,
     and `tools/share.py verify` will fail if these drift. -->
{head}

<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{ --bg:#f6f3ec; --panel:#fffdf8; --ink:#23201b; --muted:#6b6459;
  --line:#e2dccf; --accent:#b4531f; --accent-soft:#eadfce; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#17150f; --panel:#201d16; --ink:#ece7db; --muted:#a49b89;
  --line:#322d23; --accent:#e08a4e; --accent-soft:#2b2418; }} }}
:root[data-theme="dark"] {{ --bg:#17150f; --panel:#201d16; --ink:#ece7db;
  --muted:#a49b89; --line:#322d23; --accent:#e08a4e; --accent-soft:#2b2418; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); line-height:1.65;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif; }}
a {{ color:var(--accent); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
header {{ border-bottom:1px solid var(--line); }}
.nav {{ display:flex; justify-content:space-between; align-items:baseline;
  padding:16px 24px; max-width:760px; margin:0 auto; }}
.brand {{ font-family:Fraunces,Georgia,serif; font-weight:600; font-size:1.1rem; color:var(--ink); }}
.brand span {{ color:var(--accent); }}
.nav a.link {{ color:var(--muted); font-size:.9rem; margin-left:20px; }}
.nav a.link:hover {{ color:var(--ink); text-decoration:none; }}
main {{ max-width:760px; margin:0 auto; padding:56px 24px 96px; }}
h1 {{ font-family:Fraunces,Georgia,serif; font-weight:600; font-size:clamp(2rem,5vw,2.6rem);
  letter-spacing:-.02em; margin:0 0 14px; }}
h2 {{ font-family:Fraunces,Georgia,serif; font-weight:600; font-size:1.35rem;
  margin:0 0 6px; letter-spacing:-.01em; }}
.lede {{ color:var(--muted); max-width:54ch; margin:0 0 14px; font-size:1.05rem; }}
.scope {{ color:var(--muted); max-width:56ch; margin:0 0 44px; font-size:.92rem;
  border-left:2px solid var(--line); padding-left:14px; }}
section {{ margin:0 0 52px; }}
.sub {{ color:var(--muted); font-size:.93rem; margin:0 0 20px; max-width:56ch; }}
ul {{ list-style:none; padding:0; margin:0; }}
li {{ border-bottom:1px solid var(--line); padding:16px 0; }}
li:last-child {{ border-bottom:none; }}
.row {{ display:flex; justify-content:space-between; align-items:baseline; gap:16px; }}
.left {{ min-width:0; }}
.vendor {{ font-weight:600; }}
.what {{ color:var(--muted); font-size:.92rem; margin-top:2px; }}
.amt {{ font-variant-numeric:tabular-nums; white-space:nowrap; font-weight:500; }}
.conf {{ display:inline-block; font-size:.66rem; letter-spacing:.07em; text-transform:uppercase;
  color:var(--accent); background:var(--accent-soft); padding:2px 7px; border-radius:999px;
  margin-left:9px; vertical-align:1px; }}
.note {{ color:var(--muted); font-size:.88rem; margin:8px 0 0; max-width:60ch; }}
.total {{ display:flex; justify-content:space-between; align-items:baseline; gap:16px;
  background:var(--panel); border:1px solid var(--line); border-radius:14px;
  padding:18px 20px; margin-top:22px; }}
.total .k {{ font-weight:600; }}
.total .v {{ font-family:Fraunces,Georgia,serif; font-size:1.7rem; font-variant-numeric:tabular-nums;
  white-space:nowrap; }}
.caveat {{ background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--accent);
  border-radius:10px; padding:16px 18px; margin-top:18px; }}
.caveat p {{ margin:0; font-size:.92rem; color:var(--muted); }}
.caveat p + p {{ margin-top:10px; }}
.caveat strong {{ color:var(--ink); }}
.check {{ border-top:1px solid var(--line); margin-top:44px; padding-top:22px;
  color:var(--muted); font-size:.88rem; }}
.check table {{ border-collapse:collapse; margin:12px 0 0; }}
.check td {{ padding:3px 0; }}
.check td.n {{ text-align:right; padding-left:18px; font-variant-numeric:tabular-nums; color:var(--ink); }}
.check tr.sum td {{ border-top:1px solid var(--line); padding-top:7px; font-weight:600; }}
footer {{ border-top:1px solid var(--line); margin-top:56px; padding-top:22px;
  color:var(--muted); font-size:.85rem; }}
@media (max-width:520px) {{
  .row {{ flex-direction:column; gap:4px; }}
  .amt {{ font-size:1.05rem; }}
  .total {{ flex-direction:column; gap:4px; }}
}}
</style>
</head>
<body>
<header><nav class="nav">
  <a class="brand" href="/">Roof<span>beam</span></a>
  <span><a class="link" href="/#projects">Projects</a><a class="link" href="/">Home</a></span>
</nav></header>
<main>
  <h1>{h1}</h1>
  <p class="lede">{lede}</p>
  <p class="scope">{scope}</p>

  <section>
    <h2>Upkeep</h2>
    <p class="sub">What recurs to keep the site and the toys running.</p>
    <ul>
{upkeep_rows}
    </ul>
    <div class="total"><span class="k">Paid so far in 2026</span><span class="v">{upkeep_total}</span></div>
    <div class="caveat">
      <p><strong>This is not an annual rate, and it would be dishonest to present it as one.</strong>
      Two of the six lines above are unresolved: the Workspace mailbox has never had its
      price written down, and the Hetzner charges vary month to month with a gap since June.
      Until both are settled, what it costs per year to run this is genuinely unknown.</p>
      <p>The domain is the other distortion, in the opposite direction: $57.00 was paid once
      and covers three years, so it flatters the annual figure by about $38.</p>
    </div>
  </section>

  <section>
    <h2>What isn&rsquo;t counted</h2>
    <p class="sub">Real expenses, deductible against the business, and not upkeep of this
    site. Counting them here would inflate the number, so they are listed instead.</p>
    <ul>
{excluded_rows}
    </ul>
    <div class="total"><span class="k">Excluded</span><span class="v">{excluded_total}</span></div>
  </section>

  <section>
    <h2>Not this entity</h2>
    <p class="sub">There was an earlier Roofbeam LLC, and it was allowed to lapse.
    Artifacts of it still surface and still bill.</p>
    <ul>
{other_rows}
    </ul>
  </section>

  <div class="check">
    The tracker records <strong>{tracker_total}</strong> of deductible expense for 2026.
    Nothing above is dropped &mdash; the split accounts for all of it:
    <table>
      <tr><td>Upkeep</td><td class="n">{upkeep_total}</td></tr>
      <tr><td>Excluded</td><td class="n">{excluded_total}</td></tr>
      <tr class="sum"><td>Tracker total</td><td class="n">{tracker_total}</td></tr>
    </table>
  </div>

  <footer>
    {source} &middot; last updated {updated}.
    Figures are as recorded, never estimated; where something is unknown it says so.
  </footer>
</main>
</body>
</html>
"""


def build(write=True):
    d = json.loads(RECORD.read_text())
    upkeep, excluded, drift = reconcile(d)

    if abs(drift) > CENT:
        direction = "unaccounted for" if drift > 0 else "counted twice"
        print(
            f"FAIL — the split does not reconcile to the tracker.\n\n"
            f"  upkeep        {money(upkeep)}\n"
            f"  excluded      {money(excluded)}\n"
            f"  sum           {money(upkeep + excluded)}\n"
            f"  tracker total {money(d['tracker_total'])}\n"
            f"  drift         {money(abs(drift))} {direction}\n\n"
            f"Fix costs/page.json — every tracker line belongs in exactly one of the\n"
            f"two lists, or the page is claiming a completeness it does not have.",
            file=sys.stderr,
        )
        return 1

    if not write:
        print(f"OK — upkeep {money(upkeep)} + excluded {money(excluded)} "
              f"= tracker {money(d['tracker_total'])}.")
        return 0

    page = PAGE.format(
        title=html.escape(share.page_title(d)),
        desc=html.escape(d["tagline"]),
        head=share.head_block(d),
        h1=html.escape(d["title"]),
        lede=html.escape(d["tracker_note"]),
        scope=html.escape(d["scope"]),
        upkeep_rows=rows(d["upkeep"], "paid_2026", "note"),
        excluded_rows=rows(d["excluded"], "amount", "why"),
        other_rows=rows(d["not_this_entity"], "amount", "why"),
        upkeep_total=money(upkeep),
        excluded_total=money(excluded),
        tracker_total=money(d["tracker_total"]),
        source=html.escape(d["source"]),
        updated=d["updated"],
    )
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page)
    print(f"costs/index.html — upkeep {money(upkeep)}, excluded {money(excluded)}, "
          f"reconciles to {money(d['tracker_total'])}.")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        sys.exit(build())
    elif cmd == "check":
        sys.exit(build(write=False))
    else:
        sys.exit(__doc__)
