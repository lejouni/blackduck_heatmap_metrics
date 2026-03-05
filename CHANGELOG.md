# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.17] - 2026-03-05

### Added
- **Capacity Usage Monitoring** — new `--capacity-sph` and `--sph-warning-pct` CLI options add a dedicated
  *Capacity Usage – Scans Per Hour (SPH)* section to both report types
  - `--capacity-sph <N>`: set your hosted environment's SPH ceiling (e.g. `--capacity-sph 1500`)
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
  - The section is hidden automatically when `--capacity-sph` is not provided — zero additional
    report size impact when not in use

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

[0.1.16]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.16
[0.1.15]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.15
[0.1.14]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.14
[0.1.13]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.13
[0.1.11]: https://github.com/lejouni/blackduck_heatmap_metrics/releases/tag/v0.1.11
