# Changelog

## 1.2.0 (2026-11-11)
- Brighter map (blue sea, green land, lighter grid and rings); the old dark map is still available under
  Settings → Map. The map now fits the window: the world view fills the full width, the azimuthal view leaves room
  for the compass labels. Legend has its own background.
- Automatic update: QSO Map downloads the new version from GitHub, checks size and SHA-256, installs it
  silently and restarts. Settings: check now, install without asking. Each release has a small
  `QSOMap-Update-x.y.z.exe` next to the full setup.
- Survey button (www.pd3rah.nl/qsomap/enquete.php), asked once after the fifth start.
- Period selection: whole log, or one year, month or day (◀ ▶ and a drop-down list with the number of QSOs);
  map, table, statistics and timeline follow the chosen period.
- Fixed: Russia (and Fiji) were not filled on the world map because they cross the 180° meridian; they are now
  split at the date line. Night shading is lighter (darker sea, light shade over land).
- Internet access via Windows WinHTTP (the bundled Python has no OpenSSL), so the update check also works in
  the installed program.

## 1.1.0 (2026-11-09)
- Edit a wrong or missing locator per contact (✎ in the STATION panel or right-click in the table),
  optionally for all QSOs with the same call. Corrections are remembered per log file and included in
  Export → ADIF; the original log is not changed. "Restore original" undoes a correction.

## 1.0.0 (2026-11-09)
- First version: ADIF (.adi) on a world map, azimuthal (equidistant around your QTH) and flat world view.
- Distance and bearing (short and long path) per contact; ODX, statistics, distance distribution, per band.
- Position from LAT/LON, GRIDSQUARE or, as a fallback, the callsign prefix.
- Filters on band, mode and call; timeline that plays back your log in chronological order.
- Grey line (day/night) with the sun position; distance rings and compass rose.
- Export to ADIF with DISTANCE, to CSV, and the map to PostScript.
- Opens the CW Station logbook directly. Dutch and English, 6 colour themes.
