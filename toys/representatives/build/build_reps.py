#!/usr/bin/env python3
"""Build the decks for Meet Your Government.

    pip install pyyaml
    python3 toys/representatives/build/build_reps.py

Writes toys/representatives/data/<ST>.json per state (its Congress
delegation, its elected executives, its legislature, its highest court),
data/US.json (President, Vice President, Cabinet, Supreme Court), and
data/states.json as the index. Sources, all public domain or CC0:

  - Congress: unitedstates/congress-legislators — current members, term
    history, social handles, committee seats.
  - State legislators: Open States bulk "people/current" CSVs. No tenure
    or committees in these files, so state cards say less than federal
    ones. That asymmetry is the data's, not a judgement; the page says so.
  - State executives: the openstates/people repository's executive/ files.
    Coverage varies by state; the page doesn't pretend otherwise.
  - Federal executive, Supreme Court, state high courts: Wikidata.
    Wikidata keeps fictional presidents and forgets to close old terms, so
    only real, living people count, and each office takes its most
    recently started holder.
  - State supreme court *justices* are deliberately absent: no open source
    is current (Wikidata has a fraction of them; CourtListener still seats
    Justice Souter). The state's court gets one card that links out.

Facts only. No scores, no ratings, no party colour-coding: the toy is
"learn more / skip", not "thumbs up / thumbs down".
"""

import csv
import datetime as dt
import io
import json
import pathlib
import sys
import tarfile
import urllib.parse
import urllib.request

import yaml

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "data"

CL = "https://unitedstates.github.io/congress-legislators"
OS = "https://data.openstates.org/people/current/{}.csv"
PHOTO = "https://unitedstates.github.io/images/congress/225x275/{}.jpg"
OS_PEOPLE = "https://github.com/openstates/people/archive/refs/heads/main.tar.gz"
WDQS = "https://query.wikidata.org/sparql"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{}?width=450"

# Wikidata items, each confirmed by label lookup (not memory: a wrong QID
# here once returned a German court title).
POTUS, VPOTUS, CHIEF_JUSTICE, ASSOC_JUSTICE = "Q11696", "Q11699", "Q11147", "Q11144"
US_CABINET = "Q639738"
STATE_SUPREME_COURT = "Q7603882"
SERVICE_SECRETARIES = {"United States Secretary of the Army", "United States Secretary of the Navy",
                       "United States Secretary of the Air Force"}

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia", "PR": "Puerto Rico",
    "AS": "American Samoa", "GU": "Guam", "MP": "Northern Mariana Islands",
    "VI": "U.S. Virgin Islands",
}

