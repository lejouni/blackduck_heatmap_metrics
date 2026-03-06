# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.21] - 2026-03-06

### Added
- **New `--project-scans-report` flag** — generates a dedicated project scan counts report instead of the standard heatmap analysis
  - **Aggregated view**: When viewing "All Scan Types" (default), report shows one row per project with total scans across all scan types and the entire time range
  - **Per-scan-type view**: When selecting a specific scan type from the dropdown, report shows daily breakdown for that scan type
  - **Interactive filtering**: Filter by project name (text search), scan type (dropdown), and date range (start/end date pickers)
  - **Sortable columns**: Click any column header to sort (Project Name, Scan Type, Scan Count)
  - **Pagination**: Handle large datasets with configurable page sizes (10/20/30/50/100 rows per page)
  - **CSV export**: Export filtered data with detailed breakdown by scan type (even when viewing aggregated "All Scan Types")
  - **Fixed-width columns**: Long project names wrap to multiple lines, preventing column width changes
  - **Progress indicators**: Shows progress bars during data processing for transparency
  - **Year filtering support**: Respects `--start-year` and `--end-year` arguments to limit data scope
  - **Compact output**: Dramatically reduces file size compared to full heatmap report
  - **Date range tracking**: Automatically calculates and displays the date range of the filtered data

### Use Cases
- Generate summary reports of total scan activity per project across a time period
- Export scan counts to CSV for further analysis in Excel or other tools
- Share lightweight scan metrics without the full heatmap visualization overhead
- Monitor which projects are being scanned and how frequently
- Compare scan activity across different scan types (SIGNATURE, SCA_SCAN, etc.)

### Usage Examples
```bash
# Generate project scans report for 2026
bdmetrics "data.zip" --project-scans-report --start-year 2026 --end-year 2026

# With project group filter and no project limit
bdmetrics "data.zip" --project-scans-report --project-group "Demo" --max-projects 0

# Combine with compression for smaller files
bdmetrics "data.zip" --project-scans-report --compress --start-year 2025
```

## [0.1.20] - 2026-03-05

### Changed
- **Minimum Python version raised to 3.8** — Python 3.6 and 3.7 are no longer supported.
  `pandas >= 2.0.0` (a required dependency) dropped Python 3.7 support, making 3.8 the
  accurate minimum. Users on Python 3.6/3.7 will now receive a clear pip error instead
  of the cryptic `"from versions: none"` message.
- **Classifiers updated** — removed Python 3.7 classifier, added Python 3.12 and 3.13.

### Fixed
- **`.pkgtest` venv directory added to `.gitignore`** — the release-script temporary test
  venv was not gitignored, causing it to be committed and then failing to recreate on
  other machines (Windows locks `python.exe` in an existing venv, leaving it without
  `pip.exe` or activation scripts). Other users would then get
  `"Defaulting to user installation because normal site-packages is not writeable"` and
  a failed install.

## [0.1.19] - 2026-03-05

### Fixed
- **Package installation failed with "No matching distribution found"** — `pyproject.toml`
  dependency minimums were accidentally set to the developer's locally installed versions
  (`pandas>=3.0.1`, `plotly>=6.6.0`, `blackduck>=1.1.3`, etc.), which do not exist on PyPI
  for most users. Reverted to the same conservative lower bounds used in `setup.py`:
  - `pandas>=2.0.0` (was `>=3.0.1`)
  - `jinja2>=3.1.0` (was `>=3.1.6`)
  - `plotly>=5.18.0` (was `>=6.6.0`)
  - `tqdm>=4.65.0` (was `>=4.67.3`)
  - `blackduck>=1.0.0` (was `>=1.1.3`)
  - `requests>=2.31.0` (was `>=2.32.5`)

## [0.1.18] - 2026-03-05

### Added
- **Info icons on all metric cards and section headings** — every summary card and chart section
  heading now has a small circular `ⓘ` icon that shows a descriptive tooltip on hover,
  explaining what the metric or chart illustrates
  - Summary cards: Total Files, Total Records, Unique Projects, Total Scans, Successful Scans,
    Failed Scans, Success Rate, Busiest Hours, Quietest Hours
  - SPH cards (JS-rendered): Peak SPH, Hours Over Capacity, Hours in Warning
  - Section headings: Black Duck Scan Overview, Scan Types Breakdown, Top Projects,
    Top Projects by Time Block, Time Series Trends, Scan Type Evolution Over Time,
    Capacity Usage – SPH
  - Implemented via a lightweight `.info-icon` CSS class (no external dependencies)

