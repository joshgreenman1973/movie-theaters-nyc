# Cinema Treasures NYC theater dataset — methodology

## Source
All data extracted from Cinema Treasures (cinematreasures.org), a crowdsourced,
user-edited database of historic and current movie theaters. Each theater has a
stable numeric ID and detail page at `https://cinematreasures.org/theaters/{id}`,
captured per-row in `cinema_treasures_id` / `cinema_treasures_url`.

Extraction date: 2026-06-26.

## How theaters were enumerated
Cinema Treasures organizes theaters by country -> state -> city. NYC boroughs map
to "cities" as follows:

- Manhattan -> city slug `new-york`
- Brooklyn -> `brooklyn`
- Bronx -> `bronx`
- Staten Island -> `staten-island`
- Queens -> NOT a single slug. The bare `queens` slug redirects away. Queens
  theaters are filed under ~40 neighborhood "cities" (Astoria, Flushing, Jamaica,
  Long Island City, Ridgewood, etc.). We enumerated each neighborhood slug
  individually. Ambiguous slugs that also exist outside Queens (Ridgewood,
  Glendale, Sunnyside, Floral Park, Bellerose) were resolved by reading the
  actual city + state on each detail page (see Borough assignment).

For each city listing we requested `?status=all`, which returns theaters of every
status (Open, Showing Movies, Closed, Demolished, Renovating, Restoring), paging
through 30 results per page. We captured each theater's numeric ID from the listing
links, then fetched every detail page.

Listing totals reported by the site at extraction time:
Manhattan 498, Brooklyn 405, Bronx 125, Staten Island 42, Queens ~165 (summed
across neighborhoods).

## Fields and how each was extracted (per detail page)
- **name** — page `<h1>`.
- **street_address / city / state / zip** — hCard microformat classes on the page
  (`street-address`, `locality`, `region`, `postal-code`). These are structured,
  not free-text, so they are reliable when present.
- **latitude / longitude** — read from the map element's `data_latitude` /
  `data_longitude` HTML attributes. These are the coordinates the site uses to
  place the theater's map marker. Left blank when the attribute is absent or 0.
- **status** — read from the map element's `data_status` attribute and normalized
  to Open / Closed / Demolished / Renovating / Restoring. ("Showing Movies" is a
  sub-state of Open and is normalized to Open.)
- **screens / seats** — read from the structured stat links
  (`/screens/N`, `/seats/N`) shown in the overview box.
- **year_opened_guess / year_closed_guess** — Cinema Treasures does NOT expose
  structured open/close-year fields. These columns are a BEST-EFFORT regex pull
  from the free-text overview prose ("opened in 1927", "closed in 1986"). They are
  LOW CONFIDENCE: the prose often mentions multiple years (renovations, reopenings,
  name changes), so the captured year may be the wrong one. Treat as a hint to
  verify, not as ground truth. Blank when no year pattern was found.

## Borough assignment
Primary: the city name on the detail page (e.g. "Springfield Gardens" -> Queens).
Fallback: the listing the ID came from, used only when the detail-page city is
missing or doesn't map to a known NYC borough. The `borough_source` column records
which method was used (`detail_city` vs `listing`).

## Data-quality flags column
`data_quality_flags` is a semicolon-separated list flagging missing/low-confidence
fields per row: `no_coords`, `no_seats`, `no_screens`, `no_street_address`,
`no_year_opened`, `no_year_closed`, `no_borough`, `borough_from_listing_only`.

## Known limitations / reliability caveats
- **Crowdsourced source.** Seats, screens, addresses and especially years are
  user-entered and unverified. Some are wrong, outdated, or blank.
- **Years are unreliable** (see above) — they are extracted from prose, not fields.
- **Status reflects the site's current label**, which may lag reality (a theater
  marked Open may have since closed, etc.).
- **"Demolished" vs "Closed"** is the contributor's judgment; not independently
  verified.
- We did not fabricate any value. Missing source data is left blank.
- Coordinates are the site's marker position, occasionally approximate.

## Year enrichment (AI pass)
Because the raw regex-pulled years were demonstrably unreliable (e.g. the Roxy
showed "closed 2022" when it was demolished in 1960; many had opened-after-closed),
every theater's Cinema Treasures description was re-read and its years re-extracted
by an AI model (Claude), one page at a time, with instructions to:
- report the ORIGINAL opening year, not later renovations, reopenings, twinnings or
  name changes;
- report the year the theater CLOSED as a movie house (distinct from demolition);
- attach a confidence rating (high / medium / low) and a short verbatim quote from
  the page as evidence.

Per-theater results live in `enrich/years_slice_*.json` as
`{id, name, opened, closed, demolished, confidence, evidence}`. These AI-extracted
years OVERRIDE the raw regex guesses in the final dataset. Where the source gave only
a decade ("1950s"), the decade's first year is used and the row is marked lower
confidence. Where no year is stated, the field is left blank — not invented.

