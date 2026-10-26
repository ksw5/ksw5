# iPhone Duo pickup notifications — Washington, NC 27889

This project checks [Duo Checker](https://duo-checker.on-forge.com/) every ~20 minutes via GitHub Actions and creates an assigned GitHub Issue when a newly available iPhone Duo color/storage combination appears at a monitored nearby Apple Store.

## Monitored Apple Stores
- Crabtree Valley Mall — Raleigh, NC
- Southpoint — Durham, NC
- Friendly Center — Greensboro, NC
- Lynnhaven Mall — Virginia Beach, VA
- Short Pump Town Center — Richmond, VA

These are a reviewed, approximate ~200-mile area store list, **not** a geospatial radius calculation. Edit `NEARBY_STORES` in `check.py` to change it.

## Verified live data format
On October 26, 2026, GitHub's Ubuntu runner fetched the actual server-rendered HTML: 269 `tr[data-store]` rows, eight `td[data-color][data-storage]` cells per store, and a `span.sq-available` with a `title` ending in `Available` only where pickup is offered. The parser uses these actual attributes rather than nearby page text.

A positive availability was observed remotely during validation (Michigan Avenue, Chicago and Lakeside Shopping Center, Louisiana), while all selected local stores were unavailable. The read-only GitHub run correctly reported zero local stock. Six unit tests covered positives, negatives, malformed HTML, and conflicting indicators. No notification issue was created in testing.

## Activate and use
1. Merge the PR into `main` to start scheduled runs. Scheduled jobs run only on the default branch.
2. In GitHub **Actions → iPhone Duo stock check → Run workflow**, trigger a manual check to confirm the first production run.
3. Install/sign into the GitHub mobile app and enable notifications for **Issues** in this repo. Email notifications also work if configured in GitHub; receipt has not been end-to-end tested.
4. When the bot creates an assigned issue, open the issue's Duo Checker store link and verify live availability with Apple before ordering or traveling.

## Alert behavior
- 20-minute cron (`7,27,47` UTC minutes every hour), GitHub may delay or skip scheduled runs under load.
- No alerts for unavailable items, other cities, unknown data, or mere webpage changes.
- One new issue for each newly available store/SKU. Existing issue remains open while pickup is available. After a verified sellout the issue closes; a later restock produces a new issue.
- If page schema becomes unrecognizable or fewer than 200 stores are present, fail with a logged error without modifying issues.
- Relies on third-party site data; does not reserve or buy phones.
