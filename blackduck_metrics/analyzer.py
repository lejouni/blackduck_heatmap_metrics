"""
Core analysis functions for Black Duck heatmap metrics.
"""

import zipfile
from pathlib import Path
import pandas as pd
import numpy as np
from jinja2 import Template, Undefined
import json
from datetime import datetime
from tqdm import tqdm
import gzip
import base64
try:
    from importlib.resources import files
except ImportError:
    # Fallback for Python < 3.9
    from importlib_resources import files


class UndefinedSafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that converts Jinja2 Undefined to None."""
    def default(self, obj):
        if isinstance(obj, Undefined):
            return None
        return super().default(obj)


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
        
        for csv_file in tqdm(csv_files, desc="Reading CSV files", unit="file"):
            print(f"  - {csv_file}")
            # Read CSV directly from zip file
            with zip_ref.open(csv_file) as f:
                df = pd.read_csv(f)
                dataframes[csv_file] = df
    
    return dataframes


def calculate_busy_quiet_hours(data):
    """
    Calculate the distribution of scans across 3-hour time blocks.
    Time blocks: 06-09, 09-12, 12-15, 15-18, 18-21, 21-00, 00-03, 03-06
    Also calculates these metrics separately for successful and failed scans.
    
    Args:
        data: DataFrame with 'hour_parsed' column and optionally 'is_success' and 'is_failure' columns
        
    Returns:
        dict: Dictionary containing distribution of scans across time blocks and busiest/quietest blocks
              Includes separate metrics for all scans, successful scans only, and failed scans only
    """
    # Define the 8 time blocks in order: 06-09, 09-12, 12-15, 15-18, 18-21, 21-00, 00-03, 03-06
    time_blocks = [6, 9, 12, 15, 18, 21, 0, 3]
    time_block_labels = ['06-09', '09-12', '12-15', '15-18', '18-21', '21-00', '00-03', '03-06']
    
    result = {
        'time_blocks': [],  # List of dicts with time block info
        'time_blocks_success': [],
        'time_blocks_failed': [],
        'busiest_hour': None,
        'busiest_hour_end': None,
        'busiest_count': 0,
        'busiest_percentage': 0,
        'quietest_hour': None,
        'quietest_hour_end': None,
        'quietest_count': 0,
        'quietest_percentage': 0,
        # Success-only metrics
        'busiest_hour_success': None,
        'busiest_hour_end_success': None,
        'busiest_count_success': 0,
        'busiest_percentage_success': 0,
        'quietest_hour_success': None,
        'quietest_hour_end_success': None,
        'quietest_count_success': 0,
        'quietest_percentage_success': 0,
        # Failed-only metrics
        'busiest_hour_failed': None,
        'busiest_hour_end_failed': None,
        'busiest_count_failed': 0,
        'busiest_percentage_failed': 0,
        'quietest_hour_failed': None,
        'quietest_hour_end_failed': None,
        'quietest_count_failed': 0,
        'quietest_percentage_failed': 0
    }
    
    if data is None or len(data) == 0:
        return result
    
    if 'hour_parsed' not in data.columns:
        return result
    
    def map_hour_to_block(hour):
        """Map hour (0-23) to time block start hour"""
        if 6 <= hour < 9:
            return 6
        elif 9 <= hour < 12:
            return 9
        elif 12 <= hour < 15:
            return 12
        elif 15 <= hour < 18:
            return 15
        elif 18 <= hour < 21:
            return 18
        elif 21 <= hour < 24:
            return 21
        elif 0 <= hour < 3:
            return 0
        else:  # 3 <= hour < 6
            return 3
    
    def calc_metrics(subset_data, prefix=''):
        """Helper function to calculate metrics for a data subset"""
        metrics = {}
        time_blocks_list = []
        
        if len(subset_data) == 0:
            return metrics, time_blocks_list
            
        try:
            # Extract hour of day (0-23)
            subset_copy = subset_data.copy()
            subset_copy['hour_of_day'] = subset_copy['hour_parsed'].dt.hour
            
            # Map hours to time blocks
            subset_copy['hour_block'] = subset_copy['hour_of_day'].apply(map_hour_to_block)
            
            # Count scans per time block
            block_counts = subset_copy.groupby('hour_block').size()
            total_scans = len(subset_copy)
            
            # Create time blocks list with all blocks (even if 0 count)
            for i, block_start in enumerate(time_blocks):
                block_end = (block_start + 3) % 24
                count = int(block_counts.get(block_start, 0))
                percentage = round((count / total_scans) * 100, 1) if total_scans > 0 else 0
                time_blocks_list.append({
                    'label': time_block_labels[i],
                    'start': block_start,
                    'end': block_end,
                    'count': count,
                    'percentage': percentage
                })
            
            if len(block_counts) > 0 and total_scans > 0:
                # Find busiest 3-hour block
                busiest_block = block_counts.idxmax()
                metrics[f'busiest_hour{prefix}'] = int(busiest_block)
                metrics[f'busiest_hour_end{prefix}'] = int((busiest_block + 3) % 24)
                metrics[f'busiest_count{prefix}'] = int(block_counts[busiest_block])
                metrics[f'busiest_percentage{prefix}'] = round((block_counts[busiest_block] / total_scans) * 100, 1)
                
                # Find quietest 3-hour block
                quietest_block = block_counts.idxmin()
                metrics[f'quietest_hour{prefix}'] = int(quietest_block)
                metrics[f'quietest_hour_end{prefix}'] = int((quietest_block + 3) % 24)
                metrics[f'quietest_count{prefix}'] = int(block_counts[quietest_block])
                metrics[f'quietest_percentage{prefix}'] = round((block_counts[quietest_block] / total_scans) * 100, 1)
        except Exception as e:
            print(f"Warning: Could not calculate busy/quiet hours for {prefix}: {e}")
        
        return metrics, time_blocks_list
    
    try:
        # Calculate for all scans
        metrics, time_blocks_list = calc_metrics(data, '')
        result.update(metrics)
        result['time_blocks'] = time_blocks_list
        
        # Calculate for successful scans only
        if 'is_success' in data.columns:
            success_data = data[data['is_success'] == True]
            metrics, time_blocks_list = calc_metrics(success_data, '_success')
            result.update(metrics)
            result['time_blocks_success'] = time_blocks_list
        
        # Calculate for failed scans only
        if 'is_failure' in data.columns:
            failed_data = data[data['is_failure'] == True]
            metrics, time_blocks_list = calc_metrics(failed_data, '_failed')
            result.update(metrics)
            result['time_blocks_failed'] = time_blocks_list
    
    except Exception as e:
        print(f"Warning: Could not calculate busy/quiet hours: {e}")
    
    return result


def copy_busy_quiet_metrics(target_dict, busy_quiet):
    """
    Helper function to copy all busiest/quietest hour metrics from busy_quiet dict to target dict.
    Includes metrics for all scans, successful scans only, and failed scans only.
    Also copies time_blocks data.
    
    Args:
        target_dict: Dictionary to copy metrics to
        busy_quiet: Dictionary containing busiest/quietest hour metrics from calculate_busy_quiet_hours
    """
    # Time blocks data
    target_dict['time_blocks'] = busy_quiet.get('time_blocks', [])
    target_dict['time_blocks_success'] = busy_quiet.get('time_blocks_success', [])
    target_dict['time_blocks_failed'] = busy_quiet.get('time_blocks_failed', [])
    
    # All scans metrics
    target_dict['busiest_hour'] = busy_quiet['busiest_hour']
    target_dict['busiest_hour_end'] = busy_quiet['busiest_hour_end']
    target_dict['busiest_count'] = busy_quiet['busiest_count']
    target_dict['busiest_percentage'] = busy_quiet['busiest_percentage']
    target_dict['quietest_hour'] = busy_quiet['quietest_hour']
    target_dict['quietest_hour_end'] = busy_quiet['quietest_hour_end']
    target_dict['quietest_count'] = busy_quiet['quietest_count']
    target_dict['quietest_percentage'] = busy_quiet['quietest_percentage']
    
    # Success-only metrics
    target_dict['busiest_hour_success'] = busy_quiet['busiest_hour_success']
    target_dict['busiest_hour_end_success'] = busy_quiet['busiest_hour_end_success']
    target_dict['busiest_count_success'] = busy_quiet['busiest_count_success']
    target_dict['busiest_percentage_success'] = busy_quiet['busiest_percentage_success']
    target_dict['quietest_hour_success'] = busy_quiet['quietest_hour_success']
    target_dict['quietest_hour_end_success'] = busy_quiet['quietest_hour_end_success']
    target_dict['quietest_count_success'] = busy_quiet['quietest_count_success']
    target_dict['quietest_percentage_success'] = busy_quiet['quietest_percentage_success']
    
    # Failed-only metrics
    target_dict['busiest_hour_failed'] = busy_quiet['busiest_hour_failed']
    target_dict['busiest_hour_end_failed'] = busy_quiet['busiest_hour_end_failed']
    target_dict['busiest_count_failed'] = busy_quiet['busiest_count_failed']
    target_dict['busiest_percentage_failed'] = busy_quiet['busiest_percentage_failed']
    target_dict['quietest_hour_failed'] = busy_quiet['quietest_hour_failed']
    target_dict['quietest_hour_end_failed'] = busy_quiet['quietest_hour_end_failed']
    target_dict['quietest_count_failed'] = busy_quiet['quietest_count_failed']
    target_dict['quietest_percentage_failed'] = busy_quiet['quietest_percentage_failed']


def calculate_projects_by_time_block(data):
    """
    Calculate top projects for each 3-hour time block.
    Time blocks: 06-09, 09-12, 12-15, 15-18, 18-21, 21-00, 00-03, 03-06
    
    Args:
        data: DataFrame with 'hour_parsed' and 'projectName' columns, 
              optionally with 'is_success' and 'is_failure' columns
        
    Returns:
        dict: Dictionary with projects_by_time_block, projects_by_time_block_success, projects_by_time_block_failed
    """
    result = {
        'projects_by_time_block': {},
        'projects_by_time_block_success': {},
        'projects_by_time_block_failed': {}
    }
    
    if data is None or len(data) == 0:
        return result
    
    if 'hour_parsed' not in data.columns or 'projectName' not in data.columns:
        return result
    
    # Define the 8 time blocks
    time_block_labels = ['06-09', '09-12', '12-15', '15-18', '18-21', '21-00', '00-03', '03-06']
    
    def map_hour_to_block_label(hour):
        """Map hour (0-23) to time block label"""
        if 6 <= hour < 9:
            return '06-09'
        elif 9 <= hour < 12:
            return '09-12'
        elif 12 <= hour < 15:
            return '12-15'
        elif 15 <= hour < 18:
            return '15-18'
        elif 18 <= hour < 21:
            return '18-21'
        elif 21 <= hour < 24:
            return '21-00'
        elif 0 <= hour < 3:
            return '00-03'
        else:  # 3 <= hour < 6
            return '03-06'
    
    try:
        # Extract hour of day and map to time block
        data_copy = data.copy()
        data_copy['hour_of_day'] = data_copy['hour_parsed'].dt.hour
        data_copy['time_block'] = data_copy['hour_of_day'].apply(map_hour_to_block_label)
        
        # Calculate for all scans
        for time_block in time_block_labels:
            block_data = data_copy[data_copy['time_block'] == time_block]
            if len(block_data) > 0:
                top_projects = block_data.groupby('projectName').size().nlargest(10).to_dict()
                result['projects_by_time_block'][time_block] = top_projects
        
        # Calculate for successful scans only
        if 'is_success' in data_copy.columns:
            success_data = data_copy[data_copy['is_success'] == True]
            for time_block in time_block_labels:
                block_data = success_data[success_data['time_block'] == time_block]
                if len(block_data) > 0:
                    top_projects = block_data.groupby('projectName').size().nlargest(10).to_dict()
                    result['projects_by_time_block_success'][time_block] = top_projects
        
        # Calculate for failed scans only
        if 'is_failure' in data_copy.columns:
            failed_data = data_copy[data_copy['is_failure'] == True]
            for time_block in time_block_labels:
                block_data = failed_data[failed_data['time_block'] == time_block]
                if len(block_data) > 0:
                    top_projects = block_data.groupby('projectName').size().nlargest(10).to_dict()
                    result['projects_by_time_block_failed'][time_block] = top_projects
    
    except Exception as e:
        print(f"Warning: Could not calculate projects by time block: {e}")
    
    return result


def calculate_scan_types_by_status(data):
    """
    Calculate scan type distributions for all scans, successful scans only, and failed scans only.
    
    Args:
        data: DataFrame with 'scanType' column and optionally 'is_success' and 'is_failure' columns
        
    Returns:
        dict: Dictionary containing scan_types, scan_types_success, and scan_types_failed (all sorted alphabetically)
    """
    result = {
        'scan_types': {},
        'scan_types_success': {},
        'scan_types_failed': {}
    }
    
    if data is None or len(data) == 0:
        return result
    
    if 'scanType' not in data.columns:
        return result
    
    # Calculate scan types for all scans (sorted alphabetically)
    scan_types_dict = data['scanType'].value_counts().to_dict()
    result['scan_types'] = dict(sorted(scan_types_dict.items(), key=lambda x: x[0].upper()))
    
    # Calculate scan types for successful scans only (sorted alphabetically)
    if 'is_success' in data.columns:
        success_data = data[data['is_success'] == True]
        if len(success_data) > 0:
            success_dict = success_data['scanType'].value_counts().to_dict()
            result['scan_types_success'] = dict(sorted(success_dict.items(), key=lambda x: x[0].upper()))
    
    # Calculate scan types for failed scans only (sorted alphabetically)
    if 'is_failure' in data.columns:
        failed_data = data[data['is_failure'] == True]
        if len(failed_data) > 0:
            failed_dict = failed_data['scanType'].value_counts().to_dict()
            result['scan_types_failed'] = dict(sorted(failed_dict.items(), key=lambda x: x[0].upper()))
    
    return result


def calculate_top_projects_by_status(data):
    """
    Calculate top 15 projects by scan count for all scans, successful scans only, and failed scans only.
    
    Args:
        data: DataFrame with 'projectName' and 'scanCount' columns, and optionally 'is_success' and 'is_failure' columns
        
    Returns:
        dict: Dictionary containing top_projects, top_projects_success, and top_projects_failed
    """
    result = {
        'top_projects': {},
        'top_projects_success': {},
        'top_projects_failed': {}
    }
    
    if data is None or len(data) == 0:
        return result
    
    if 'projectName' not in data.columns or 'scanCount' not in data.columns:
        return result
    
    # Calculate top projects for all scans (count rows, each row is a scan)
    result['top_projects'] = data.groupby('projectName').size().nlargest(15).to_dict()
    
    # Calculate top projects for successful scans only
    if 'is_success' in data.columns:
        success_data = data[data['is_success'] == True]
        if len(success_data) > 0 and 'projectName' in success_data.columns:
            result['top_projects_success'] = success_data.groupby('projectName').size().nlargest(15).to_dict()
    
    # Calculate top projects for failed scans only
    if 'is_failure' in data.columns:
        failed_data = data[data['is_failure'] == True]
        if len(failed_data) > 0 and 'projectName' in failed_data.columns:
            result['top_projects_failed'] = failed_data.groupby('projectName').size().nlargest(15).to_dict()
    
    return result


def analyze_data(dataframes):
    """
    Analyze the data and prepare statistics for visualization.
    
    Args:
        dataframes: Dictionary of DataFrames
        
    Returns:
        dict: Analysis results
    """
    analysis = {
        'summary': {
            # Initialize all expected fields with defaults
            'total_files': 0,
            'total_rows': 0,
            'unique_projects': 0,
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'scan_types': {},
            'scan_types_success': {},
            'scan_types_failed': {},
            'busiest_hour': None,
            'busiest_hour_end': None,
            'busiest_count': 0,
            'busiest_percentage': 0,
            'quietest_hour': None,
            'quietest_hour_end': None,
            'quietest_count': 0,
            'quietest_percentage': 0,
            'busiest_hour_success': None,
            'busiest_hour_end_success': None,
            'busiest_count_success': 0,
            'busiest_percentage_success': 0,
            'quietest_hour_success': None,
            'quietest_hour_end_success': None,
            'quietest_count_success': 0,
            'quietest_percentage_success': 0,
            'busiest_hour_failed': None,
            'busiest_hour_end_failed': None,
            'busiest_count_failed': 0,
            'busiest_percentage_failed': 0,
            'quietest_hour_failed': None,
            'quietest_hour_end_failed': None,
            'quietest_count_failed': 0,
            'quietest_percentage_failed': 0,
            'time_blocks': [],
            'time_blocks_success': [],
            'time_blocks_failed': []
        },
        'files': [],
        'aggregated': {
            # Initialize all expected aggregated fields with defaults
            'by_project': {},
            'scan_types': {},
            'projects_by_scan_type': {},
            'projects_by_scan_type_success': {},
            'projects_by_scan_type_failed': {},
            'projects_by_time_block': {},
            'projects_by_time_block_success': {},
            'projects_by_time_block_failed': {},
            'top_projects': {},
            'top_projects_success': {},
            'top_projects_failed': {},
            'states': {}
        },
        'by_year': {},
        'by_project': {},
        'by_year_project': {},
        'by_file': {},  # Per-file statistics
        'available_files': list(dataframes.keys())  # Track available CSV files
    }
    
    # Combine all dataframes for aggregated analysis
    all_data = pd.concat(dataframes.values(), ignore_index=True) if len(dataframes) > 0 else None
    
    # Pre-compute state classifications once (vectorized operation)
    success_states = ['COMPLETED', 'SUCCESS', 'COMPLETE']
    failure_states = ['ERROR', 'FAILED', 'FAILURE', 'CANCELLED']
    
    if all_data is not None and 'state' in all_data.columns:
        # Vectorized state classification - much faster than repeated filtering
        all_data['state_upper'] = all_data['state'].str.upper()
        all_data['is_success'] = all_data['state_upper'].isin([s.upper() for s in success_states])
        all_data['is_failure'] = all_data['state_upper'].isin([s.upper() for s in failure_states])
    
    # Extract year information if hour column exists
    available_years = []
    if all_data is not None and 'hour' in all_data.columns:
        try:
            all_data['hour_parsed'] = pd.to_datetime(all_data['hour'])
            all_data['year'] = all_data['hour_parsed'].dt.year
            available_years = sorted(all_data['year'].unique().tolist())
            analysis['available_years'] = available_years
            
            # Optimized: Use groupby instead of iterating through years
            print("Analyzing by year...")
            year_groups = all_data.groupby('year')
            
            for year, year_data in tqdm(year_groups, desc="Analyzing by year", unit="year"):
                year_stats = {
                    'total_rows': len(year_data),
                    'unique_projects': year_data['projectName'].nunique() if 'projectName' in year_data.columns else 0,
                    'total_scans': len(year_data),
                    'successful_scans': year_data['is_success'].sum() if 'is_success' in year_data.columns else 0,
                    'failed_scans': year_data['is_failure'].sum() if 'is_failure' in year_data.columns else 0
                }
                # Add top projects (all, success, failed)
                top_projects_data = calculate_top_projects_by_status(year_data)
                year_stats.update(top_projects_data)
                # Add scan types (all, success, failed)
                scan_types_data = calculate_scan_types_by_status(year_data)
                year_stats.update(scan_types_data)
                # Add busiest/quietest hours for this year
                busy_quiet = calculate_busy_quiet_hours(year_data)
                copy_busy_quiet_metrics(year_stats, busy_quiet)
                analysis['by_year'][str(year)] = year_stats
                
        except Exception as e:
            print(f"Warning: Could not extract year information: {e}")
    
    # Black Duck specific aggregations
    if all_data is not None and 'projectName' in all_data.columns:
        # Calculate statistics for each project (all projects)
        all_projects_list = sorted([p for p in all_data['projectName'].unique().tolist() if pd.notna(p)])
        
        # Set available_projects to all projects that have data
        analysis['available_projects'] = all_projects_list
        
        # Optimized: Use groupby instead of iterating and filtering
        print("Analyzing projects...")
        project_groups = all_data.groupby('projectName')
        
        # Pre-compute aggregations for all projects at once
        project_agg = project_groups.agg({
            'is_success': 'sum' if 'is_success' in all_data.columns else 'count',
            'is_failure': 'sum' if 'is_failure' in all_data.columns else 'count',
        })
        
        for project_name in tqdm(all_projects_list, desc="Analyzing projects", unit="project"):
            if pd.notna(project_name) and project_name in project_groups.groups:
                project_data = project_groups.get_group(project_name)
                
                project_stats = {
                    'total_scans': len(project_data),
                    'successful_scans': int(project_agg.loc[project_name, 'is_success']) if 'is_success' in project_agg.columns else 0,
                    'failed_scans': int(project_agg.loc[project_name, 'is_failure']) if 'is_failure' in project_agg.columns else 0
                }
                # Add scan types (all, success, failed)
                scan_types_data = calculate_scan_types_by_status(project_data)
                project_stats.update(scan_types_data)
                # Add busiest/quietest hours for this project
                busy_quiet = calculate_busy_quiet_hours(project_data)
                copy_busy_quiet_metrics(project_stats, busy_quiet)
                analysis['by_project'][project_name] = project_stats
        
        # Generate year+project combinations - optimized with multi-level groupby
        if available_years and 'hour' in all_data.columns:
            print("Analyzing year-project combinations...")
            # Multi-level groupby is much faster than nested loops
            year_project_groups = all_data.groupby(['year', 'projectName'])
            
            with tqdm(total=len(available_years) * len(all_projects_list), desc="Year-project analysis", unit="combo") as pbar:
                for year in available_years:
                    if str(year) not in analysis['by_year_project']:
                        analysis['by_year_project'][str(year)] = {}
                    
                    for project_name in all_projects_list:
                        if pd.notna(project_name):
                            try:
                                project_year_data = year_project_groups.get_group((year, project_name))
                                
                                if len(project_year_data) > 0:
                                    project_year_stats = {
                                        'total_scans': len(project_year_data),
                                        'successful_scans': project_year_data['is_success'].sum() if 'is_success' in project_year_data.columns else 0,
                                        'failed_scans': project_year_data['is_failure'].sum() if 'is_failure' in project_year_data.columns else 0
                                    }
                                    # Add scan types (all, success, failed)
                                    scan_types_data = calculate_scan_types_by_status(project_year_data)
                                    project_year_stats.update(scan_types_data)
                                    # Add busiest/quietest hours for this year+project combination
                                    busy_quiet = calculate_busy_quiet_hours(project_year_data)
                                    copy_busy_quiet_metrics(project_year_stats, busy_quiet)
                                    analysis['by_year_project'][str(year)][project_name] = project_year_stats
                            except KeyError:
                                # This year-project combination doesn't exist
                                pass
                            pbar.update(1)
        
        # Project-level aggregations
        if 'scanCount' in all_data.columns:
            project_stats = all_data.groupby('projectName').agg({
                'scanCount': 'sum',
                'totalScanSize': 'sum' if 'totalScanSize' in all_data.columns else 'count',
                'codeLocationName': 'count'
            }).to_dict('index')
            analysis['aggregated']['by_project'] = project_stats
        
        # Scan type distribution (sorted alphabetically)
        if 'scanType' in all_data.columns:
            scan_type_dist = all_data['scanType'].value_counts().to_dict()
            analysis['aggregated']['scan_types'] = dict(sorted(scan_type_dist.items(), key=lambda x: x[0].upper()))
            
            # Top projects by scan type (all, success, failed)
            analysis['aggregated']['projects_by_scan_type'] = {}
            analysis['aggregated']['projects_by_scan_type_success'] = {}
            analysis['aggregated']['projects_by_scan_type_failed'] = {}
            
            for scan_type in all_data['scanType'].unique():
                # All scans of this type
                scan_type_data = all_data[all_data['scanType'] == scan_type]
                top_projects = scan_type_data.groupby('projectName').size().nlargest(15).to_dict()
                analysis['aggregated']['projects_by_scan_type'][scan_type] = top_projects
                
                # Successful scans of this type
                if 'is_success' in all_data.columns:
                    success_scan_type_data = all_data[(all_data['scanType'] == scan_type) & (all_data['is_success'] == True)]
                    if len(success_scan_type_data) > 0:
                        top_projects_success = success_scan_type_data.groupby('projectName').size().nlargest(15).to_dict()
                        analysis['aggregated']['projects_by_scan_type_success'][scan_type] = top_projects_success
                
                # Failed scans of this type
                if 'is_failure' in all_data.columns:
                    failed_scan_type_data = all_data[(all_data['scanType'] == scan_type) & (all_data['is_failure'] == True)]
                    if len(failed_scan_type_data) > 0:
                        top_projects_failed = failed_scan_type_data.groupby('projectName').size().nlargest(15).to_dict()
                        analysis['aggregated']['projects_by_scan_type_failed'][scan_type] = top_projects_failed
        
        # Top projects by time block (all, success, failed)
        if 'hour_parsed' in all_data.columns and 'projectName' in all_data.columns:
            time_block_projects = calculate_projects_by_time_block(all_data)
            analysis['aggregated'].update(time_block_projects)
        
        # State distribution
        if 'state' in all_data.columns:
            state_dist = all_data['state'].value_counts().to_dict()
            analysis['aggregated']['states'] = state_dist
        
        # Top projects by scan count (overall, success, failed)
        top_projects_data = calculate_top_projects_by_status(all_data)
        analysis['aggregated'].update(top_projects_data)
    
    # Generate per-file statistics (only if multiple files)
    if len(dataframes) > 1:
        print("Analyzing individual files...")
        for filename, df in tqdm(dataframes.items(), desc="Analyzing files", unit="file"):
            # Apply same state classification to individual file data
            file_data = df.copy()
            if 'state' in file_data.columns:
                file_data['state_upper'] = file_data['state'].str.upper()
                file_data['is_success'] = file_data['state_upper'].isin([s.upper() for s in success_states])
                file_data['is_failure'] = file_data['state_upper'].isin([s.upper() for s in failure_states])
            
            file_stats = {
                'total_rows': len(file_data),
                'unique_projects': file_data['projectName'].nunique() if 'projectName' in file_data.columns else 0,
                'total_scans': len(file_data),
                'successful_scans': file_data['is_success'].sum() if 'is_success' in file_data.columns else 0,
                'failed_scans': file_data['is_failure'].sum() if 'is_failure' in file_data.columns else 0,
                'by_year': {},
                'by_project': {},
                'by_year_project': {}
            }
            # Add top projects (all, success, failed)
            top_projects_data = calculate_top_projects_by_status(file_data)
            file_stats.update(top_projects_data)
            # Add scan types (all, success, failed)
            scan_types_data = calculate_scan_types_by_status(file_data)
            file_stats.update(scan_types_data)
            
            # Calculate busiest/quietest hours for this file if hour data exists
            if 'hour' in file_data.columns:
                if 'hour_parsed' not in file_data.columns:
                    file_data['hour_parsed'] = pd.to_datetime(file_data['hour'])
                busy_quiet = calculate_busy_quiet_hours(file_data)
                copy_busy_quiet_metrics(file_stats, busy_quiet)
            
            # Generate year-based statistics for this file
            if 'hour' in file_data.columns:
                try:
                    file_data['hour_parsed'] = pd.to_datetime(file_data['hour'])
                    file_data['year'] = file_data['hour_parsed'].dt.year
                    file_years = sorted(file_data['year'].unique().tolist())
                    
                    for year in file_years:
                        year_data = file_data[file_data['year'] == year]
                        year_stats = {
                            'total_rows': len(year_data),
                            'unique_projects': year_data['projectName'].nunique() if 'projectName' in year_data.columns else 0,
                            'total_scans': len(year_data),
                            'successful_scans': year_data['is_success'].sum() if 'is_success' in year_data.columns else 0,
                            'failed_scans': year_data['is_failure'].sum() if 'is_failure' in year_data.columns else 0
                        }
                        # Add top projects (all, success, failed)
                        top_projects_data = calculate_top_projects_by_status(year_data)
                        year_stats.update(top_projects_data)
                        # Add scan types (all, success, failed)
                        scan_types_data = calculate_scan_types_by_status(year_data)
                        year_stats.update(scan_types_data)
                        # Add busiest/quietest hours for this file+year combination
                        busy_quiet = calculate_busy_quiet_hours(year_data)
                        copy_busy_quiet_metrics(year_stats, busy_quiet)
                        file_stats['by_year'][str(year)] = year_stats
                except Exception as e:
                    pass
            
            # Generate project-based statistics for this file
            if 'projectName' in file_data.columns:
                file_projects = sorted([p for p in file_data['projectName'].unique().tolist() if pd.notna(p)])
                # Store available projects for this file
                file_stats['available_projects'] = file_projects
                
                for project in file_projects:
                    project_data = file_data[file_data['projectName'] == project]
                    project_stats = {
                        'total_scans': len(project_data),
                        'successful_scans': project_data['is_success'].sum() if 'is_success' in project_data.columns else 0,
                        'failed_scans': project_data['is_failure'].sum() if 'is_failure' in project_data.columns else 0
                    }
                    # Add scan types (all, success, failed)
                    scan_types_data = calculate_scan_types_by_status(project_data)
                    project_stats.update(scan_types_data)
                    # Add busiest/quietest hours for this file+project combination
                    if 'hour_parsed' in project_data.columns:
                        busy_quiet = calculate_busy_quiet_hours(project_data)
                        copy_busy_quiet_metrics(project_stats, busy_quiet)
                    file_stats['by_project'][project] = project_stats
                
                # Generate year+project combinations for this file
                if 'hour' in file_data.columns and 'year' in file_data.columns:
                    file_years = sorted(file_data['year'].unique().tolist())
                    for year in file_years:
                        if str(year) not in file_stats['by_year_project']:
                            file_stats['by_year_project'][str(year)] = {}
                        for project in file_projects:
                            if pd.notna(project):
                                year_project_data = file_data[(file_data['year'] == year) & (file_data['projectName'] == project)]
                                if len(year_project_data) > 0:
                                    year_project_stats = {
                                        'total_scans': len(year_project_data),
                                        'successful_scans': year_project_data['is_success'].sum() if 'is_success' in year_project_data.columns else 0,
                                        'failed_scans': year_project_data['is_failure'].sum() if 'is_failure' in year_project_data.columns else 0
                                    }
                                    # Add scan types (all, success, failed)
                                    scan_types_data = calculate_scan_types_by_status(year_project_data)
                                    year_project_stats.update(scan_types_data)
                                    # Add busiest/quietest hours for this file+year+project combination
                                    busy_quiet = calculate_busy_quiet_hours(year_project_data)
                                    copy_busy_quiet_metrics(year_project_stats, busy_quiet)
                                    file_stats['by_year_project'][str(year)][project] = year_project_stats
            
            analysis['by_file'][filename] = file_stats
    
    for filename, df in dataframes.items():
        # Limit preview to essential columns and fewer rows to reduce HTML size
        preview_cols = ['projectName', 'scanType', 'state', 'hour', 'scanCount'] if all([col in df.columns for col in ['projectName', 'scanType', 'state', 'hour', 'scanCount']]) else df.columns[:5]
        preview_df = df[preview_cols].head(5) if len(preview_cols) > 0 else df.head(5)
        
        file_info = {
            'name': filename,
            'rows': len(df),
            'columns': list(df.columns),
            'column_count': len(df.columns),
            'dtypes': df.dtypes.astype(str).to_dict(),
            'preview': preview_df.to_dict('records'),
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
        
        # Use pre-computed success/failure flags
        if 'is_success' in all_data.columns:
            analysis['summary']['successful_scans'] = int(all_data['is_success'].sum())
            analysis['summary']['failed_scans'] = int(all_data['is_failure'].sum())
        else:
            analysis['summary']['successful_scans'] = 0
            analysis['summary']['failed_scans'] = 0
        
        # Calculate scan types for all scans, successful scans, and failed scans
        scan_types_data = calculate_scan_types_by_status(all_data)
        analysis['summary'].update(scan_types_data)
        
        # Calculate busiest/quietest hours for overall data
        if 'hour_parsed' in all_data.columns:
            busy_quiet = calculate_busy_quiet_hours(all_data)
            copy_busy_quiet_metrics(analysis['summary'], busy_quiet)
    
    return analysis


def aggregate_time_series(data, threshold=500):
    """
    Aggregate time series data if it exceeds threshold to reduce HTML size.
    For large datasets, group by day instead of hour.
    
    Args:
        data: DataFrame with 'hour' column
        threshold: Maximum number of data points before aggregation
        
    Returns:
        Aggregated data or original if below threshold
    """
    if len(data) <= threshold:
        return data
    
    # Aggregate by date instead of hour
    data_copy = data.copy()
    data_copy['date'] = pd.to_datetime(data_copy['hour_parsed']).dt.date
    return data_copy.groupby('date', as_index=False).agg({
        'hour': 'first',  # Keep first hour of the day for display
        'hour_parsed': 'first'
    }).assign(**{col: data_copy.groupby('date')[col].sum() for col in data_copy.columns if col not in ['hour', 'hour_parsed', 'date', 'year']})


def generate_chart_data(dataframes, min_scans=10, skip_detailed=False):
    """
    Generate data for charts and trend visualization.
    
    Args:
        dataframes: Dictionary of DataFrames
        min_scans: Minimum number of scans for a project to be included in trend charts (default: 10)
        skip_detailed: Skip year+project combination charts to reduce file size (default: False)
        
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
        'scan_type_evolution_by_year_project': {},
        'by_file': {}  # Per-file chart data
    }
    
    # Combine all dataframes for aggregated charts
    all_data = pd.concat(dataframes.values(), ignore_index=True) if len(dataframes) > 0 else None
    
    if all_data is not None:
        # Add state classification columns for status filtering
        success_states = ['COMPLETED', 'SUCCESS', 'COMPLETE']
        failure_states = ['ERROR', 'FAILED', 'FAILURE', 'CANCELLED']
        
        if 'state' in all_data.columns:
            all_data['state_upper'] = all_data['state'].str.upper()
            all_data['is_success'] = all_data['state_upper'].isin([s.upper() for s in success_states])
            all_data['is_failure'] = all_data['state_upper'].isin([s.upper() for s in failure_states])
        
        # Time-based trends if hour column exists
        if 'hour' in all_data.columns:
            # Initialize variables to avoid scope issues
            available_years = []
            all_projects = []
            year_groups = None
            project_groups = None
            year_project_groups = None
            
            try:
                # Parse hour column and sort - do this ONCE
                print("Parsing time data...")
                # Check if we already have hour_parsed and year from analysis phase
                if 'hour_parsed' not in all_data.columns:
                    all_data['hour_parsed'] = pd.to_datetime(all_data['hour'])
                if 'year' not in all_data.columns:
                    all_data['year'] = all_data['hour_parsed'].dt.year
                    
                all_data_sorted = all_data.sort_values('hour_parsed')
                
                # Helper function to generate time series for a dataset (now uses already sorted data)
                def generate_time_series_for_data(data_sorted, status_filter=None):
                    """
                    Generate time series data for charts.
                    
                    Args:
                        data_sorted: Pre-sorted DataFrame
                        status_filter: 'success', 'failed', or None for all scans
                    """
                    # Apply status filter if specified
                    if status_filter == 'success' and 'is_success' in data_sorted.columns:
                        data_sorted = data_sorted[data_sorted['is_success'] == True]
                    elif status_filter == 'failed' and 'is_failure' in data_sorted.columns:
                        data_sorted = data_sorted[data_sorted['is_failure'] == True]
                    
                    if len(data_sorted) == 0:
                        return []
                    
                    series_list = []
                    # Number of scans over time (count of records per hour)
                    time_trend = data_sorted.groupby('hour', sort=False).size().reset_index(name='count')
                    
                    # Sample data if too many points (> 200) to reduce HTML size
                    if len(time_trend) > 200:
                        # Keep every nth point to get approximately 200 points
                        step = len(time_trend) // 200
                        time_trend = time_trend.iloc[::step]
                    
                    series_list.append({
                        'name': 'Number of Scans Over Time',
                        'x': time_trend['hour'].tolist(),
                        'y': time_trend['count'].tolist(),
                        'type': 'scatter'
                    })
                    
                    # Total scan size over time
                    if 'totalScanSize' in data_sorted.columns:
                        size_trend = data_sorted.groupby('hour', sort=False)['totalScanSize'].sum().reset_index()
                        
                        # Sample data if too many points
                        if len(size_trend) > 1000:
                            step = len(size_trend) // 1000
                            size_trend = size_trend.iloc[::step]
                        
                        series_list.append({
                            'name': 'Total Scan Size Over Time',
                            'x': size_trend['hour'].tolist(),
                            'y': size_trend['totalScanSize'].tolist(),
                            'type': 'scatter'
                        })
                    return series_list
                
                # Generate time series for all data (all, success, failed)
                charts['time_series'] = generate_time_series_for_data(all_data_sorted)
                charts['time_series_success'] = generate_time_series_for_data(all_data_sorted, 'success')
                charts['time_series_failed'] = generate_time_series_for_data(all_data_sorted, 'failed')
                
                # Optimized: Use groupby instead of filtering multiple times
                available_years = sorted(all_data['year'].unique().tolist())
                year_groups = all_data_sorted.groupby('year', sort=False)
                
                print("Generating charts by year...")
                for year in tqdm(available_years, desc="Charts by year", unit="year"):
                    year_data_sorted = year_groups.get_group(year)
                    year_key = str(year)
                    charts['time_series_by_year'][year_key] = {}
                    charts['time_series_by_year'][year_key]['time_series'] = generate_time_series_for_data(year_data_sorted)
                    charts['time_series_by_year'][year_key]['time_series_success'] = generate_time_series_for_data(year_data_sorted, 'success')
                    charts['time_series_by_year'][year_key]['time_series_failed'] = generate_time_series_for_data(year_data_sorted, 'failed')
                
                # Generate time series by project - use groupby to avoid repeated filtering
                if 'projectName' in all_data.columns:
                    all_projects = sorted([p for p in all_data['projectName'].unique().tolist() if pd.notna(p)])
                    project_groups = all_data_sorted.groupby('projectName', sort=False)
                    
                    # Filter projects by minimum scan count
                    project_scan_counts = all_data.groupby('projectName').size()
                    projects_for_charts = [p for p in all_projects if project_scan_counts.get(p, 0) >= min_scans]
                    
                    if len(projects_for_charts) < len(all_projects):
                        print(f"  Filtered to {len(projects_for_charts)}/{len(all_projects)} projects with >= {min_scans} scans")
                    else:
                        print(f"  All {len(all_projects)} projects have >= {min_scans} scans")
                    
                    # Generate charts by project
                    print("Generating charts by project...")
                    for project in tqdm(projects_for_charts, desc="Charts by project", unit="project"):
                        if pd.notna(project) and project in project_groups.groups:
                            project_data_sorted = project_groups.get_group(project)
                            charts['time_series_by_project'][project] = {}
                            charts['time_series_by_project'][project]['time_series'] = generate_time_series_for_data(project_data_sorted)
                            charts['time_series_by_project'][project]['time_series_success'] = generate_time_series_for_data(project_data_sorted, 'success')
                            charts['time_series_by_project'][project]['time_series_failed'] = generate_time_series_for_data(project_data_sorted, 'failed')
                    
                    # Generate time series by year+project - only if not skipping detailed charts
                    if not skip_detailed:
                        print("Generating charts by year-project combinations...")
                        year_project_groups = all_data_sorted.groupby(['year', 'projectName'], sort=False)
                    
                        total_combinations = len(available_years) * len(projects_for_charts)
                        with tqdm(total=total_combinations, desc="Year-project charts", unit="combo") as pbar:
                            for year in available_years:
                                for project in projects_for_charts:
                                    if pd.notna(project):
                                        try:
                                            year_project_data_sorted = year_project_groups.get_group((year, project))
                                            if len(year_project_data_sorted) > 0:
                                                if str(year) not in charts['time_series_by_year_project']:
                                                    charts['time_series_by_year_project'][str(year)] = {}
                                                charts['time_series_by_year_project'][str(year)][project] = generate_time_series_for_data(year_project_data_sorted)
                                        except KeyError:
                                            pass
                                        pbar.update(1)
                    else:
                        print("Skipping year-project combinations to reduce file size")
                def generate_scan_type_evolution(data_sorted, status_filter=None):
                    """
                    Generate scan type evolution data for charts.
                    
                    Args:
                        data_sorted: Pre-sorted DataFrame
                        status_filter: 'success', 'failed', or None for all scans
                    """
                    # Apply status filter if specified
                    if status_filter == 'success' and 'is_success' in data_sorted.columns:
                        data_sorted = data_sorted[data_sorted['is_success'] == True]
                    elif status_filter == 'failed' and 'is_failure' in data_sorted.columns:
                        data_sorted = data_sorted[data_sorted['is_failure'] == True]
                    
                    if len(data_sorted) == 0:
                        return {}
                    
                    evolution = {}
                    if 'scanType' in data_sorted.columns and 'hour' in data_sorted.columns:
                        # Group by scanType and hour to get counts
                        for scan_type in data_sorted['scanType'].unique():
                            if pd.notna(scan_type):
                                scan_type_data = data_sorted[data_sorted['scanType'] == scan_type]
                                time_trend = scan_type_data.groupby('hour', sort=False).size().reset_index(name='count')
                                
                                # Sample data if too many points (> 100 per scan type)
                                if len(time_trend) > 100:
                                    step = len(time_trend) // 100
                                    time_trend = time_trend.iloc[::step]
                                
                                evolution[scan_type] = {
                                    'x': time_trend['hour'].tolist(),
                                    'y': time_trend['count'].tolist()
                                }
                    return evolution
                
                # Scan type evolution over time - all data (all, success, failed)
                print("Generating scan type evolution charts...")
                charts['scan_type_evolution'] = generate_scan_type_evolution(all_data_sorted)
                charts['scan_type_evolution_success'] = generate_scan_type_evolution(all_data_sorted, 'success')
                charts['scan_type_evolution_failed'] = generate_scan_type_evolution(all_data_sorted, 'failed')
                
                # Scan type evolution by year - use pre-computed groups
                for year in tqdm(available_years, desc="Scan type by year", unit="year"):
                    year_data_sorted = year_groups.get_group(year)
                    year_key = str(year)
                    charts['scan_type_evolution_by_year'][year_key] = {}
                    charts['scan_type_evolution_by_year'][year_key]['scan_type_evolution'] = generate_scan_type_evolution(year_data_sorted)
                    charts['scan_type_evolution_by_year'][year_key]['scan_type_evolution_success'] = generate_scan_type_evolution(year_data_sorted, 'success')
                    charts['scan_type_evolution_by_year'][year_key]['scan_type_evolution_failed'] = generate_scan_type_evolution(year_data_sorted, 'failed')
                
                # Scan type evolution by project - use pre-computed groups
                if 'projectName' in all_data.columns:
                    for project in tqdm(projects_for_charts, desc="Scan type by project", unit="project"):
                        if pd.notna(project) and project in project_groups.groups:
                            project_data_sorted = project_groups.get_group(project)
                            charts['scan_type_evolution_by_project'][project] = {}
                            charts['scan_type_evolution_by_project'][project]['scan_type_evolution'] = generate_scan_type_evolution(project_data_sorted)
                            charts['scan_type_evolution_by_project'][project]['scan_type_evolution_success'] = generate_scan_type_evolution(project_data_sorted, 'success')
                            charts['scan_type_evolution_by_project'][project]['scan_type_evolution_failed'] = generate_scan_type_evolution(project_data_sorted, 'failed')
                    
                    # Scan type evolution by year+project - only if not skipping detailed charts
                    if not skip_detailed:
                        total_combinations = len(available_years) * len(projects_for_charts)
                        with tqdm(total=total_combinations, desc="Scan type year-project", unit="combo") as pbar:
                            for year in available_years:
                                for project in projects_for_charts:
                                    if pd.notna(project):
                                        try:
                                            year_project_data_sorted = year_project_groups.get_group((year, project))
                                            if len(year_project_data_sorted) > 0:
                                                if str(year) not in charts['scan_type_evolution_by_year_project']:
                                                    charts['scan_type_evolution_by_year_project'][str(year)] = {}
                                                charts['scan_type_evolution_by_year_project'][str(year)][project] = generate_scan_type_evolution(year_project_data_sorted)
                                        except KeyError:
                                            pass
                                        pbar.update(1)
                    else:
                        print("Skipping year-project scan type evolution to reduce file size")
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
    
    # Generate per-file chart data (only if multiple files)
    if len(dataframes) > 1:
        print("Generating per-file chart data...")
        for filename, df in tqdm(dataframes.items(), desc="File charts", unit="file"):
            file_charts = {
                'time_series': [],
                'scan_type_evolution': {}
            }
            
            # Only generate if file has time data
            if 'hour' in df.columns:
                try:
                    # Parse time data for this file
                    file_data = df.copy()
                    if 'hour_parsed' not in file_data.columns:
                        file_data['hour_parsed'] = pd.to_datetime(file_data['hour'])
                    file_data_sorted = file_data.sort_values('hour_parsed')
                    
                    # Generate time series for this file
                    def generate_file_time_series(data_sorted):
                        series_list = []
                        time_trend = data_sorted.groupby('hour', sort=False).size().reset_index(name='count')
                        
                        if len(time_trend) > 1000:
                            step = len(time_trend) // 1000
                            time_trend = time_trend.iloc[::step]
                        
                        series_list.append({
                            'name': 'Number of Scans Over Time',
                            'x': time_trend['hour'].tolist(),
                            'y': time_trend['count'].tolist(),
                            'type': 'scatter'
                        })
                        
                        if 'totalScanSize' in data_sorted.columns:
                            size_trend = data_sorted.groupby('hour', sort=False)['totalScanSize'].sum().reset_index()
                            
                            if len(size_trend) > 1000:
                                step = len(size_trend) // 1000
                                size_trend = size_trend.iloc[::step]
                            
                            series_list.append({
                                'name': 'Total Scan Size Over Time',
                                'x': size_trend['hour'].tolist(),
                                'y': size_trend['totalScanSize'].tolist(),
                                'type': 'scatter'
                            })
                        return series_list
                    
                    file_charts['time_series'] = generate_file_time_series(file_data_sorted)
                    
                    # Generate scan type evolution for this file
                    if 'scanType' in file_data.columns:
                        for scan_type in file_data_sorted['scanType'].unique():
                            if pd.notna(scan_type):
                                scan_type_data = file_data_sorted[file_data_sorted['scanType'] == scan_type]
                                time_trend = scan_type_data.groupby('hour', sort=False).size().reset_index(name='count')
                                
                                if len(time_trend) > 500:
                                    step = len(time_trend) // 500
                                    time_trend = time_trend.iloc[::step]
                                
                                file_charts['scan_type_evolution'][scan_type] = {
                                    'x': time_trend['hour'].tolist(),
                                    'y': time_trend['count'].tolist()
                                }
                except Exception as e:
                    print(f"Warning: Could not generate charts for file {filename}: {e}")
            
            charts['by_file'][filename] = file_charts
    
    return charts


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy and pandas types."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return super().default(obj)