## Building the final dataset
`build_data.py` merges the raw pull with the enriched years to produce
`theaters.json`, applying these rules:
- A theater is placed on the animated timeline only if it has a known opening year
  AND (it is still open OR it has a known closing year). Theaters failing this test
  are counted as "undated" and omitted from the animation rather than shown as
  perpetually lit.
- The light goes out in the year the theater CLOSED. Demolition year is used only as
  a fallback when the closing year is unknown.
- Impossible orderings (gone-before-opened) are dropped and flagged low confidence.
- **Movie-era floor (1905).** Cinema Treasures records a venue's BUILDING opening year.
  Dedicated movie theaters did not exist in New York City before about 1905; the first
  projected film here was 1896 (Koster & Bial's Music Hall), shown within vaudeville
  programs, not in a movie theater. So the effective movie-theater opening used by the
  timeline is floored at 1905: 57 venues that opened earlier (as vaudeville or
  legitimate theaters) are shown entering at 1905, and their true building-opening year
  is kept in the `building_opened` field and surfaced in each detail card. Any venue
  that had already closed before 1905 never operated as a movie theater and is dropped
  from the timeline. This means the years 1905-1910 carry a cohort of older venues whose
  exact film-conversion year is not recorded — read that early stretch with that caveat.

## Manual corrections (sourced)
A few well-known repertory/arthouse houses were left undated by the crowdsourced source,
or recorded only under a later non-cinema identity, so they fell off the timeline. These
were corrected by hand from secondary sources and are listed in `MANUAL_OVERRIDES` in
`build_data.py`:
- **Bleecker Street Cinema** — opened 1960 (founded by Lionel Rogosin), closed Sept 6,
  1990. (Wikipedia; Village Preservation.)
- **Theatre 80 St. Marks** — revival film house from August 1971 into the mid-1990s
  (closing year taken as 1994; medium confidence). (Wikipedia; Village Preservation.)
- **Elgin Theater** (Chelsea) — showed films 1942-1978, then became the Joyce Theater
  (a dance venue) in 1982. Cinema Treasures filed it under "Joyce Theater" and marked it
  open; it is relabeled here and dated to its movie-house life, 1942-1978. (Wikipedia.)

## Active vs. repurposed (what counts as "still lit")
Cinema Treasures marks a venue "Open" when the building is in use — which includes grand
movie palaces that were restored as concert halls (Radio City, the Beacon, Loew's Kings,
United Palace, the Brooklyn Paramount, the St. George), former movie houses now running as
Broadway or Off-Broadway theaters (the Winter Garden, Palace, New Amsterdam and a dozen
others), churches, and arts centers (BRIC, Coney Island USA). None of these screen films to
the public today. So a venue is treated as a currently-active movie theater only if it
actually shows movies now — recognized by name (chains and named art houses) or an explicit
keep-list of public film venues (e.g. Film at Lincoln Center, Walter Reade, Spectacle, Japan
Society, Symphony Space's Thalia). 48 "open" venues were reclassified:
- Prominent palaces are dated to the year they stopped showing films (Radio City 1979,
  Brooklyn Paramount 1962, Loew's Kings 1977, United Palace 1969, Beacon 1974, St. George
  1977, Staten Island Paramount 1978) and go dark on the map at that year.
- Others that lack a known film-closing year are moved to "undated" rather than assigned a
  guessed date, so they leave the animation rather than sit falsely lit.
This is a judgment line; the keep-list and overrides live in `build_data.py` and can be
adjusted. The count of currently-active cinemas (62) is deliberately conservative.

## Final dataset summary (as built)
- 1,210 theaters placed on the map (of 1,235 pulled; 25 lacked coordinates).
- 1,036 have an opening year (86%); 891 have a closing year.
- 878 are on the animated timeline; 332 are undated and omitted from it. Of the 878,
  ~50 predate the movie era and are floored to 1905 (see above).
- 62 venues still screen films to the public and are lit at 2026.
- Shape of the story: the seat total peaks in the late 1930s — about 508 theaters and
  roughly 661,000 seats in 1938 — then declines to 62 active cinemas and 47,191 seats
  today: a 93% loss of movie seats, with 816 theaters gone dark.
- These figures track real history: U.S. movie attendance peaked in the late 1940s and
  fell sharply with suburbanization and television through the 1950s-1960s.

These aggregate figures are only as reliable as a crowdsourced source allows; treat
them as well-sourced estimates, not an official census. Individual year confidence is
exposed in each theater's detail card.

## Files
- `cinema_treasures_raw.csv` / `.json` — raw pull, one row per theater.
- `enrich/years_slice_*.json` — AI-extracted years with confidence + evidence quotes.
- `theaters.json` — the merged dataset the website loads.
- `../build_data.py` — the merge/cleaning script (re-runnable).
- `METHODOLOGY.md` — this file.
