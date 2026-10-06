#!/usr/bin/env python3
"""Build the per-state decks for Meet Your Representatives.

    python3 toys/representatives/build/build_reps.py

Pulls two public datasets and writes one small JSON file per state into
toys/representatives/data/, plus data/states.json as the index:

  - Federal: unitedstates/congress-legislators (public domain) — current
    legislators, their term history, social handles, and committee seats.
  - State:   Open States bulk "people/current" CSVs (CC0) — current state
    legislators. Open States does not carry tenure in this file, so state
    cards say less than federal ones. That asymmetry is the data's, not a
    judgement, and the page says so.

Facts only. No scores, no ratings, no party colour-coding: the toy is
"learn more / skip", not "thumbs up / thumbs down".
"""

import csv
import datetime as dt
import io
import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "data"

CL = "https://unitedstates.github.io/congress-legislators"
OS = "https://data.openstates.org/people/current/{}.csv"
PHOTO = "https://unitedstates.github.io/images/congress/225x275/{}.jpg"

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

# What each state actually calls its lower chamber. Everyone else: "House".
LOWER = {
    "CA": "Assembly", "NV": "Assembly", "NY": "Assembly", "WI": "Assembly",
    "NJ": "General Assembly", "MD": "House of Delegates",
    "VA": "House of Delegates", "WV": "House of Delegates",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "roofbeam.net build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def party(p):
    return {"Democrat": "Democratic"}.get(p, p or "")


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
        if ch == "upper":
            chamber, role = "upper", "State Senator"
        elif ch == "lower":
            chamber, role = "lower", f"State {LOWER.get(st, 'House')} member" if st in LOWER else "State Representative"
        else:  # Nebraska's unicameral, DC council
            chamber, role = "upper", "Senator, Unicameral Legislature" if st == "NE" else "Councilmember"
        links = [u for u in (r["links"] or "").split(";") if u]
        sources = [u for u in (r["sources"] or "").split(";") if u]
        pick = lambda host: next((u for u in links + sources if host in u), None)
        d = r["current_district"]
        out.append({
            "id": r["id"],
            "level": "state",
            "chamber": chamber,
            "state": st,
            "district": d,
            "name": r["name"],
            "role": role,
            "seat": f"{STATES[st]} · " + (d if not d.isdigit() else f"District {d}"),
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


def main():
    fed = federal()
    print(f"federal: {len(fed)}")
    state = {st: state_legislators(st) for st in STATES}
    n_state = sum(map(len, state.values()))
    print(f"state: {n_state}")
    if len(fed) < MIN_FEDERAL or n_state < MIN_STATE:
        sys.exit(f"suspiciously small build (federal {len(fed)}, state {n_state}) — not writing")

    OUT.mkdir(exist_ok=True)
    index = []
    for st, name in STATES.items():
        people = [p for p in fed if p["state"] == st] + state[st]
        if not people:
            continue
        order = {("federal", "senate"): 0, ("federal", "house"): 1,
                 ("state", "upper"): 2, ("state", "lower"): 3}
        people.sort(key=lambda p: (order[(p["level"], p["chamber"])],
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
