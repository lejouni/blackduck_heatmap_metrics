# Black Duck Heatmap Metrics Analyzer

A Python-based tool for analyzing Black Duck scan metrics from CSV files in zip archives. Generates interactive HTML dashboards with time series analysis, scan type evolution tracking, and year-based filtering.

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
- 📊 **Interactive Charts**: Plotly-powered visualizations with hover details
- 🎯 **Black Duck Specific**: Tailored for Black Duck scan heatmap data
- 📅 **Multi-level Filtering**: Filter by file, year, and project
- 🔍 **Scan Type Analysis**: Track scan type distribution and evolution over time
- ✅ **Success/Failure Metrics**: Monitor scan success rates
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🚀 **Performance Optimized**: Configurable min-scans threshold and skip-detailed mode for large datasets
- 📑 **Dual Report Generation**: Creates both full (with filters) and simplified (year-only) reports

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
bdmetrics "C:\Users\JouniLehto\Downloads\heatmap-data.zip"

# Specify output file
bdmetrics "path/to/data.zip" -o custom_report.html

# Set minimum scans threshold (default: 10)
# Only projects with 50+ scans will appear in trend charts
bdmetrics "path/to/data.zip" --min-scans 50

# Skip detailed year+project combinations for faster processing and smaller files
# Recommended for large datasets (reduces file size by ~36%)
bdmetrics "path/to/data.zip" --skip-detailed

# Combine options for optimal performance with large datasets
bdmetrics "path/to/data.zip" --min-scans 100 --skip-detailed -o report.html

# Show version
bdmetrics --version

# Show help
bdmetrics --help
```

### Performance Optimization

For large datasets with thousands of projects:

- Use `--min-scans` to filter out low-activity projects from trend charts (default: 10)
- Use `--skip-detailed` to skip year+project combination charts (saves ~36% file size)
- Example: Dataset with 37,706 projects → 7,261 projects (--min-scans 100) → 282 MB vs 456 MB baseline

### Legacy Usage (if using main.py directly)

```bash
python main.py "path/to/your/heatmap-data.zip"
```

### Example

```bash
python main.py "heatmap-data.zip"
```

This will:
1. Extract and read all CSV files from the zip archive
2. Analyze Black Duck scan metrics
3. Generate an interactive HTML report as `report_YYYYMMDD_HHMMSS.html`

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

## Report Features

The generated HTML dashboard includes:

### Dual Report Generation

Each run generates **two reports**:
1. **Full Report** (`report_YYYYMMDD_HHMMSS.html`): Complete filtering capabilities
2. **Simple Report** (`report_YYYYMMDD_HHMMSS_simple.html`): Year-only filtering for quick overview

### Summary Section
- **Total Files Processed**: Number of CSV files analyzed
- **Total Records**: Number of scan records
- **Unique Projects**: Count of distinct projects
- **Total Scans**: Total number of scans
- **Successful Scans**: Number of completed scans
- **Failed Scans**: Number of failed scans
- **Success Rate**: Percentage of successful scans

### Interactive Filters (Full Report)
- **File Selector**: Filter by specific CSV file
- **Year Selector**: Filter all data and charts by year
- **Project Search**: Type-ahead project search with dynamic filtering
- **Clear Filters**: Reset all filters to show all data

### Interactive Filters (Simple Report)
- **Year Selector**: Filter all data and charts by year only

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
│   ├── __init__.py           # Package initialization
│   ├── analyzer.py           # Core data analysis and report generation
│   ├── cli.py                # Command-line interface
│   └── templates/
│       ├── template.html        # Full report template (all filters)
│       └── template_simple.html # Simple report template (year filter only)
├── main.py                   # Legacy entry point
├── template.html             # Root template for development
├── template_simple.html      # Root simple template for development
├── setup.py                  # Package installation script
├── pyproject.toml            # Project metadata
├── requirements.txt          # Python dependencies
├── MANIFEST.in               # Package manifest
└── README.md                 # This file
```

## How It Works

1. **Data Extraction**: Reads CSV files from zip archive using pandas
2. **Time-based Analysis**: Parses timestamps and groups data by year and project
3. **Aggregation**: Calculates statistics per file, year, project, and year+project combinations
4. **Chart Generation**: Prepares optimized data structures for Plotly visualizations
   - Applies min-scans threshold to filter low-activity projects
   - Optionally skips year+project combinations for performance
   - Reduces data sampling for large datasets (time series: 200 points, scan type evolution: 100 points)
5. **Template Rendering**: Jinja2 combines data with both full and simple HTML templates
6. **Output**: Generates two timestamped HTML files with embedded charts

## Customization

### Template Styling
Edit templates in `blackduck_metrics/templates/`:
- `template.html` - Full report with all filters
- `template_simple.html` - Simple report with year filter only
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

Each run generates **two reports** with timestamp-based filenames:

### Full Report (with all filters)
- Format: `report_YYYYMMDD_HHMMSS.html`
- Example: `report_20260119_171725.html`
- Features: File, year, and project filtering

### Simple Report (year-only filtering)
- Format: `report_YYYYMMDD_HHMMSS_simple.html`
- Example: `report_20260119_171725_simple.html`
- Features: Year filtering only, faster to load

Both reports are:
- Standalone HTML files (no external dependencies except Plotly CDN)
- Self-contained with embedded data and charts
- Shareable - can be opened directly in any modern browser

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
- Click "Clear Filters" to see all data

**Charts not updating after filter selection**
- Ensure JavaScript is enabled
- Try refreshing the page
- Check browser console for errors

**"Year+Project combination data not available" message**
- Report was generated with `--skip-detailed` flag
- Regenerate without this flag for full year+project filtering
- This is normal for optimized reports

**Report file too large**
- Use `--min-scans 50` or higher to reduce projects in charts
- Use `--skip-detailed` to skip year+project combinations (~36% size reduction)
- Example: 456 MB → 282 MB with --min-scans 100 --skip-detailed

**Year filter not working**
- Ensure `hour` column contains valid timestamps
- Check that data spans multiple years

**Charts show "No data available"**
- Verify CSV files contain the required columns
- Check for empty or malformed data
- Ensure project has sufficient scans (check min-scans threshold)

## License

MIT License