# What each state calls its lower chamber, and its members. Everyone else:
# "House of Representatives", "State Representative".
LOWER = {
    "CA": ("Assembly", "Assemblymember"), "NV": ("Assembly", "Assemblymember"),
    "NY": ("Assembly", "Assemblymember"), "WI": ("Assembly", "Assemblymember"),
    "NJ": ("General Assembly", "Assemblymember"),
    "MD": ("House of Delegates", "Delegate"), "VA": ("House of Delegates", "Delegate"),
    "WV": ("House of Delegates", "Delegate"),
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "roofbeam.net build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def party(p):
    """One vocabulary across sources: Wikidata says "Connecticut Republican"
    and "independent politician"; Open States says "Democrat"."""
    p = (p or "").replace(" Party", "")
    for name in ("Republican", "Democratic"):
        if name in p:
            return name
    if p == "Democrat":
        return "Democratic"
    if p.lower().startswith("independent"):
        return "Independent"
    return p


def ordinal(n):
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def spans(terms, kind):
    """Collapse consecutive same-chamber terms into (first_year, last_year) runs."""
    runs = []
    for t in terms:
        if t["type"] != kind:
            continue
        s, e = int(t["start"][:4]), int(t["end"][:4])
        if runs and s - runs[-1][1] <= 1:
            runs[-1][1] = e
        else:
            runs.append([s, e])
    return runs


def federal():
    people = json.loads(get(f"{CL}/legislators-current.json"))
    social = {p["id"]["bioguide"]: p.get("social", {})
              for p in json.loads(get(f"{CL}/legislators-social-media.json"))}
    committees = {c["thomas_id"]: c for c in json.loads(get(f"{CL}/committees-current.json"))}
    names = {}
    for c in committees.values():
        names[c["thomas_id"]] = c["name"]
        for sc in c.get("subcommittees", []):
            names[c["thomas_id"] + sc["thomas_id"]] = sc["name"]
    seats = {}
    for cid, members in json.loads(get(f"{CL}/committee-membership-current.json")).items():
        if cid not in committees:  # subcommittees: keep the deck about full committees
            continue
        for m in members:
            seats.setdefault(m["bioguide"], []).append(
                {"name": names[cid], "title": m.get("title", "")})

    out = []
    for p in people:
        bg = p["id"]["bioguide"]
        cur = p["terms"][-1]
        kind = cur["type"]
        chamber_terms = [t for t in p["terms"] if t["type"] == kind]
        run = spans(p["terms"], kind)[-1]
        # Senators: count 6-year terms; House: count 2-year terms (the run in office now).
        n = sum(1 for t in chamber_terms if int(t["start"][:4]) >= run[0])
        if kind == "sen":
            role = "U.S. Senator"
            seat = STATES[cur["state"]]
        elif cur["state"] in ("DC", "PR", "AS", "GU", "MP", "VI"):
            role = "Resident Commissioner" if cur["state"] == "PR" else "Delegate to the U.S. House"
            seat = STATES[cur["state"]]
        else:
            role = "U.S. Representative"
            d = cur.get("district", 0)
            seat = f"{STATES[cur['state']]} · " + ("at large" if d == 0 else f"District {d}")
        career = []
        for t, label in (("rep", "U.S. House"), ("sen", "U.S. Senate")):
            for s, e in spans(p["terms"], t):
                career.append({"label": label, "from": s, "to": None if e > dt.date.today().year else e})
        career.sort(key=lambda c: c["from"])
        ids = p["id"]
        sm = social.get(bg, {})
        out.append({
            "id": bg,
            "level": "federal",
            "branch": "legislative",
            "chamber": "senate" if kind == "sen" else "house",
            "state": cur["state"],
            "district": str(cur.get("district", "")) if kind == "rep" else "",
            "name": p["name"].get("official_full") or f"{p['name']['first']} {p['name']['last']}",
            "role": role,
            "seat": seat,
            "party": party(cur.get("party")),
            "since": run[0],
            "term": f"{ordinal(n)} term" if n > 1 else "1st term",
            "term_ends": cur["end"][:4],
            "born": p.get("bio", {}).get("birthday", ""),
            "photo": PHOTO.format(bg),
            "phone": cur.get("phone", ""),
            "office": cur.get("address", ""),
            "website": cur.get("url", ""),
            "contact": cur.get("contact_form", ""),
            "committees": seats.get(bg, []),
            "career": career,
            "social": {k: sm[k] for k in ("twitter", "facebook", "youtube", "instagram") if sm.get(k)},
            "links": [l for l in [
                {"label": "Congress.gov", "url": f"https://www.congress.gov/member/{bg}"},
                {"label": "Votes · GovTrack", "url": f"https://www.govtrack.us/congress/members/{ids['govtrack']}"} if ids.get("govtrack") else None,
                {"label": "Money · OpenSecrets", "url": f"https://www.opensecrets.org/members-of-congress/summary?cid={ids['opensecrets']}"} if ids.get("opensecrets") else None,
                {"label": "Ballotpedia", "url": "https://ballotpedia.org/" + ids["ballotpedia"].replace(" ", "_")} if ids.get("ballotpedia") else None,
                {"label": "Wikipedia", "url": "https://en.wikipedia.org/wiki/" + ids["wikipedia"].replace(" ", "_")} if ids.get("wikipedia") else None,
            ] if l],
        })
    return out


# Open States doesn't publish legislatures for these; anywhere else, a failed
# fetch must fail the build rather than ship a state with no legislators.
NO_OPEN_STATES = {"AS", "GU", "MP", "VI"}

# Floors for a sane build. Congress is 535 + 6 delegates; state legislatures
# total ~7,400 seats. Well under either means an upstream broke, not that
# thousands of people left office — refuse to write rather than publish a gap.
MIN_FEDERAL, MIN_STATE = 500, 6500


def state_legislators(st):
    try:
        raw = get(OS.format(st.lower())).decode("utf-8")
    except Exception as e:
        if st in NO_OPEN_STATES:
            return []
        sys.exit(f"{st}: Open States fetch failed ({e}) — not writing a partial build")
    out = []
    for r in csv.DictReader(io.StringIO(raw)):
        ch = r["current_chamber"]
        d = r["current_district"]
        where = d if not d.isdigit() else f"District {d}"
        if ch == "upper" and st == "NE":
            chamber, role, body = "upper", "State Senator", "Nebraska Legislature"
        elif ch == "upper":
            chamber, role, body = "upper", "State Senator", f"{STATES[st]} State Senate"
        elif ch == "lower":
            house, member = LOWER.get(st, ("House of Representatives", "State Representative"))
            chamber, role, body = "lower", member, f"{STATES[st]} {house}"
        else:  # DC's council is its legislature
            chamber, role, body = "upper", "Councilmember", "Council of the District of Columbia"
        links = [u for u in (r["links"] or "").split(";") if u]
        sources = [u for u in (r["sources"] or "").split(";") if u]
        pick = lambda host: next((u for u in links + sources if host in u), None)
        out.append({
            "id": r["id"],
            "level": "state",
            "branch": "legislative",
            "chamber": chamber,
            "state": st,
            "district": d,
            "name": r["name"],
            "role": role,
            "seat": f"{body} · {where}",
            "party": party(r["current_party"]),
            "since": None,
            "term": "",
            "term_ends": "",
            "born": r["birth_date"],
            "photo": r["image"],
            "phone": r["capitol_voice"] or r["district_voice"],
            "office": r["capitol_address"] or r["district_address"],
            "email": r["email"],
            "website": links[0] if links else "",
            "contact": "",
            "bio": r["biography"],
            "committees": [],
            "career": [],
            "social": {k: r[k] for k in ("twitter", "facebook", "youtube", "instagram") if r.get(k)},
            "links": [l for l in [
                {"label": "Open States", "url": "https://openstates.org/person/" + r["id"].split("/")[-1] + "/"},
                {"label": "Ballotpedia", "url": pick("ballotpedia.org")} if pick("ballotpedia.org") else None,
                {"label": "Vote Smart", "url": pick("votesmart.org")} if pick("votesmart.org") else None,
                {"label": "Wikipedia", "url": pick("wikipedia.org")} if pick("wikipedia.org") else None,
            ] if l],
        })
    return out


# ---------------------------------------------------------------- Wikidata

def sparql(query):
    url = WDQS + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": "roofbeam.net build (hello@roofbeam.net)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        rows = json.load(r)["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in rows]


def qid(uri):
    return uri.rsplit("/", 1)[-1]


def commons(url):
    """A Wikidata P18 value is a Special:FilePath URL; ask Commons for a sized one."""
    return FILEPATH.format(urllib.parse.quote(urllib.parse.unquote(url.rsplit("/", 1)[-1]))) if url else ""


def federal_officers():
    """President, Vice President, the Cabinet and the Supreme Court."""
    rows = sparql(f"""
SELECT ?pos ?posLabel ?p ?pLabel ?start ?img ?dob ?article WHERE {{
  {{ VALUES ?pos {{ wd:{POTUS} wd:{VPOTUS} wd:{CHIEF_JUSTICE} wd:{ASSOC_JUSTICE} }} }}
  UNION {{ ?pos wdt:P361 wd:{US_CABINET} }}
  ?p p:P39 ?st . ?st ps:P39 ?pos ; pq:P580 ?start .
  ?p wdt:P31 wd:Q5 .
  FILTER NOT EXISTS {{ ?st pq:P582 ?end }}
  FILTER NOT EXISTS {{ ?p wdt:P570 ?died }}
  OPTIONAL {{ ?p wdt:P18 ?img }}
  OPTIONAL {{ ?p wdt:P569 ?dob }}
  OPTIONAL {{ ?article schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}""")
    # One row per (office, person): Wikidata can carry several images or birthdays.
    seen = {}
    for r in rows:
        seen.setdefault((r["pos"], r["p"]), r)
    by_pos = {}
    for r in seen.values():
        # Wikidata's "part of the Cabinet" also sweeps in the Postmaster
        # General, service secretaries and advisers, and which cabinet-level
        # posts count changes by administration. Keep the fixed, statutory
        # set: the heads of the 15 executive departments.
        if qid(r["pos"]) not in (POTUS, VPOTUS, CHIEF_JUSTICE, ASSOC_JUSTICE) and not (
                r["posLabel"] == "United States Attorney General"
                or (r["posLabel"].startswith("United States Secretary of")
                    and r["posLabel"] not in SERVICE_SECRETARIES)):
            continue
        by_pos.setdefault(qid(r["pos"]), []).append(r)
    holders = []
    for pos, rs in by_pos.items():
        rs.sort(key=lambda r: r["start"], reverse=True)
        # Associate justices share one office; every other office has one
        # holder, and an unclosed older term is Wikidata lag, not a co-holder.
        holders += rs if pos == ASSOC_JUSTICE else rs[:1]

    parties = {}
    ids = " ".join(f"wd:{qid(r['p'])}" for r in holders)
    for r in sparql(f"""
SELECT ?p ?partyLabel WHERE {{
  VALUES ?p {{ {ids} }}
  ?p p:P102 ?s . ?s ps:P102 ?party . FILTER NOT EXISTS {{ ?s pq:P582 ?e }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""):
        parties.setdefault(r["p"], r["partyLabel"])

    def rank(r):
        pos = qid(r["pos"])
        return ({POTUS: 0, VPOTUS: 1, CHIEF_JUSTICE: 3, ASSOC_JUSTICE: 4}.get(pos, 2), r["start"], r["posLabel"])

    out = []
    for r in sorted(holders, key=rank):
        pos = qid(r["pos"])
        court = pos in (CHIEF_JUSTICE, ASSOC_JUSTICE)
        title = r["posLabel"]
        if pos == ASSOC_JUSTICE:
            title = "Associate Justice of the Supreme Court"
        elif title.startswith("United States "):
            title = "U.S. " + title[len("United States "):]
        links = [{"label": "Wikidata", "url": r["p"]}]
        if r.get("article"):
            links.insert(0, {"label": "Wikipedia", "url": r["article"]})
        if court:
            links.insert(0, {"label": "Supreme Court", "url": "https://www.supremecourt.gov/about/biographies.aspx"})
        out.append({
            "id": qid(r["p"]),
            "level": "federal",
            "branch": "judicial" if court else "executive",
            "chamber": "court" if court else ("head" if pos in (POTUS, VPOTUS) else "cabinet"),
            "state": "US", "district": "",
            "name": r["pLabel"],
            "role": title,
            "seat": "Supreme Court of the United States" if court else "United States",
            # Justices are not partisan offices; showing a party there would be
            # an inference, and this page shows facts.
            "party": "" if court else party(parties.get(r["p"])),
            "since": int(r["start"][:4]),
            "since_label": "On the Court since" if court else "In office since",
            "term": "", "term_ends": "",
            "born": r.get("dob", "")[:10],
            "photo": commons(r.get("img", "")),
            "phone": "", "office": "", "website": "", "contact": "",
            "committees": [], "career": [], "social": {},
            "links": links,
        })
    heads = [o for o in out if o["chamber"] == "head"]
    cabinet = [o for o in out if o["chamber"] == "cabinet"]
    justices = [o for o in out if o["branch"] == "judicial"]
    # Vacancies happen (an acting secretary isn't recorded as the holder), so
    # allow a little slack; much more than that means Wikidata changed shape.
    if len(heads) != 2 or not 12 <= len(cabinet) <= 15 or not 7 <= len(justices) <= 9:
        sys.exit(f"Wikidata looks off: {len(heads)} President/VP, {len(cabinet)} department heads, "
                 f"{len(justices)} justices — not writing")
    return out


def state_high_courts():
    """One card per state: its highest court, linking to who sits there now."""
    rows = sparql(f"""
SELECT ?court ?courtLabel ?state ?stateLabel ?site ?article WHERE {{
  ?court wdt:P31 wd:{STATE_SUPREME_COURT} ; wdt:P1001 ?state .
  OPTIONAL {{ ?court wdt:P856 ?site }}
  OPTIONAL {{ ?article schema:about ?court ; schema:isPartOf <https://en.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}""")
    code = {v: k for k, v in STATES.items()}
    out = {}
    for r in sorted(rows, key=lambda r: r.get("site", "")):
        st = code.get(r["stateLabel"])
        if not st:
            continue
        c = out.setdefault(st, {
            "id": qid(r["court"]),
            "level": "state", "branch": "judicial", "chamber": "court",
            "state": st, "district": "",
            "name": r["courtLabel"],
            "role": "Your state's highest court",
            "seat": STATES[st],
            "party": "", "since": None, "term": "", "term_ends": "", "born": "",
            "photo": "", "phone": "", "office": "", "contact": "",
            "website": "", "committees": [], "career": [], "social": {},
            "links": [], "kind": "institution",
        })
        if r.get("site") and not c["website"]:
            c["website"] = r["site"]
        if r.get("article") and not any(l["label"] == "Wikipedia" for l in c["links"]):
            c["links"].append({"label": "Wikipedia", "url": r["article"]})
    for c in out.values():
        c["links"].insert(0, {"label": "Ballotpedia", "url": "https://ballotpedia.org/" + urllib.parse.quote(c["name"].replace(" ", "_"))})
    return out


# ------------------------------------------------- Open States: executives

EXEC_ORDER = ["governor", "lieutenant governor", "secretary of state", "attorney general",
              "treasurer", "comptroller", "controller", "auditor"]


def state_executives():
    raw = get(OS_PEOPLE)
    today = dt.date.today().isoformat()
    out = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for m in tar:
            parts = m.name.split("/")
            # people-main/data/<st>/executive/<file>.yml
            if len(parts) != 5 or parts[3] != "executive" or not m.name.endswith(".yml"):
                continue
            st = parts[2].upper()
            if st not in STATES:
                continue
            d = yaml.safe_load(tar.extractfile(m))
            # YAML turns bare dates into date objects; compare as ISO strings.
            for r in d.get("roles", []):
                for k in ("start_date", "end_date"):
                    if r.get(k):
                        r[k] = str(r[k])
            role = next((r for r in d.get("roles", [])
                         if (r.get("end_date") or "9999") >= today and (r.get("start_date") or "") <= today), None)
            if not role:
                continue
            kind = role["type"].replace("_", " ").lower()
            kind = {"lt governor": "lieutenant governor"}.get(kind, kind)
            office = (d.get("offices") or [{}])[0]
            ids = d.get("ids") or {}
            links = [l["url"] for l in d.get("links") or [] if l.get("url")]
            parties = [p["name"] for p in d.get("party") or [] if not p.get("end_date")]
            out.setdefault(st, []).append({
                "id": d["id"],
                "level": "state", "branch": "executive", "chamber": "exec",
                "state": st, "district": "",
                "name": d["name"],
                "role": " ".join(w if w in ("of", "the", "and") else w.capitalize() for w in kind.split()),
                "seat": STATES[st],
                "party": party(parties[0]) if parties else "",
                "since": int(role["start_date"][:4]) if role.get("start_date") else None,
                "term": "", "term_ends": (role.get("end_date") or "")[:4],
                "born": str(d.get("birth_date") or ""),
                "photo": d.get("image", ""),
                "phone": office.get("voice", ""),
                "office": (office.get("address") or "").replace(" ; ;", ",").replace(";", ","),
                "email": d.get("email", ""),
                "website": links[0] if links else "",
                "contact": "", "committees": [], "career": [],
                "social": {k: ids[k] for k in ("twitter", "facebook", "youtube", "instagram") if ids.get(k)},
                "links": [{"label": "Open States", "url": "https://openstates.org/person/" + d["id"].split("/")[-1] + "/"}],
                "order": EXEC_ORDER.index(kind) if kind in EXEC_ORDER else len(EXEC_ORDER),
            })
    return out


def main():
    us = federal_officers()
    print(f"federal executive + Supreme Court: {len(us)}")
    courts = state_high_courts()
    print(f"state high courts: {len(courts)}")
    execs = state_executives()
    print(f"state executives: {sum(map(len, execs.values()))} across {len(execs)} states")
    if len(courts) < 45 or len(execs) < 40:
        sys.exit("suspiciously few state courts or executives — not writing")
    fed = federal()
    print(f"federal: {len(fed)}")
    state = {st: state_legislators(st) for st in STATES}
    n_state = sum(map(len, state.values()))
    print(f"state: {n_state}")
    if len(fed) < MIN_FEDERAL or n_state < MIN_STATE:
        sys.exit(f"suspiciously small build (federal {len(fed)}, state {n_state}) — not writing")

    OUT.mkdir(exist_ok=True)
    (OUT / "US.json").write_text(json.dumps(us, separators=(",", ":"), ensure_ascii=False))
    index = []
    # Legislative, executive, judicial: the order the Constitution takes them in.
    order = {("federal", "senate"): 0, ("federal", "house"): 1,
             ("state", "upper"): 2, ("state", "lower"): 3,
             ("state", "exec"): 4, ("state", "court"): 5}
    for st, name in STATES.items():
        people = ([p for p in fed if p["state"] == st] + state[st]
                  + execs.get(st, []) + ([courts[st]] if st in courts else []))
        if not people:
            continue
        people.sort(key=lambda p: (order[(p["level"], p["chamber"])], p.pop("order", 0),
                                   int(p["district"]) if p["district"].isdigit() else 0,
                                   p["district"], p["name"]))
        (OUT / f"{st}.json").write_text(json.dumps(people, separators=(",", ":"), ensure_ascii=False))
        index.append({"code": st, "name": name, "count": len(people),
                      "federal": sum(p["level"] == "federal" for p in people)})
        print(f"  {st}: {len(people)}")
    (OUT / "states.json").write_text(json.dumps({
        "built": dt.date.today().isoformat(),
        "states": sorted(index, key=lambda s: s["name"]),
    }, indent=1))


if __name__ == "__main__":
    main()