### Changed
- **`--capacity-sph` now defaults to `120`** instead of being disabled — the Capacity Usage SPH
  section is now always visible in every report; pass `--capacity-sph <N>` to override with
  your actual hosted environment ceiling

## [0.1.17] - 2026-03-05

### Added
- **Capacity Usage Monitoring** — new `--capacity-sph` and `--sph-warning-pct` CLI options add a dedicated
  *Capacity Usage – Scans Per Hour (SPH)* section to both report types
  - `--capacity-sph <N>`: set your hosted environment's SPH ceiling (default: `120`; e.g. `--capacity-sph 1500`)
  - `--sph-warning-pct <N>`: percentage of the ceiling that triggers a warning alarm (default: `80`;
    pass `100` to disable warning zone and track only over-capacity hours)
  - When enabled the report adds:
    - **Peak SPH** card showing the highest observed SPH value and its % of capacity
    - **Hours Over Capacity** card — count of hours where SPH ≥ capacity ceiling
    - **Hours in Warning** card — count of hours that approach the ceiling; automatically
      hidden when `--sph-warning-pct 100` (empty warning zone edge-case)
    - **Scans Per Hour Over Time** Plotly chart with colour-coded markers
      (red = over capacity, amber = warning, blue = normal) and dashed reference lines
    - **Over Capacity & Warning Hours** drill-down table listing the top contributing
      projects per flagged hour, sorted by SPH descending
  - SPH is calculated as `scanCount.sum()` per hour bucket (not row count)
- **Snippet % column in Over Capacity & Warning Hours table** — each flagged hour row now shows
  the percentage of that hour's scans that are SNIPPET scan type
  - Colour-coded: 🔴 red ≥ 50%, 🟡 amber ≥ 25%, 🟢 green < 25%
  - Displays `—` when `scanType` column is absent from the data

### Fixed
- **Time Series "Number of Scans Over Time" used row count instead of `scanCount`** — the
  `generate_time_series_for_data()` function was calling `groupby('hour').size()` (CSV row count)
  instead of `groupby('hour')['scanCount'].sum()`, causing the chart to under-count scans when
  multiple code locations share an hour bucket with `scanCount > 1`; fallback to `.size()` is
  retained when the `scanCount` column is absent
- **Scan Type Evolution used row count instead of `scanCount`** — same fix applied to
  `generate_scan_type_evolution()` so per-scan-type counts now correctly reflect
  `scanCount.sum()` per hour per type

## [0.1.16] - 2026-03-04

### Added
- `--max-projects` CLI option to control the cap on projects included in trend charts
  - Default: `1000` (preserves previous behaviour)
  - Pass `0` to include all qualifying projects with no limit
  - Example: `bdmetrics data.zip --max-projects 0`
- `--end-year` CLI option to exclude data after a given year
  - Combine with `--start-year` to analyse a specific year range
  - Example: `bdmetrics data.zip --start-year 2022 --end-year 2024`

### Fixed
- **Scan count discrepancy between project charts** — "Top Projects by Scan Count" and all
  interactive project ranking views (time block, date, scan type) now use the same metric:
  the sum of the `scanCount` column per project. Previously the initial bar chart used
  `scanCount.sum` while every post-interaction update used a row count (`.size()`), causing
  different numbers to appear for the same project depending on which UI element was last
  interacted with.
- **Spurious "Generating simple report data (all years)" pass** when `--simple` was not
  specified alongside `--start-year` / `--end-year`. The extra `analyze_data` call is now
  gated on both `--simple` and a year filter being active.
- **Year filter not applied during chart-project selection** in `generate_chart_data`.
  Projects were previously selected from the full unfiltered dataset even when `--start-year`
  or `--end-year` was provided; the upfront per-file year filter now runs before any project
  enumeration so only years within the requested range are considered.

## [0.1.15] - 2026-03-03

### Added
- `--compress` flag to gzip-compress HTML output files as `.html.gz`
  - Browsers open `.html.gz` files natively (Chrome, Firefox, Edge)
  - Significantly reduces file size for large reports
  - Original `.html` file is replaced by the compressed `.html.gz` file
  - Example: `bdmetrics data.zip --compress` produces `report_YYYYMMDD_HHMMSS.html.gz`

