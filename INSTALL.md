# Installation and Usage Guide

## Package Structure

The project is now organized as a Python package:

```
blackduck_heatmap_metrics/
├── blackduck_metrics/          # Main package directory
│   ├── __init__.py            # Package initialization
│   ├── analyzer.py            # Core analysis functions
│   ├── cli.py                 # Command-line interface
│   └── templates/             # HTML templates
│       └── template.html      # Report template
├── main.py                    # Legacy standalone script (still works)
├── template.html              # Template (kept for compatibility)
├── setup.py                   # Setup configuration
├── pyproject.toml             # Modern Python packaging config
├── MANIFEST.in                # Package manifest
├── requirements.txt           # Dependencies
└── README.md                  # Documentation
```

## Installation Options

### Option 1: Install as Package (Recommended)

Install in development mode (changes to code are immediately reflected):
```bash
pip install -e .
```

Or install normally:
```bash
pip install .
```

After installation, use the `bdmetrics` command:
```bash
bdmetrics "path/to/data.zip"
bdmetrics "path/to/data.zip" -o output.html
bdmetrics --version
bdmetrics --help
```

### Option 2: Use as Standalone Script

You can still use the original `main.py`:
```bash
python main.py "path/to/data.zip"
```

### Option 3: Use as Python Module

Import and use programmatically:
```python
from blackduck_metrics import read_csv_from_zip, analyze_data, generate_chart_data, generate_html_report

# Your custom analysis workflow
dataframes = read_csv_from_zip("data.zip")
analysis = analyze_data(dataframes)
chart_data = generate_chart_data(dataframes)
generate_html_report(analysis, chart_data, "report.html")
```

## Publishing to PyPI (Future)

To publish this package to PyPI so others can install with `pip install blackduck-heatmap-metrics`:

1. Create accounts on PyPI and TestPyPI
2. Build the package:
   ```bash
   python -m build
   ```
3. Upload to TestPyPI first:
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```
4. Test installation:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ blackduck-heatmap-metrics
   ```
5. Upload to PyPI:
   ```bash
   python -m twine upload dist/*
   ```

## Uninstallation

```bash
pip uninstall blackduck-heatmap-metrics
```

## Development

To contribute or modify:

1. Clone the repository
2. Install in editable mode: `pip install -e .`
3. Make changes to `blackduck_metrics/analyzer.py` or `blackduck_metrics/cli.py`
4. Test: `bdmetrics "test-data.zip"`
5. Changes are immediately reflected without reinstalling

## Testing

Test the package:
```bash
# Test CLI
bdmetrics "C:\Users\JouniLehto\Downloads\heatmap-data (1).zip"

# Test with output specification
bdmetrics "path/to/data.zip" -o custom_name.html

# Test version
bdmetrics --version

# Test help
bdmetrics --help
```

Test as module:
```python
from blackduck_metrics import read_csv_from_zip, analyze_data

dataframes = read_csv_from_zip("test.zip")
analysis = analyze_data(dataframes)
print(f"Processed {analysis['summary']['total_rows']} rows")
```
