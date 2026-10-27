# T-Mobile iPhone Duo regional stock monitor

A **separate** GitHub Actions workflow checks public T-Mobile per-store **iPhone Duo** product pages about every 20 minutes at minute 12, 32 and 52. It opens and assigns a GitHub Issue when a monitored store page explicitly changes to or first reports **In stock**. It closes that issue when a subsequently readable product page clearly reports no confirmed stock.

## Limitations
- The store page only reports a **model-level** label. **Color, size and online pickup eligibility are not confirmed**. Verify your intended configuration at T-Mobile checkout or phone the store before traveling. The status may have been updated a few days ago; alerts include the page's date.
- T-Mobile's site has *High demand*, *In stock*, and redirect-to-general-store page states. Only `In stock` with the explicit confirmation message and update date no older than seven days triggers an alert. *High demand* does not.
- If the product URL redirects to the store homepage or changes unexpectedly, the checker records `unknown` and never fires a false stock alert. HTTP failures likewise do not cause issues to close.
- The list contains **16 candidate named stores** in an approximate regional area around Washington NC 27889 (Washington, Greenville, Williamston, New Bern, Kinston, Rocky Mount, Goldsboro, Raleigh, Durham, Greensboro, Jacksonville, Wilmington and Fayetteville). It is **not complete coverage of all T-Mobile locations within 200 miles** and not a geospatial search. Stores can be added to `SLUGS` in `check.py`.
- A positive page may be stale despite the seven-day cutoff, and GitHub cron runs can be delayed or occasionally skipped.
- This checks without logging in, buying anything, or interacting with checkout.

## Notifications
GitHub creates separate **T-Mobile** Issues tagged `tmobile-iphone-duo-stock`. Enable GitHub mobile app push notifications for assigned Issues, plus your repository notification preferences. Phone notification delivery depends on GitHub; it cannot be guaranteed or fully tested without your device.

## Validation
The read-only diagnostic fetched six public store pages using a GitHub Actions runner on October 26, 2026. Arlington Plaza (Greenville NC) and a remote New York control reported "In stock" (last updated Oct 23); Williamston and Durham reported "High demand"; Washington and New Bern product links redirected to the general store page. In the full integration test at 8:46 PM EDT on October 26, the **16 candidate pages** produced 2 in-stock pages (Greenville Arlington Plaza and Fayetteville Skibo Rd), 4 high-demand pages, and 10 redirects to general store homepages. Only six had directly verifiable stock flags, so current monitoring coverage is narrower than the 16 locations. This distinction is explicitly handled by the parser. Eight unit tests and read-only integration checks run on PR changes before notifications are activated.
