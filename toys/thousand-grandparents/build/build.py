#!/usr/bin/env python3
"""Build the data pack for "A Thousand Grandparents".

Everything here is a historical constant, not a live feed, so the figures are
encoded as literals with their citation attached and the script's job is to
VALIDATE them (sums, shares, internal consistency) and emit descent.json.

Sources
  HSUS  Historical Statistics of the United States, Colonial Times to 1970
        (Bureau of the Census, 1975), Series A 6-8 (total population) and
        Series Z 1-19 (colonial population by race).
  C1860 Population of the United States in 1860: Compiled from the Original
        Returns of the Eighth Census (GPO, 1864).
  A1860 Agriculture of the United States in 1860 (GPO, 1864) -- slaveholder
        returns from the slave schedules.
  BRYC  Bryc, Durand, Macpherson, Reich & Mountain (2015), "The Genetic
        Ancestry of African Americans, Latinos, and European Americans across
        the United States," Am. J. Hum. Genet. 96(1):37-53.
  CHANG Chang (1999), "Recent common ancestors of all present-day
        individuals," Adv. Appl. Prob. 31:1002-1026.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "descent.json")

# ---------------------------------------------------------------- population
# (year, total, black, enslaved)  enslaved=None before the 1790 census; before
# emancipation in the North nearly the whole black population was enslaved, so
# the colonial rows carry black-as-enslaved and are flagged as such in meta.
POP = [
    (1610,      350,      0, None), (1620,     2302,     20, None),
    (1630,     4646,     60, None), (1640,    26634,    597, None),
    (1650,    50368,   1600, None), (1660,    75058,   2920, None),
    (1670,   111935,   4535, None), (1680,   151507,   6971, None),
    (1690,   210372,  16729, None), (1700,   250888,  27817, None),
    (1710,   331711,  44866, None), (1720,   466185,  68839, None),
    (1730,   629445,  91021, None), (1740,   905563, 150024, None),
    (1750,  1170760, 236420, None), (1760,  1593625, 325806, None),
    (1770,  2148076, 459822, None), (1780,  2780369, 575420, None),
    (1790,  3929214,  757208,  697681), (1800,  5308483, 1002037,  893602),
    (1810,  7239881, 1377808, 1191362), (1820,  9638453, 1771656, 1538022),
    (1830, 12866020, 2328642, 2009043), (1840, 17069453, 2873648, 2487355),
    (1850, 23191876, 3638808, 3204313), (1860, 31443321, 4441830, 3953760),
]

# ------------------------------------------------------- 1860, state by state
# enslaved / total from C1860; pct_fam = share of free families holding slaves,
# from the A1860 slaveholder returns (the standard published compilation).
# region: deep | upper | border | north
STATES = [
    # st, name,            total,   enslaved, free_black, pct_fam, region
    ("SC","South Carolina",  703708,  402406,   9914, 45.8, "deep"),
    ("MS","Mississippi",     791305,  436631,    773, 49.0, "deep"),
    ("GA","Georgia",        1057286,  462198,   3500, 37.0, "deep"),
    ("AL","Alabama",         964201,  435080,   2690, 35.1, "deep"),
    ("FL","Florida",         140424,   61745,    932, 34.0, "deep"),
    ("LA","Louisiana",       708002,  331726,  18647, 29.2, "deep"),
    ("TX","Texas",           604215,  182566,    355, 28.5, "deep"),
    ("NC","North Carolina",  992622,  331059,  30463, 27.7, "upper"),
    ("VA","Virginia",       1596318,  490865,  58042, 26.0, "upper"),
    ("TN","Tennessee",      1109801,  275719,   7300, 24.8, "upper"),
    ("AR","Arkansas",        435450,  111115,    144, 20.0, "upper"),
    ("KY","Kentucky",       1155684,  225483,  10684, 23.0, "border"),
    ("MO","Missouri",       1182012,  114931,   3572, 12.9, "border"),
    ("MD","Maryland",        687049,   87189,  83942, 12.0, "border"),
    ("DE","Delaware",        112216,    1798,  19829,  3.2, "border"),
    ("DC","Dist. of Columbia",75080,    3185,  11131,  4.0, "border"),
]

# Free-state aggregate, 1860 (C1860). New Jersey still returned 18 people held
# as "apprentices for life" -- the last legally enslaved people in the North.
NORTH_1860 = {"total": 18936579, "enslaved": 18, "free_black": 226152, "pct_fam": 0.05}

# ------------------------------------------------- gene flow across the line
# BRYC 2015, table 1 and figure 3. Defaults the toy ships with; exposed as a
# control so a visitor can see how much of the "both" number rests on them.
ADMIX = {
    "aa_mean_european": 0.240,       # mean European ancestry, African Americans
    "aa_share_any_european": 0.965,  # share w/ >=1% European ancestry
    "ea_share_any_african": 0.035,   # share of European Americans w/ >=1% African
    "ea_share_any_african_by_state": {  # highest-admixture states
        "SC": 0.130, "LA": 0.120, "GA": 0.085, "AL": 0.075,
        "MS": 0.070, "NC": 0.060, "VA": 0.055, "TN": 0.050,
        "AR": 0.045, "TX": 0.040, "FL": 0.040, "KY": 0.035,
        "MO": 0.030, "MD": 0.035, "DE": 0.030, "DC": 0.040,
    },
}

GEN_YEARS = 28  # mean generational interval; sensitivity noted in the methodology

def build():
    errs = []

    # --- validate the 1860 slave states against the published national totals
    st_enslaved = sum(s[3] for s in STATES)
    st_free_black = sum(s[4] for s in STATES)
    st_total = sum(s[2] for s in STATES)
    nat_total, nat_black, nat_enslaved = POP[-1][1], POP[-1][2], POP[-1][3]

    tot_enslaved = st_enslaved + NORTH_1860["enslaved"]
    if abs(tot_enslaved - nat_enslaved) > 2000:
        errs.append(f"enslaved: states {tot_enslaved:,} vs national {nat_enslaved:,}")

    tot_pop = st_total + NORTH_1860["total"]
    if abs(tot_pop - nat_total) / nat_total > 0.02:
        errs.append(f"population: states {tot_pop:,} vs national {nat_total:,}")

    tot_black = st_enslaved + st_free_black + NORTH_1860["enslaved"] + NORTH_1860["free_black"]
    if abs(tot_black - nat_black) / nat_black > 0.03:
        errs.append(f"black pop: states {tot_black:,} vs national {nat_black:,}")

    # --- every population row must be internally consistent
    for yr, tot, blk, ens in POP:
        if blk > tot: errs.append(f"{yr}: black {blk:,} > total {tot:,}")
        if ens is not None and ens > blk:
            errs.append(f"{yr}: enslaved {ens:,} > black {blk:,}")
    for a, b in zip(POP, POP[1:]):
        if b[1] <= a[1]: errs.append(f"population not increasing at {b[0]}")

    for s in STATES:
        if not 0 <= s[5] <= 100: errs.append(f"{s[0]}: pct_fam {s[5]} out of range")
        if s[3] + s[4] > s[2]: errs.append(f"{s[0]}: black pop exceeds total")

    if errs:
        print("VALIDATION FAILED", file=sys.stderr)
        for e in errs: print("  " + e, file=sys.stderr)
        sys.exit(1)

    # --- region aggregates, weighted by free families (proxied by free pop/5)
    regions = {}
    for key in ("deep", "upper", "border"):
        rs = [s for s in STATES if s[6] == key]
        w = [(s[2] - s[3] - s[4]) for s in rs]          # free white population
        pct = sum(x * s[5] for x, s in zip(w, rs)) / sum(w)
        ens = sum(s[3] for s in rs); tot = sum(s[2] for s in rs)
        fb = sum(s[4] for s in rs)
        regions[key] = {
            "pct_fam": round(pct, 2),
            "enslaved_share": round(ens / tot, 4),
            # of the region's BLACK population, the share held in slavery -- the
            # border states are the surprise here: Maryland's free black
            # population nearly equalled its enslaved one.
            "black_enslaved_share": round(ens / (ens + fb), 4),
            "total": tot, "enslaved": ens, "free_black": fb,
            "states": [s[0] for s in rs],
        }
    regions["north"] = {
        "pct_fam": NORTH_1860["pct_fam"],
        "enslaved_share": round(NORTH_1860["enslaved"] / NORTH_1860["total"], 6),
        "black_enslaved_share": round(
            NORTH_1860["enslaved"] / (NORTH_1860["enslaved"] + NORTH_1860["free_black"]), 6),
        "total": NORTH_1860["total"], "enslaved": NORTH_1860["enslaved"],
        "free_black": NORTH_1860["free_black"], "states": [],
    }
    # "the South" as a whole -- the 25.4% figure everyone quotes
    south = [s for s in STATES if s[6] in ("deep", "upper", "border")]
    w = [(s[2] - s[3] - s[4]) for s in south]
    s_ens, s_fb = sum(s[3] for s in south), sum(s[4] for s in south)
    regions["south_all"] = {
        "pct_fam": round(sum(x * s[5] for x, s in zip(w, south)) / sum(w), 2),
        "enslaved_share": round(s_ens / sum(s[2] for s in south), 4),
        "black_enslaved_share": round(s_ens / (s_ens + s_fb), 4),
        "total": sum(s[2] for s in south), "enslaved": s_ens, "free_black": s_fb,
        "states": [s[0] for s in south],
    }

    pack = {
        "meta": {
            "title": "A Thousand Grandparents",
            "generation_years": GEN_YEARS,
            "note_colonial_enslaved": (
                "Before the 1790 census the black population is reported without a "
                "free/enslaved split. Rows before 1790 treat the black population as "
                "enslaved, which slightly overstates it: the free black population "
                "was small but not zero throughout the colonial period."
            ),
            "sources": {
                "HSUS": "Historical Statistics of the United States, Colonial Times to 1970 (Census Bureau, 1975), Series A 6-8, Z 1-19.",
                "C1860": "Population of the United States in 1860: Eighth Census (GPO, 1864).",
                "A1860": "Agriculture of the United States in 1860 (GPO, 1864) - slave schedules.",
                "BRYC": "Bryc et al. (2015), Am. J. Hum. Genet. 96(1):37-53.",
                "CHANG": "Chang (1999), Adv. Appl. Prob. 31:1002-1026.",
            },
        },
        "population": [
            {"year": y, "total": t, "black": b, "enslaved": e} for y, t, b, e in POP
        ],
        "states1860": [
            {"st": s[0], "name": s[1], "total": s[2], "enslaved": s[3],
             "free_black": s[4], "pct_fam": s[5], "region": s[6]} for s in STATES
        ],
        "north1860": NORTH_1860,
        "regions": regions,
        "admixture": ADMIX,
        "checks": {
            "enslaved_1860": nat_enslaved,
            "enslaved_1860_from_states": tot_enslaved,
            "slaveholding_share_slave_states": regions["south_all"]["pct_fam"],
            "enslaved_share_us_1860": round(nat_enslaved / nat_total, 4),
        },
    }

    with open(OUT, "w") as f:
        json.dump(pack, f, separators=(",", ":"))
    print(f"validation ok  ->  {OUT}  ({os.path.getsize(OUT):,} b)")
    print(f"  1860 enslaved      {nat_enslaved:,} ({100*nat_enslaved/nat_total:.1f}% of {nat_total:,})")
    print(f"  slaveholding families, slave states  {regions['south_all']['pct_fam']}%")
    for k in ("deep", "upper", "border", "north"):
        print(f"    {k:7s} owners {regions[k]['pct_fam']:5.1f}%   enslaved {100*regions[k]['enslaved_share']:5.1f}% of all"
              f"   {100*regions[k]['black_enslaved_share']:5.1f}% of black pop")

if __name__ == "__main__":
    build()
