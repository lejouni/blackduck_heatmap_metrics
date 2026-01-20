"""
Command-line interface for Black Duck Heatmap Metrics Analyzer.
"""

import argparse
from pathlib import Path
from datetime import datetime
import time

from . import __version__
from .analyzer import read_csv_from_zip, analyze_data, generate_chart_data, generate_html_report


def main():
    """Main function to orchestrate the analysis."""
    # Start timing
    start_time = time.time()
    
    parser = argparse.ArgumentParser(
        description='Analyze Black Duck scan heatmap data from CSV files in zip archives',
        prog='bdmetrics'
    )
    parser.add_argument(
        'zip_file',
        help='Path to the zip file containing CSV files with Black Duck scan data'
    )
    
    # Generate default filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_output = f'report_{timestamp}.html'
    
    parser.add_argument(
        '-o', '--output',
        default=default_output,
        help=f'Output HTML file path (default: {default_output})'
    )
    
    parser.add_argument(
        '--min-scans',
        type=int,
        default=10,
        help='Minimum number of scans for a project to be included in trend charts (default: 10)'
    )
    
    parser.add_argument(
        '--skip-detailed',
        action='store_true',
        help='Skip year+project combination charts to significantly reduce file size (recommended for large datasets)'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    
    args = parser.parse_args()
    
    zip_path = Path(args.zip_file)
    
    if not zip_path.exists():
        print(f"Error: File not found: {zip_path}")
        return 1
    
    if not zip_path.suffix == '.zip':
        print(f"Error: File must be a zip archive: {zip_path}")
        return 1
    
    print(f"Reading CSV files from: {zip_path}")
    
    try:
        # Read CSV files from zip
        dataframes = read_csv_from_zip(zip_path)
        
        # Analyze data
        print("\nAnalyzing data...")
        analysis = analyze_data(dataframes)
        
        # Generate chart data
        print(f"Generating charts (min scans per project: {args.min_scans})...")
        if args.skip_detailed:
            print("  Skip detailed mode: Year+project combinations will be skipped")
        chart_data = generate_chart_data(dataframes, min_scans=args.min_scans, skip_detailed=args.skip_detailed)
        
        # Create output directory if it doesn't exist
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate HTML report
        print("Creating HTML report...")
        generate_html_report(analysis, chart_data, args.output, min_scans=args.min_scans)
        
        # Calculate execution time
        elapsed_time = time.time() - start_time
        
        print("\nAnalysis complete!")
        print(f"  Files processed: {analysis['summary']['total_files']}")
        print(f"  Total rows: {analysis['summary']['total_rows']}")
        print(f"  Execution time: {elapsed_time:.2f} seconds")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
