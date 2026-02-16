# Black Duck Heatmap Metrics Analyzer

A Python-based tool for analyzing Black Duck scan metrics from CSV files in zip archives. Generates interactive HTML dashboards with time series analysis, scan type evolution tracking, and year-based filtering.

## Quick Start

```bash
# 1. Install the package
pip install -e .

# 2. Run analysis on your heatmap data
bdmetrics "path/to/heatmap-data.zip"

# 3. Open the generated report in your browser
# Output: report_YYYYMMDD_HHMMSS.html
```

For project group filtering:
```bash
bdmetrics "data.zip" --project-group "Demo" \
  --bd-url "https://your-server.com" \
  --bd-token "your-api-token"
```

## Table of Contents

- [Prerequisites](#prerequisites)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Command-Line Examples](#command-line-examples)
  - [Multi-CSV File Support](#multi-csv-file-support)
  - [Choosing the Right Report Type](#choosing-the-right-report-type)
  - [Performance Optimization](#performance-optimization)
  - [Command-Line Options Reference](#command-line-options-reference)
  - [Using Project Group Filter](#using-project-group-filter)
- [CSV Data Format](#csv-data-format)
- [Report Features](#report-features)
- [How It Works](#how-it-works)
- [Output Files](#output-files)
- [Customization](#customization)
- [Browser Compatibility](#browser-compatibility)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Exporting Heatmap Data from Black Duck

Before using this tool, you need to export the heatmap data from your Black Duck server:

1. **Access Black Duck Administration**
   - Log in to your Black Duck server as an administrator
   - Navigate to **System → Log Files**

2. **Download Heatmap Logs**
   - In the Log Files section, locate the **Heatmap** logs
   - Select the time period you want to analyze
   - Click **Download** to export the data as a ZIP archive
   - The downloaded file will contain CSV files with scan metrics

3. **Use the Downloaded ZIP**
   - Save the downloaded ZIP file (e.g., `heatmap-data.zip`)
   - Use this ZIP file as input to the `bdmetrics` command

📖 **Detailed Instructions**: [Black Duck Documentation - Downloading Log Files](https://documentation.blackduck.com/bundle/bd-hub/page/Administration/LogFiles.html#DownloadingLogFiles)

## Features

- 📦 **Zip Archive Support**: Reads CSV files directly from zip archives
- � **Multi-CSV Support**: Handles multiple CSV files (different Black Duck instances) with aggregated view
- �📊 **Interactive Charts**: Plotly-powered visualizations with hover details
- 🎯 **Black Duck Specific**: Tailored for Black Duck scan heatmap data
- 📅 **Multi-level Filtering**: Filter by file, year, and project
- 🏢 **Project Group Filtering**: Filter by Black Duck project groups (includes nested sub-groups)
- 🔍 **Scan Type Analysis**: Track scan type distribution and evolution over time
- ✅ **Success/Failure Metrics**: Monitor scan success rates
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🚀 **Performance Optimized**: Configurable min-scans threshold and skip-detailed mode for large datasets
- 📑 **Flexible Report Types**: Choose between full interactive report or simplified static report

## Installation

### From Source

1. Clone or download this repository
2. Install the package:

```bash
# Install in development mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

### Using pip (once published to PyPI)

```bash
pip install blackduck-heatmap-metrics
```

## Usage

After installation, you can use the `bdmetrics` command from anywhere:

```bash
bdmetrics path/to/your/heatmap-data.zip
```

Or use it as a Python module:

```python
from blackduck_metrics import read_csv_from_zip, analyze_data, generate_chart_data, generate_html_report

# Read data
dataframes = read_csv_from_zip("path/to/heatmap-data.zip")

# Analyze
analysis = analyze_data(dataframes)
chart_data = generate_chart_data(dataframes)

# Generate report
generate_html_report(analysis, chart_data, "output_report.html")
```

### Command-Line Examples

```bash
# Basic usage - generates report with default settings
bdmetrics "C:\Users\Downloads\heatmap-data.zip"

# Specify output file
bdmetrics "path/to/data.zip" -o custom_report.html

# Set minimum scans threshold (default: 10)
# Only projects with 50+ scans will appear in trend charts
bdmetrics "path/to/data.zip" --min-scans 50

# Filter data from a specific year onwards (excludes older data)
bdmetrics "path/to/data.zip" --start-year 2020

# Filter by Black Duck project group (requires Black Duck connection)
# Includes all projects in the specified group and all nested sub-groups
bdmetrics "path/to/data.zip" --project-group "Demo"

# Filter by project group with credentials passed as arguments
bdmetrics "path/to/data.zip" --project-group "Demo" --bd-url "https://your-server.com" --bd-token "your-token"

# Skip detailed year+project combinations for faster processing and smaller files
# Recommended for large datasets (reduces file size by ~36%)
bdmetrics "path/to/data.zip" --skip-detailed

# Generate simplified report without interactive filters
# Creates a smaller file that loads faster (no dynamic filtering)
bdmetrics "path/to/data.zip" --simple

# Combine options for optimal performance with large datasets
bdmetrics "path/to/data.zip" --min-scans 100 --skip-detailed --start-year 2020 -o report.html

# Show version
bdmetrics --version

# Show help
bdmetrics --help
```

### Multi-CSV File Support

The tool automatically handles zip archives containing **multiple CSV files**, ideal for comparing different Black Duck SCA instances or environments.

**Use Case Examples:**
- Compare **Production vs. Staging vs. Development** Black Duck instances
- Analyze **Regional instances** (US, EU, APAC) in one report
- Track metrics across **different Black Duck servers** in your organization

**How it works:**

```bash
# Process a zip with multiple CSV files (different Black Duck instances)
bdmetrics "multi-instance-data.zip"

# The report will:
# 1. Show AGGREGATED statistics from all instances in the summary
# 2. Provide a FILE DROPDOWN to select specific instances
# 3. Dynamically update charts when you select an instance
```

**Example zip structure:**
```
multi-instance-data.zip
├── production-blackduck.csv      # 50,000 scans
├── staging-blackduck.csv          # 15,000 scans
└── development-blackduck.csv      # 8,000 scans
```

**Report behavior:**
- **Default view (All Files)**: Shows aggregated 73,000 total scans
- **File dropdown selection**: Choose "production-blackduck.csv" → Shows only 50,000 scans
- **Charts update**: All visualizations filter to the selected instance
- **Cross-instance comparison**: Switch between files to compare metrics

### Choosing the Right Report Type

**Use Full Report (default)** when you need:
- ✅ Interactive filtering by file, year, and project
- ✅ Ad-hoc exploration of specific projects
- ✅ Detailed drill-down analysis
- ✅ Dynamic chart updates based on selections
- 📊 Ideal for: Analysis, investigation, troubleshooting

**Use Simple Report (`--simple`)** when you need:
- ✅ Fastest page load times
- ✅ Smaller file size for sharing
- ✅ Static overview of all data
- ✅ No JavaScript complexity
- 📊 Ideal for: Reports, presentations, email attachments, archiving

**Example decision matrix:**
```bash
# Detailed analysis of specific teams → Full report
bdmetrics "data.zip" --project-group "Team A"

# Quick overview to share with management → Simple report
bdmetrics "data.zip" --simple

# Large dataset for detailed investigation → Full report with optimizations
bdmetrics "data.zip" --min-scans 100 --skip-detailed

# Large dataset for quick overview → Simple report with optimizations
bdmetrics "data.zip" --simple --min-scans 100 --skip-detailed --start-year 2024
```

### Performance Optimization

For large datasets with thousands of projects:

- Use `--min-scans` to filter out low-activity projects from trend charts (default: 10)
- Use `--skip-detailed` to skip year+project combination charts (saves ~36% file size)
- Use `--start-year` to exclude historical data before a specific year (e.g., `--start-year 2020`)
- Use `--project-group` to analyze only projects within a specific Black Duck project group
- Use `--simple` to generate a simplified report without interactive filters (smaller file size, faster loading)
- Example: Dataset with 37,706 projects → 7,261 projects (--min-scans 100) → 282 MB vs 456 MB baseline

### Command-Line Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `zip_file` | Required | - | Path to zip file containing CSV heatmap data |
| `-o, --output` | Optional | `report_<timestamp>.html` | Custom output filename |
| `--min-scans` | Integer | `10` | Minimum scans for project to appear in trend charts |
| `--skip-detailed` | Flag | `False` | Skip year+project charts (reduces file size ~36%) |
| `--simple` | Flag | `False` | Generate simplified report without interactive filters |
| `--start-year` | Integer | None | Filter data from this year onwards (e.g., `2020`) |
| `--project-group` | String | None | Filter by Black Duck project group (includes all nested sub-groups) |
| `--bd-url` | String | `$BD_URL` | Black Duck server URL |
| `--bd-token` | String | `$BD_API_TOKEN` | Black Duck API token |
| `-v, --version` | Flag | - | Show version and exit |
| `-h, --help` | Flag | - | Show help message and exit |

**Note:** `--bd-url` and `--bd-token` are only required when using `--project-group`.

### Using Project Group Filter

The `--project-group` option allows you to filter analysis to only include projects that are members of a specific Black Duck project group. This requires connecting to your Black Duck server.

**Important:** When you specify a project group, the tool will automatically include:
- ✅ All projects directly in the specified group
- ✅ All projects in any sub-project-groups (nested groups)
- ✅ All projects in sub-sub-project-groups (recursively traverses the entire hierarchy)

This means if you have a structure like:
```
Business Unit A
├── Team 1
│   ├── Project A
│   └── Project B
├── Team 2
│   ├── Subteam 2.1
│   │   └── Project C
│   └── Project D
└── Project E
```

Filtering by `--project-group "Business Unit A"` will include Projects A, B, C, D, and E.

**Getting a Black Duck API Token:**

1. Log in to your Black Duck server
2. Click on your username (top right) → **My Access Tokens**
3. Click **Create New Token**
4. Enter a name (e.g., "Heatmap Metrics Tool")
5. Set appropriate scope/permissions (read access to projects)
6. Click **Create**
7. Copy the token immediately (it won't be shown again)

**Setup Black Duck Connection:**

You can provide credentials in two ways:

**Option 1: Environment Variables (Recommended for automation)**

```bash
# On Windows (PowerShell)
$env:BD_URL = "https://your-blackduck-server.com"
$env:BD_API_TOKEN = "your-api-token-here"

# Or use username/password (API token is recommended)
$env:BD_URL = "https://your-blackduck-server.com"
$env:BD_USERNAME = "your-username"
$env:BD_PASSWORD = "your-password"

# On Linux/Mac
export BD_URL="https://your-blackduck-server.com"
export BD_API_TOKEN="your-api-token-here"
```

**Option 2: Command-Line Arguments (Recommended for one-time use)**

```bash
# Pass credentials directly via command-line
bdmetrics "path/to/data.zip" --project-group "Demo" \
  --bd-url "https://your-blackduck-server.com" \
  --bd-token "your-api-token-here"
```

**Example Usage:**

```bash
# Filter to only analyze projects in the "Business Unit A" group (using env vars)
bdmetrics "path/to/data.zip" --project-group "Business Unit A"

# Same, but with credentials as arguments
bdmetrics "path/to/data.zip" --project-group "Business Unit A" \
  --bd-url "https://your-server.com" --bd-token "your-token"

# Combine with other filters
bdmetrics "path/to/data.zip" --project-group "Demo" --start-year 2024 --min-scans 50

# Complete example: Project group + simplified report + optimizations
bdmetrics "heatmap-data.zip" \
  --project-group "Business Unit A" \
  --simple \
  --min-scans 100 \
  --skip-detailed \
  --start-year 2024 \
  --bd-url "https://blackduck.example.com" \
  --bd-token "your-token"
# Creates: report_YYYYMMDD_HHMMSS_Business_Unit_A.html (optimized simple report)
```

Running the `bdmetrics` command will:
1. Extract and read all CSV files from the zip archive
2. Analyze Black Duck scan metrics
3. Generate an interactive HTML report:
   - **By default**: Full report with all interactive filters (file, year, project): `report_YYYYMMDD_HHMMSS.html`
   - **With `--simple`**: Simplified report without filters (smaller, faster): `report_YYYYMMDD_HHMMSS.html`
   - **With `--project-group`**: Report includes project group name: `report_YYYYMMDD_HHMMSS_<group-name>.html`

## CSV Data Format

The tool expects CSV files with the following columns:
- `hour`: Timestamp of the scan
- `codeLocationId`: Unique identifier for code location
- `codeLocationName`: Name of the code location
- `versionName`: Version being scanned
- `projectName`: Name of the project
- `scanCount`: Number of scans
- `scanType`: Type of scan (e.g., SIGNATURE, BINARY_ANALYSIS)
- `totalScanSize`: Total size of the scan
- `maxScanSize`: Maximum scan size
- `state`: Scan state (COMPLETED, FAILED, etc.)
- `transitionReason`: Reason for state transition

### Multi-CSV File Support

If your zip archive contains **multiple CSV files** (e.g., from different Black Duck SCA instances):

- **Aggregated View**: The report shows combined statistics across all CSV files by default
- **File Selector**: In full reports, use the dropdown to view data from specific Black Duck instances
- **Instance Comparison**: Compare metrics across different Black Duck servers or environments

**Example use case:**
```
heatmap-data.zip
├── production-instance.csv     # Production Black Duck data
├── staging-instance.csv        # Staging Black Duck data
└── development-instance.csv    # Development Black Duck data
```

The report will:
- Display **aggregated totals** from all three instances in summary statistics
- Provide a **file dropdown** to filter charts by specific instance
- Enable **cross-instance analysis** and comparison

## Report Features

The generated HTML dashboard includes:

### Report Types

Each run generates **one report** based on your selection:
- **Full Report** (default): Interactive report with complete filtering capabilities (file, year, project)
  - Filename: `report_YYYYMMDD_HHMMSS.html` or `report_YYYYMMDD_HHMMSS_<project-group>.html`
- **Simple Report** (with `--simple` flag): Lightweight report without interactive filters
  - Filename: Same as full report
  - Faster loading, smaller file size, ideal for sharing

### Report Type Comparison

| Feature | Full Report | Simple Report (`--simple`) |
|---------|-------------|---------------------------|
| **File filter** | ✅ Dropdown (multi-instance support) | ❌ Not available |
| **Year filter** | ✅ Interactive dropdown | ❌ Not available |
| **Project search** | ✅ Type-ahead search | ❌ Not available |
| **Dynamic chart updates** | ✅ Real-time filtering | ❌ Static data |
| **Charts included** | ✅ All charts | ✅ All charts |
| **Summary statistics** | ✅ Aggregated + per-instance | ✅ Aggregated only |
| **File size** | Larger | Smaller |
| **Page load speed** | Slower | Faster |
| **Best for** | Analysis & investigation | Sharing & reporting |

### Summary Section

Displays **aggregated statistics** across all CSV files in the zip archive:

- **Total Files Processed**: Number of CSV files analyzed (e.g., different Black Duck instances)
- **Total Records**: Aggregated scan records from all files
- **Unique Projects**: Combined count of distinct projects across all instances
- **Total Scans**: Aggregated total number of scans
- **Successful Scans**: Combined number of completed scans
- **Failed Scans**: Combined number of failed scans
- **Success Rate**: Overall percentage of successful scans

**Note:** When multiple CSV files are present, summary statistics represent the **combined view** of all Black Duck instances. Use the file filter to view instance-specific metrics.

### Interactive Filters

**Full Report** includes:
- **File Selector**: Dropdown to filter by specific CSV file (Black Duck instance)
  - Shows "All Files" by default (aggregated view)
  - Lists each CSV file individually when multiple files are present
  - Dynamically updates all charts and statistics based on selection
  - Useful for comparing different Black Duck SCA instances or environments
- **Year Selector**: Filter all data and charts by year
- **Project Search**: Type-ahead project search with dynamic filtering
- **Clear Filters**: Reset all filters to show aggregated data across all files

**Simple Report** (generated with `--simple` flag):
- No interactive filters
- Static view of all data
- Smaller file size and faster page load

### Charts and Visualizations

1. **Scan Activity Over Time**
   - Line chart showing number of scans over time
   - Total scan size trends
   - Filters by year, project, and file

2. **Top Projects by Scan Count**
   - Horizontal bar chart of top 20 projects
   - Updates based on filter selection

3. **Scan Type Distribution**
   - Pie chart showing breakdown of scan types
   - Updates based on year/project selection

4. **Scan Type Evolution Over Time**
   - Multi-line time series chart
   - Interactive checkbox selection for scan types
   - Track how different scan types have evolved
   - Smart error messages when data unavailable (shows min-scans threshold)
   - Automatically updates when filters change

### Smart Error Messages

The tool provides context-aware messages when data is unavailable:
- "No trend data for this project (project has less than X scans)" - when project doesn't meet min-scans threshold
- "Year+Project combination data not available" - when --skip-detailed flag was used

### Black Duck Overview
- Scan type breakdown with counts
- State distribution
- Filterable statistics

## Requirements

- Python 3.7+
- pandas >= 2.0.0
- jinja2 >= 3.1.0
- plotly >= 5.18.0

## Project Structure

```
blackduck_heatmap_metrics/
├── blackduck_metrics/
│   ├── __init__.py              # Package initialization
│   ├── analyzer.py              # Core data analysis and report generation
│   ├── blackduck_connector.py   # Black Duck SCA connection handler
│   ├── cli.py                   # Command-line interface
│   └── templates/
│       ├── template.html        # Full report template (interactive filters)
│       └── template_simple.html # Simple report template (no filters)
├── setup.py                     # Package installation script
├── pyproject.toml               # Project metadata
├── requirements.txt             # Python dependencies
├── MANIFEST.in                  # Package manifest
└── README.md                    # This file
```

## How It Works

1. **Data Extraction**: Reads all CSV files from zip archive using pandas
   - Supports single or multiple CSV files (e.g., different Black Duck instances)
   - Each CSV file is processed and tracked separately
2. **Project Filtering** (optional): Connects to Black Duck to filter projects by project group
3. **Time-based Analysis**: Parses timestamps and groups data by year and project
4. **Aggregation**: Calculates statistics per file, year, project, and year+project combinations
   - Generates both aggregated (all files) and individual file statistics
   - Enables cross-instance comparison when multiple CSV files are present
5. **Chart Generation**: Prepares optimized data structures for Plotly visualizations
   - Applies min-scans threshold to filter low-activity projects
   - Optionally skips year+project combinations for performance
   - Reduces data sampling for large datasets (time series: 200 points, scan type evolution: 100 points)
6. **Template Rendering**: Jinja2 combines data with selected template (full or simple)
7. **Output**: Generates a timestamped HTML file with embedded charts and interactive file selector (when multiple CSVs)

## Customization

### Template Styling
Edit templates in `blackduck_metrics/templates/`:
- `template.html` - Full report with interactive filters
- `template_simple.html` - Simple report without filters
- Customize: Color scheme (blue gradient), chart types, layouts, summary cards, fonts

### Data Analysis
Modify `blackduck_metrics/analyzer.py` to:
- Add new aggregations
- Include additional metrics
- Change chart data calculations
- Adjust min-scans thresholds
- Modify data sampling rates
- Adjust filtering logic

## Output Files

Each run generates **one report** with a timestamp-based filename:

### Default Filename Format
- Basic: `report_YYYYMMDD_HHMMSS.html`
- With project group: `report_YYYYMMDD_HHMMSS_<sanitized-group-name>.html`
- Custom (with `-o`): Your specified filename

### Examples
```bash
# Default full report
bdmetrics "data.zip"
# Output: report_20260216_143015.html

# Simple report
bdmetrics "data.zip" --simple
# Output: report_20260216_143015.html

# With project group
bdmetrics "data.zip" --project-group "Business Unit A"
# Output: report_20260216_143015_Business_Unit_A.html

# With project group and simple
bdmetrics "data.zip" --project-group "Demo" --simple
# Output: report_20260216_143015_Demo.html

# Custom filename
bdmetrics "data.zip" -o my_report.html
# Output: my_report.html
```

### Report Characteristics
All generated reports are:
- Standalone HTML files (no external dependencies except Plotly CDN)
- Self-contained with embedded data and charts
- Shareable - can be opened directly in any modern browser
- Single file per execution (either full or simple, based on flags)

## Browser Compatibility

The generated reports work in all modern browsers:
- Chrome/Edge (recommended)
- Firefox
- Safari
- Opera

Requires JavaScript enabled for interactive features.

## Troubleshooting

**No charts showing**
- Check browser console (F12) for JavaScript errors
- Ensure Plotly CDN is accessible
- Verify CSV data has the expected columns

**Charts show "No trend data for this project (project has less than X scans)"**
- This is normal for projects with few scans
- Adjust `--min-scans` threshold if needed (default: 10)
- In full reports, click "Clear Filters" to see all data
- Simple reports show all data without filtering

**Charts not updating after filter selection**
- Ensure JavaScript is enabled
- Try refreshing the page
- Check browser console for errors

**"Year+Project combination data not available" message**
- Report was generated with `--skip-detailed` flag
- Regenerate without this flag for full year+project filtering
- This is normal for optimized reports

**Report file too large**
- Use `--simple` to generate a report without interactive filters (significantly smaller)
- Use `--min-scans 50` or higher to reduce projects in charts
- Use `--skip-detailed` to skip year+project combinations (~36% size reduction)
- Use `--start-year` to exclude historical data
- Example: 456 MB → 282 MB with --min-scans 100 --skip-detailed

**Filters not available or working**
- If using `--simple` flag, filters are not included by design (use default mode for filters)
- In full reports, ensure JavaScript is enabled
- Ensure `hour` column contains valid timestamps
- Check that data spans multiple years for year filtering

**Charts show "No data available"**
- Verify CSV files contain the required columns
- Check for empty or malformed data
- Ensure project has sufficient scans (check min-scans threshold)

## License

MIT License
