#!/usr/bin/env python3
"""
Heatmap Metrics Analyzer
Reads CSV files from a zip archive and generates an interactive HTML report
with data comparisons and trends.
"""

import argparse
import zipfile
from pathlib import Path
import pandas as pd
from jinja2 import Template
import json
from datetime import datetime


def read_csv_from_zip(zip_path):
    """
    Read all CSV files from a zip archive and return them as a dictionary of DataFrames.
    
    Args:
        zip_path: Path to the zip file
        
    Returns:
        dict: Dictionary with filename as key and DataFrame as value
    """
    dataframes = {}
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # List all CSV files in the zip
        csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
        
        if not csv_files:
            raise ValueError(f"No CSV files found in {zip_path}")
        
        print(f"Found {len(csv_files)} CSV file(s) in the archive:")
        
        for csv_file in csv_files:
            print(f"  - {csv_file}")
            # Read CSV directly from zip file
            with zip_ref.open(csv_file) as f:
                df = pd.read_csv(f)
                dataframes[csv_file] = df
    
    return dataframes


def analyze_data(dataframes):
    """
    Analyze the data and prepare statistics for visualization.
    
    Args:
        dataframes: Dictionary of DataFrames
        
    Returns:
        dict: Analysis results
    """
    analysis = {
        'summary': {},
        'files': [],
        'aggregated': {},
        'by_year': {},
        'by_project': {},
        'by_year_project': {}
    }
    
    # Combine all dataframes for aggregated analysis
    all_data = pd.concat(dataframes.values(), ignore_index=True) if len(dataframes) > 0 else None
    
    # Extract year information if hour column exists
    available_years = []
    if all_data is not None and 'hour' in all_data.columns:
        try:
            all_data['hour_parsed'] = pd.to_datetime(all_data['hour'])
            all_data['year'] = all_data['hour_parsed'].dt.year
            available_years = sorted(all_data['year'].unique().tolist())
            analysis['available_years'] = available_years
            
            # Calculate statistics for each year
            for year in available_years:
                year_data = all_data[all_data['year'] == year]
                
                # Calculate success/failure for this year
                success_states = ['COMPLETED', 'SUCCESS', 'COMPLETE']
                failure_states = ['ERROR', 'FAILED', 'FAILURE', 'CANCELLED']
                successful_scans_year = 0
                failed_scans_year = 0
                
                # Each row is one scan, so count rows instead of summing scanCount
                if 'state' in year_data.columns:
                    successful_scans_year = len(year_data[year_data['state'].str.upper().isin([s.upper() for s in success_states])])
                    failed_scans_year = len(year_data[year_data['state'].str.upper().isin([s.upper() for s in failure_states])])
                
                year_stats = {
                    'total_rows': len(year_data),
                    'unique_projects': year_data['projectName'].nunique() if 'projectName' in year_data.columns else 0,
                    'total_scans': len(year_data),  # Each row is one scan
                    'successful_scans': successful_scans_year,
                    'failed_scans': failed_scans_year,
                    'scan_types': year_data['scanType'].value_counts().to_dict() if 'scanType' in year_data.columns else {},
                    'top_projects': year_data.groupby('projectName')['scanCount'].sum().nlargest(15).to_dict() if 'projectName' in year_data.columns and 'scanCount' in year_data.columns else {}
                }
                analysis['by_year'][str(year)] = year_stats
                
        except Exception as e:
            print(f"Warning: Could not extract year information: {e}")
    
    # Black Duck specific aggregations
    if all_data is not None and 'projectName' in all_data.columns:
        # Calculate statistics for each project (all projects)
        all_projects_list = sorted([p for p in all_data['projectName'].unique().tolist() if pd.notna(p)])
        
        # Set available_projects to all projects that have data
        analysis['available_projects'] = all_projects_list
        
        for project_name in all_projects_list:
            project_data = all_data[all_data['projectName'] == project_name]
            
            # Calculate success/failure for this project
            success_states = ['COMPLETED', 'SUCCESS', 'COMPLETE']
            failure_states = ['ERROR', 'FAILED', 'FAILURE', 'CANCELLED']
            successful_scans_project = 0
            failed_scans_project = 0
            
            if 'state' in project_data.columns:
                successful_scans_project = len(project_data[project_data['state'].str.upper().isin([s.upper() for s in success_states])])
                failed_scans_project = len(project_data[project_data['state'].str.upper().isin([s.upper() for s in failure_states])])
            
            project_stats = {
                'total_scans': len(project_data),
                'successful_scans': successful_scans_project,
                'failed_scans': failed_scans_project,
                'scan_types': project_data['scanType'].value_counts().to_dict() if 'scanType' in project_data.columns else {}
            }
            analysis['by_project'][project_name] = project_stats
        
        # Generate year+project combinations for ALL projects in the filter list
        if available_years and 'hour' in all_data.columns:
            for year in available_years:
                year_data = all_data[all_data['year'] == year]
                if str(year) not in analysis['by_year_project']:
                    analysis['by_year_project'][str(year)] = {}
                
                # Calculate for all projects
                for project_name in all_projects_list:
                    if pd.notna(project_name):
                        project_year_data = year_data[year_data['projectName'] == project_name]
                        
                        # Only create entry if there are actual scans for this project in this year
                        if len(project_year_data) > 0:
                            # Calculate success/failure
                            successful_scans_proj = 0
                            failed_scans_proj = 0
                            if 'state' in project_year_data.columns:
                                successful_scans_proj = len(project_year_data[project_year_data['state'].str.upper().isin([s.upper() for s in success_states])])
                                failed_scans_proj = len(project_year_data[project_year_data['state'].str.upper().isin([s.upper() for s in failure_states])])
                            
                            project_year_stats = {
                                'total_scans': len(project_year_data),
                                'successful_scans': successful_scans_proj,
                                'failed_scans': failed_scans_proj,
                                'scan_types': project_year_data['scanType'].value_counts().to_dict() if 'scanType' in project_year_data.columns else {}
                            }
                            analysis['by_year_project'][str(year)][project_name] = project_year_stats
        
        # Project-level aggregations
        if 'scanCount' in all_data.columns:
            project_stats = all_data.groupby('projectName').agg({
                'scanCount': 'sum',
                'totalScanSize': 'sum' if 'totalScanSize' in all_data.columns else 'count',
                'codeLocationName': 'count'
            }).to_dict('index')
            analysis['aggregated']['by_project'] = project_stats
        
        # Scan type distribution
        if 'scanType' in all_data.columns:
            scan_type_dist = all_data['scanType'].value_counts().to_dict()
            analysis['aggregated']['scan_types'] = scan_type_dist
            
            # Top projects by scan type
            analysis['aggregated']['projects_by_scan_type'] = {}
            for scan_type in all_data['scanType'].unique():
                scan_type_data = all_data[all_data['scanType'] == scan_type]
                if 'scanCount' in scan_type_data.columns:
                    top_projects = scan_type_data.groupby('projectName')['scanCount'].sum().nlargest(15).to_dict()
                    analysis['aggregated']['projects_by_scan_type'][scan_type] = top_projects
        
        # State distribution
        if 'state' in all_data.columns:
            state_dist = all_data['state'].value_counts().to_dict()
            analysis['aggregated']['states'] = state_dist
        
        # Top projects by scan count (overall)
        if 'scanCount' in all_data.columns:
            top_projects = all_data.groupby('projectName')['scanCount'].sum().nlargest(15).to_dict()
            analysis['aggregated']['top_projects'] = top_projects
    
    for filename, df in dataframes.items():
        file_info = {
            'name': filename,
            'rows': len(df),
            'columns': list(df.columns),
            'column_count': len(df.columns),
            'dtypes': df.dtypes.astype(str).to_dict(),
            'preview': df.head(10).to_dict('records'),
            'stats': {}
        }
        
        # Get basic statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            stats_df = df[numeric_cols].describe()
            file_info['stats'] = stats_df.to_dict()
            file_info['numeric_columns'] = list(numeric_cols)
        
        # Get value counts for categorical columns
        categorical_cols = df.select_dtypes(include=['object']).columns
        if len(categorical_cols) > 0:
            file_info['categorical_columns'] = list(categorical_cols)
            file_info['value_counts'] = {}
            for col in categorical_cols:
                value_counts = df[col].value_counts().head(10).to_dict()
                file_info['value_counts'][col] = value_counts
        
        analysis['files'].append(file_info)
    
    analysis['summary']['total_files'] = len(dataframes)
    analysis['summary']['total_rows'] = sum(len(df) for df in dataframes.values())
    if all_data is not None:
        analysis['summary']['unique_projects'] = all_data['projectName'].nunique() if 'projectName' in all_data.columns else 0
        # Each row is one scan, so count rows instead of summing scanCount
        analysis['summary']['total_scans'] = len(all_data)
        
        # Calculate success/failure based on state - count rows, not sum scanCount
        if 'state' in all_data.columns:
            # Assuming 'COMPLETED' or similar means success, and 'ERROR'/'FAILED' means failure
            # Adjust these values based on actual state values in your data
            success_states = ['COMPLETED', 'SUCCESS', 'COMPLETE']
            failure_states = ['ERROR', 'FAILED', 'FAILURE', 'CANCELLED']
            
            analysis['summary']['successful_scans'] = len(all_data[all_data['state'].str.upper().isin([s.upper() for s in success_states])])
            analysis['summary']['failed_scans'] = len(all_data[all_data['state'].str.upper().isin([s.upper() for s in failure_states])])
        else:
            analysis['summary']['successful_scans'] = 0
            analysis['summary']['failed_scans'] = 0
    
    return analysis


