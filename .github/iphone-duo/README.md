# iPhone Duo stock checker — ZIP 27889

Runs every ~20 minutes using GitHub Actions, subject to GitHub queue delays. Watches the public third-party [Duo Checker](https://duo-checker.on-forge.com/) website. Reports new matches via a GitHub issue (and closes it if inventory disappears). Enable GitHub app notifications for issues in this repository and watch the repository to receive alerts.

**Important:** Site markup / its machine-readable feed could not be inspected from this environment, so this is a conservative, fail-closed prototype. If parsing fails, it deliberately DOES NOT create a stock alert; inspect Actions logs to validate the live HTML before trusting it. The checker only detects stock if the page actually includes explicit item, store, and available-stock text. It never treats an HTTP 200 or any website change as stock.

Selected candidate stores are Apple retail stores around Washington, NC. Review `NEARBY_STORES` in `check.py` and adjust after confirming the geographic range; this is an inclusion list, not an actual distance calculation. The page may not expose this text server-side, in which case adapt the parser to the verified /agents feed.

### Activate
1. Merge this PR (GitHub scheduled workflows only run from the default branch).
2. Open **Actions → iPhone Duo stock check → Run workflow**, then examine the run log, especially `extract` diagnostics.
3. In **Settings → Notifications** and on your phone, enable GitHub issue notifications for this repository. If needed watch repo (Custom → Issues).
4. If the log shows the page does not expose store-level stock, do not rely on these alerts until the scraper is updated.

A new issue is created when a previously missing in-stock match appears; it is assigned to the repository owner. The issue is closed once the matching stock disappears and can reopen as a new issue next time. A page failure does not change alert status. This does not reserve or purchase a device.