def convert_to_json_serializable(obj):
    """
    Recursively convert numpy/pandas types to native Python types.
    """
    if isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj


def generate_html_report(analysis, chart_data, output_path, min_scans=10):
    """
    Generate HTML reports using Jinja2 templates.
    Creates both a full report (with filters) and a simplified report (without filters).
    
    Args:
        analysis: Analysis results
        chart_data: Chart data
        output_path: Path to save the HTML report
        min_scans: Minimum number of scans threshold for including projects in charts
    """
    # Convert all numpy/pandas types to native Python types for JSON serialization
    analysis = convert_to_json_serializable(analysis)
    chart_data = convert_to_json_serializable(chart_data)
    
    # Generate the full report with filters
    try:
        template_path = files('blackduck_metrics').joinpath('templates/template.html')
        template_content = template_path.read_text(encoding='utf-8')
    except:
        # Fallback to file path (for development)
        template_path = Path(__file__).parent / 'templates' / 'template.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    
    template = Template(template_content)
    
    # Monkey-patch json.dumps to handle Undefined objects
    original_dumps = json.dumps
    json.dumps = lambda obj, **kw: original_dumps(obj, cls=UndefinedSafeJSONEncoder, **kw)
    
    html_content = template.render(
        analysis=analysis,
        chart_data=chart_data,
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        min_scans=min_scans
    )
    
    # Restore original json.dumps
    json.dumps = original_dumps
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Get file size
    file_size = Path(output_path).stat().st_size
    if file_size > 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{file_size / 1024:.2f} KB"
    
    print(f"\n[SUCCESS] Full HTML report (with filters) generated: {output_path} ({size_str})")
    
    # Generate the simplified report without filters
    try:
        template_simple_path = files('blackduck_metrics').joinpath('templates/template_simple.html')
        template_simple_content = template_simple_path.read_text(encoding='utf-8')
    except:
        # Fallback to file path (for development)
        template_simple_path = Path(__file__).parent / 'templates' / 'template_simple.html'
        try:
            with open(template_simple_path, 'r', encoding='utf-8') as f:
                template_simple_content = f.read()
        except FileNotFoundError:
            print(f"⚠️ Warning: Simplified template not found, skipping simple report generation")
            return
    
    template_simple = Template(template_simple_content)
    
    # Monkey-patch json.dumps again for simple template
    json.dumps = lambda obj, **kw: original_dumps(obj, cls=UndefinedSafeJSONEncoder, **kw)
    
    html_simple_content = template_simple.render(
        analysis=analysis,
        chart_data=chart_data,
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        min_scans=min_scans
    )
    
    # Restore original json.dumps
    json.dumps = original_dumps
    
    # Create simple report filename by inserting '_simple' before .html
    output_path_obj = Path(output_path)
    simple_output_path = output_path_obj.parent / f"{output_path_obj.stem}_simple{output_path_obj.suffix}"
    
    with open(simple_output_path, 'w', encoding='utf-8') as f:
        f.write(html_simple_content)
    
    # Get file size
    file_size_simple = Path(simple_output_path).stat().st_size
    if file_size_simple > 1024 * 1024:
        size_str_simple = f"{file_size_simple / (1024 * 1024):.2f} MB"
    else:
        size_str_simple = f"{file_size_simple / 1024:.2f} KB"
    
    print(f"[SUCCESS] Simple HTML report (no filters) generated: {simple_output_path} ({size_str_simple})")
    print(f"Report size: {size_str}")