def generate_chart_data(dataframes, min_scans=10):
    """
    Generate data for charts and trend visualization.
    
    Args:
        dataframes: Dictionary of DataFrames
        min_scans: Minimum number of scans for a project to be included in trend charts (default: 10)
        
    Returns:
        dict: Chart data ready for Plotly
    """
    charts = {
        'trends': [],
        'project_bars': [],
        'scan_type_pie': {},
        'time_series': [],
        'time_series_by_year': {},
        'time_series_by_project': {},
        'time_series_by_year_project': {},
        'scan_type_evolution': {},
        'scan_type_evolution_by_year': {},
        'scan_type_evolution_by_project': {},
        'scan_type_evolution_by_year_project': {}
    }
    
    # Combine all dataframes for aggregated charts
    all_data = pd.concat(dataframes.values(), ignore_index=True) if len(dataframes) > 0 else None
    
    if all_data is not None:
        # Time-based trends if hour column exists
        if 'hour' in all_data.columns:
            try:
                # Parse hour column and sort
                all_data['hour_parsed'] = pd.to_datetime(all_data['hour'])
                all_data_sorted = all_data.sort_values('hour_parsed')
                all_data['year'] = all_data['hour_parsed'].dt.year
                
                # Helper function to generate time series for a dataset
                def generate_time_series_for_data(data, data_sorted):
                    series_list = []
                    # Number of scans over time (count of records per hour)
                    time_trend = data_sorted.groupby('hour').size().reset_index(name='count')
                    series_list.append({
                        'name': 'Number of Scans Over Time',
                        'x': time_trend['hour'].tolist(),
                        'y': time_trend['count'].tolist(),
                        'type': 'scatter'
                    })
                    
                    # Total scan size over time
                    if 'totalScanSize' in data.columns:
                        size_trend = data_sorted.groupby('hour')['totalScanSize'].sum().reset_index()
                        series_list.append({
                            'name': 'Total Scan Size Over Time',
                            'x': size_trend['hour'].tolist(),
                            'y': size_trend['totalScanSize'].tolist(),
                            'type': 'scatter'
                        })
                    return series_list
                
                # Generate time series for all data
                charts['time_series'] = generate_time_series_for_data(all_data, all_data_sorted)
                
                # Generate time series by year
                available_years = sorted(all_data['year'].unique().tolist())
                for year in available_years:
                    year_data = all_data[all_data['year'] == year]
                    year_data_sorted = year_data.sort_values('hour_parsed')
                    charts['time_series_by_year'][str(year)] = generate_time_series_for_data(year_data, year_data_sorted)
                
                # Generate time series by project (all projects)
                if 'projectName' in all_data.columns:
                    all_projects = sorted([p for p in all_data['projectName'].unique().tolist() if pd.notna(p)])
                    
                    # Filter projects by minimum scan count
                    project_scan_counts = all_data.groupby('projectName').size()
                    projects_for_charts = [p for p in all_projects if project_scan_counts.get(p, 0) >= min_scans]
                    
                    if len(projects_for_charts) < len(all_projects):
                        print(f"  Filtered to {len(projects_for_charts)}/{len(all_projects)} projects with >= {min_scans} scans")
                    
                    for project in projects_for_charts:
                        if pd.notna(project):
                            project_data = all_data[all_data['projectName'] == project]
                            project_data_sorted = project_data.sort_values('hour_parsed')
                            charts['time_series_by_project'][project] = generate_time_series_for_data(project_data, project_data_sorted)
                            
                            # Generate time series by year+project
                            for year in available_years:
                                year_project_data = project_data[project_data['year'] == year]
                                if len(year_project_data) > 0:
                                    if str(year) not in charts['time_series_by_year_project']:
                                        charts['time_series_by_year_project'][str(year)] = {}
                                    year_project_data_sorted = year_project_data.sort_values('hour_parsed')
                                    charts['time_series_by_year_project'][str(year)][project] = generate_time_series_for_data(year_project_data, year_project_data_sorted)
                
                # Helper function to generate scan type evolution for a dataset
                def generate_scan_type_evolution(data_sorted):
                    evolution = {}
                    if 'scanType' in data_sorted.columns and 'hour' in data_sorted.columns:
                        for scan_type in data_sorted['scanType'].unique():
                            if pd.notna(scan_type):
                                scan_type_data = data_sorted[data_sorted['scanType'] == scan_type]
                                time_trend = scan_type_data.groupby('hour').size().reset_index(name='count')
                                evolution[scan_type] = {
                                    'x': time_trend['hour'].tolist(),
                                    'y': time_trend['count'].tolist()
                                }
                    return evolution
                
                # Scan type evolution over time - all data
                charts['scan_type_evolution'] = generate_scan_type_evolution(all_data_sorted)
                
                # Scan type evolution by year
                for year in available_years:
                    year_data = all_data[all_data['year'] == year]
                    year_data_sorted = year_data.sort_values('hour_parsed')
                    charts['scan_type_evolution_by_year'][str(year)] = generate_scan_type_evolution(year_data_sorted)
                
                # Scan type evolution by project
                if 'projectName' in all_data.columns:
                    for project in projects_for_charts:
                        if pd.notna(project):
                            project_data = all_data[all_data['projectName'] == project]
                            project_data_sorted = project_data.sort_values('hour_parsed')
                            charts['scan_type_evolution_by_project'][project] = generate_scan_type_evolution(project_data_sorted)
                            
                            # Scan type evolution by year+project
                            for year in available_years:
                                year_project_data = project_data[project_data['year'] == year]
                                if len(year_project_data) > 0:
                                    if str(year) not in charts['scan_type_evolution_by_year_project']:
                                        charts['scan_type_evolution_by_year_project'][str(year)] = {}
                                    year_project_data_sorted = year_project_data.sort_values('hour_parsed')
                                    charts['scan_type_evolution_by_year_project'][str(year)][project] = generate_scan_type_evolution(year_project_data_sorted)
            except Exception as e:
                print(f"Warning: Could not parse time data: {e}")
        
        # Top projects by scan count
        if 'projectName' in all_data.columns and 'scanCount' in all_data.columns:
            project_counts = all_data.groupby('projectName')['scanCount'].sum().nlargest(15)
            charts['project_bars'] = {
                'labels': project_counts.index.tolist(),
                'values': project_counts.values.tolist()
            }
        
        # Scan type distribution
        if 'scanType' in all_data.columns:
            scan_types = all_data['scanType'].value_counts()
            charts['scan_type_pie'] = {
                'labels': scan_types.index.tolist(),
                'values': scan_types.values.tolist()
            }
    
    # Individual file trends
    for filename, df in dataframes.items():
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        # Create trend charts for key numeric columns
        priority_cols = ['scanCount', 'totalScanSize', 'maxScanSize']
        for col in priority_cols:
            if col in numeric_cols:
                chart_data = {
                    'name': f"{col}",
                    'type': 'line',
                    'x': list(range(len(df))),
                    'y': df[col].tolist(),
                    'column': col,
                    'file': filename
                }
                charts['trends'].append(chart_data)
    
    return charts


