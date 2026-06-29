# When the lights went out

An animated map of a century of New York City movie theaters — every house that
opened and closed from 1900 to today. Each theater is a light sized by its seat count.
Press play and the city's movie seats rise to a peak around 1940 of roughly 665,000 and
fall to about 106,000 now; closed theaters stay marked on the map where they once stood.

- **Left rail** — theaters currently showing, in order of opening.
- **Right rail** — theaters gone dark, in the year their lights went out.
- Toggle the size metric between seats, screens and theater count; hover or click any
  light for its name, dates and details.

## Data
Theaters, locations, seat counts and statuses come from the crowdsourced
[Cinema Treasures](https://cinematreasures.org) database. Opening and closing years
were AI-extracted from each theater's written description with a confidence rating and
a supporting quote, because the source exposes no structured year fields. Full sourcing,
assumptions, limitations and the final dataset summary are in
[`data/METHODOLOGY.md`](data/METHODOLOGY.md). Nothing here is an official census — treat
the numbers as well-sourced estimates.

## How it's built
Static site: `index.html` + `app.js` (Leaflet + a custom canvas glow layer) + `styles.css`.
`build_data.py` merges the raw pull with the enriched years into `data/theaters.json`.