### Fixed
- **Total Files** card not updating when selecting a single CSV file from the dropdown
  - Per-file statistics now correctly include `total_files: 1`
  - Previously showed blank/undefined instead of `1` when a specific file was selected

## [0.1.14] - 2026-02-20

### Changed
- `-o, --output` parameter behavior changed
  - Now accepts a folder path instead of a file path
  - Automatically generates filename with timestamp and optional project group suffix
  - Creates folder structure if it doesn't exist (including nested directories)
  - Pattern: `-o reports_multi` creates `reports_multi/report_YYYYMMDD_HHMMSS.html`
  - With project group: `reports_multi/report_YYYYMMDD_HHMMSS_<group-name>.html`

## [0.1.13] - 2026-02-16

### Added
- Black Duck SCA integration via `blackduck_connector.py` module
  - Connection using API tokens (recommended) or username/password
  - `BlackDuckConnector` class for handling Black Duck API operations
- Project group filtering feature (`--project-group` flag)
  - Recursive traversal of sub-project-groups (includes nested groups)
  - Filter analysis to specific Black Duck project groups
  - Support for `--bd-url` and `--bd-token` CLI arguments
  - Environment variable support (`BD_URL`, `BD_API_TOKEN`, `BD_USERNAME`, `BD_PASSWORD`)
- Simple report generation mode (`--simple` flag)
  - Generates lightweight report without interactive filters
  - Smaller file size and faster page load
  - Ideal for sharing and presentations
- Project group name display in reports
  - Shows in report header when `--project-group` is used
  - Included in output filename (sanitized for filesystem compatibility)
- Templates package initialization (`blackduck_metrics/templates/__init__.py`)

### Changed
- Report generation now conditional based on `--simple` flag
  - Default: Full interactive report with filters
  - With `--simple`: Simplified static report only
  - Only one report generated per execution (not two)
- Output filename format when using project groups
  - Pattern: `report_YYYYMMDD_HHMMSS_<sanitized-group-name>.html`
  - Special characters and spaces replaced with underscores
- License configuration modernized
  - `pyproject.toml`: Changed to SPDX format (`license = "MIT"`)
  - `setup.py`: Added `license="MIT"` field, removed deprecated classifier
  - Removed `License :: OSI Approved :: MIT License` from classifiers
- Version management improved
  - `setup.py` now reads version from `__init__.py` automatically
  - Single source of truth for version number
- Build system simplified
  - Removed unused `setuptools_scm` dependency from `pyproject.toml`

### Fixed
- Missing dependencies in package configuration
  - Added `requests>=2.31.0` to all dependency files
  - Added `blackduck>=1.0.0` to `pyproject.toml` and `setup.py`
  - Added `tqdm>=4.65.0` to `setup.py`
  - Synchronized `requirements.txt`, `pyproject.toml`, and `setup.py`
- Package discovery warning for templates directory
  - Created `__init__.py` in `blackduck_metrics/templates/`
  - Templates now properly recognized as Python package

### Documentation
- Comprehensive README.md updates
  - Added project group filtering documentation
  - Added simple report mode documentation
  - Added multi-CSV file support documentation
  - Added recursive sub-group behavior documentation
  - Added Black Duck API token setup instructions
  - Added report type comparison table
  - Added performance optimization guidelines
  - Fixed encoding issues (replaced � with proper emoji icons)
  - Enhanced command-line examples section
  - Improved troubleshooting section

## [0.1.11] - Previous Release

### Features
- Basic heatmap metrics analysis
- Interactive HTML report generation
- Multi-CSV file support
- Year and project filtering
- Scan type analysis
- Success/failure metrics
- Performance optimizations (`--min-scans`, `--skip-detailed`, `--start-year`)
- Plotly-powered interactive visualizations

---

## Release Notes Template

For future releases, use this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing functionality

### Deprecated
- Features that will be removed in future versions

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes
```

---

[0.1.19]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.19
[0.1.18]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.18
[0.1.17]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.17
[0.1.16]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.16
[0.1.15]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.15
[0.1.14]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.14
[0.1.13]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.13
[0.1.11]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.11