def generate_html_report(analysis, chart_data, output_path):
    """
    Generate HTML reports using Jinja2 templates.
    Creates both a full report (with filters) and a simplified report (without filters).
    
    Args:
        analysis: Analysis results
        chart_data: Chart data
        output_path: Path to save the HTML report
    """
    # Generate the full report with filters
    template_path = Path(__file__).parent / 'template.html'
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    template = Template(template_content)
    
    html_content = template.render(
        analysis=analysis,
        chart_data=json.dumps(chart_data),
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✅ Full HTML report (with filters) generated: {output_path}")
    
    # Generate the simplified report without filters
    template_simple_path = Path(__file__).parent / 'template_simple.html'
    
    if template_simple_path.exists():
        with open(template_simple_path, 'r', encoding='utf-8') as f:
            template_simple_content = f.read()
        
        template_simple = Template(template_simple_content)
        
        html_simple_content = template_simple.render(
            analysis=analysis,
            chart_data=json.dumps(chart_data),
            generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Create simple report filename by inserting '_simple' before .html
        output_path_obj = Path(output_path)
        simple_output_path = output_path_obj.parent / f"{output_path_obj.stem}_simple{output_path_obj.suffix}"
        
        with open(simple_output_path, 'w', encoding='utf-8') as f:
            f.write(html_simple_content)
        
        print(f"✅ Simple HTML report (no filters) generated: {simple_output_path}")
    else:
        print(f"⚠️ Warning: Simplified template not found at {template_simple_path}")


def main():
    """Main function to orchestrate the analysis."""
    parser = argparse.ArgumentParser(
        description='Analyze CSV files from a zip archive and generate an HTML report'
    )
    parser.add_argument(
        'zip_file',
        help='Path to the zip file containing CSV files'
    )
    
    # Generate default filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_output = f'report_{timestamp}.html'
    
    parser.add_argument(
        '-o', '--output',
        default=default_output,
        help=f'Output HTML file path (default: {default_output})'
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
        print("Generating charts...")
        chart_data = generate_chart_data(dataframes)
        
        # Generate HTML report
        print("Creating HTML report...")
        generate_html_report(analysis, chart_data, args.output)
        
        print("\nAnalysis complete!")
        print(f"  Files processed: {analysis['summary']['total_files']}")
        print(f"  Total rows: {analysis['summary']['total_rows']}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
