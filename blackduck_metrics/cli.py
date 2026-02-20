"""
Command-line interface for Black Duck Heatmap Metrics Analyzer.
"""

import argparse
from pathlib import Path
from datetime import datetime
import time

from . import __version__
from .analyzer import read_csv_from_zip, analyze_data, generate_chart_data, generate_html_report
from .blackduck_connector import BlackDuckConnector


def get_project_names_from_group(project_group_name, bd_url=None, bd_token=None):
    """
    Get list of project names from a Black Duck project group.
    
    Args:
        project_group_name: Name of the project group
        bd_url: Black Duck server URL (optional, uses BD_URL env var if not provided)
        bd_token: Black Duck API token (optional, uses BD_API_TOKEN env var if not provided)
        
    Returns:
        set: Set of project names in the group
        
    Raises:
        Exception: If connection fails or project group not found
    """
    print(f"Connecting to Black Duck to fetch projects from group '{project_group_name}'...")
    
    # Create connector (uses provided args or environment variables for auth)
    connector = BlackDuckConnector(base_url=bd_url, api_token=bd_token)
    
    try:
        # Get projects from the group
        projects_data = connector.get_project_group_projects(project_group_name)
        
        if projects_data['totalCount'] == 0:
            print(f"Warning: No projects found in group '{project_group_name}'")
            return set()
        
        # Extract project names
        project_names = set()
        for project in projects_data.get('items', []):
            if 'name' in project:
                project_names.add(project['name'])
        
        print(f"Found {len(project_names)} projects in group '{project_group_name}'")
        return project_names
        
    finally:
        connector.disconnect()


def filter_dataframes_by_projects(dataframes, project_names):
    """
    Filter dataframes to only include rows where projectName is in the given set.
    
    Args:
        dataframes: Dictionary of DataFrames
        project_names: Set of project names to include
        
    Returns:
        dict: Filtered dictionary of DataFrames
    """
    if not project_names:
        print("Warning: Empty project list, no data will be included")
        return {}
    
    filtered_dfs = {}
    total_rows_before = 0
    total_rows_after = 0
    
    for filename, df in dataframes.items():
        total_rows_before += len(df)
        
        # Check if projectName column exists
        if 'projectName' not in df.columns:
            print(f"Warning: 'projectName' column not found in {filename}, skipping filter for this file")
            filtered_dfs[filename] = df
            total_rows_after += len(df)
            continue
        
        # Filter by project names
        filtered_df = df[df['projectName'].isin(project_names)]
        filtered_dfs[filename] = filtered_df
        total_rows_after += len(filtered_df)
    
    if total_rows_before > 0:
        print(f"Filtered data: {total_rows_before} rows -> {total_rows_after} rows ({total_rows_after/total_rows_before*100:.1f}% retained)")
    else:
        print("No data to filter")
    
    return filtered_dfs


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
        default=None,
        help='Output folder path (default: current directory). Reports will be named report_<timestamp>.html or report_<timestamp>_<project-group>.html'
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
        '--simple',
        action='store_true',
        help='Generate simplified report without interactive filters (smaller file size, faster loading)'
    )
    
    parser.add_argument(
        '--start-year',
        type=int,
        help='Only analyze data from this year onwards (e.g., --start-year 2020 to exclude data before 2020)'
    )

    parser.add_argument(
        '--project-group',
        type=str,
        help='Only analyze data from this project group (e.g., --project-group "Demo" to include only projects in the "Demo" project group)'
    )
    
    parser.add_argument(
        '--bd-url',
        type=str,
        help='Black Duck server URL (can also use BD_URL environment variable)'
    )
    
    parser.add_argument(
        '--bd-token',
        type=str,
        help='Black Duck API token (can also use BD_API_TOKEN environment variable)'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    
    args = parser.parse_args()
    
    # Determine output folder and filename
    if args.output is None:
        output_folder = Path('.')
    else:
        output_folder = Path(args.output)
    
    # Generate filename with timestamp and optional project group
    if args.project_group:
        # Sanitize project group name for filename
        safe_group_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in args.project_group)
        output_filename = f'report_{timestamp}_{safe_group_name}.html'
    else:
        output_filename = default_output
    
    # Combine folder and filename
    output_path = output_folder / output_filename
    
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
        
        # Filter by project group if specified
        if args.project_group:
            print(f"\nFiltering projects by group: {args.project_group}")
            try:
                project_names = get_project_names_from_group(
                    args.project_group,
                    bd_url=args.bd_url,
                    bd_token=args.bd_token
                )
                dataframes = filter_dataframes_by_projects(dataframes, project_names)
                
                if not dataframes or all(len(df) == 0 for df in dataframes.values()):
                    print(f"Error: No data remaining after filtering by project group '{args.project_group}'")
                    return 1
                    
            except Exception as e:
                print(f"Error filtering by project group: {e}")
                print("Make sure Black Duck credentials are set via --bd-url and --bd-token arguments")
                print("or environment variables: BD_URL, BD_API_TOKEN (or BD_USERNAME and BD_PASSWORD)")
                return 1
        
        # Analyze data
        print("\nAnalyzing data...")
        if args.start_year:
            print(f"  Filtering data from year {args.start_year} onwards (for full report)")
        analysis = analyze_data(dataframes, start_year=args.start_year)
        
        # For simple report, generate analysis with all years if start_year was specified
        analysis_simple = None
        if args.start_year:
            print(f"  Generating simple report data (all years)")
            analysis_simple = analyze_data(dataframes, start_year=None)
        
        # Generate chart data
        print(f"Generating charts (min scans per project: {args.min_scans})...")
        if args.skip_detailed:
            print("  Skip detailed mode: Year+project combinations will be skipped")
        chart_data = generate_chart_data(dataframes, min_scans=args.min_scans, skip_detailed=args.skip_detailed)
        
        # For simple report, use the same chart data (generated from all years)
        chart_data_simple = chart_data if args.start_year else None
        
        # Create output folder if it doesn't exist
        output_folder.mkdir(parents=True, exist_ok=True)
        
        # Generate HTML report
        print("Creating HTML report...")
        generate_html_report(analysis, chart_data, str(output_path), min_scans=args.min_scans, 
                           analysis_simple=analysis_simple, chart_data_simple=chart_data_simple,
                           project_group_name=args.project_group, simple_only=args.simple)
        
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
