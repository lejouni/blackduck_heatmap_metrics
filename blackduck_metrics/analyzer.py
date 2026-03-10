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


def _top_projects_by_scan_count(df, n=15):
    """Return top-n projects ranked by total scan count (sum of scanCount column).
    Falls back to row count if scanCount column is absent.
    """
    if 'scanCount' in df.columns:
        return df.groupby('projectName')['scanCount'].sum().nlargest(n).to_dict()
    return df.groupby('projectName').size().nlargest(n).to_dict()


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
                top_projects = _top_projects_by_scan_count(block_data, n=10)
                result['projects_by_time_block'][time_block] = top_projects
        
        # Calculate for successful scans only
        if 'is_success' in data_copy.columns:
            success_data = data_copy[data_copy['is_success'] == True]
            for time_block in time_block_labels:
                block_data = success_data[success_data['time_block'] == time_block]
                if len(block_data) > 0:
                    top_projects = _top_projects_by_scan_count(block_data, n=10)
                    result['projects_by_time_block_success'][time_block] = top_projects
        
        # Calculate for failed scans only
        if 'is_failure' in data_copy.columns:
            failed_data = data_copy[data_copy['is_failure'] == True]
            for time_block in time_block_labels:
                block_data = failed_data[failed_data['time_block'] == time_block]
                if len(block_data) > 0:
                    top_projects = _top_projects_by_scan_count(block_data, n=10)
                    result['projects_by_time_block_failed'][time_block] = top_projects
    
    except Exception as e:
        print(f"Warning: Could not calculate projects by time block: {e}")
    
    return result


def calculate_projects_by_date(data):
    """
    Calculate top projects for each date.
    
    Args:
        data: DataFrame with 'hour_parsed' and 'projectName' columns, 
              optionally with 'is_success' and 'is_failure' columns
        
    Returns:
        dict: Dictionary with projects_by_date (formatted as YYYY-MM-DD), 
              projects_by_date_success, projects_by_date_failed, and available_dates (sorted list)
    """
    result = {
        'projects_by_date': {},
        'projects_by_date_success': {},
        'projects_by_date_failed': {},
        'available_dates': []
    }
    
    if data is None or len(data) == 0:
        return result
    
    if 'hour_parsed' not in data.columns or 'projectName' not in data.columns:
        return result
    
    try:
        # Extract date from hour_parsed
        data_copy = data.copy()
        data_copy['scan_date'] = data_copy['hour_parsed'].dt.date
        
        # Get all unique dates and sort them (most recent first)
        all_dates = sorted(data_copy['scan_date'].unique(), reverse=True)
        result['available_dates'] = [str(d) for d in all_dates]
        
        # OPTIMIZED: Pre-compute all date-project aggregations at once
        if 'scanCount' in data_copy.columns:
            date_project_counts = data_copy.groupby(['scan_date', 'projectName'])['scanCount'].sum()
        else:
            date_project_counts = data_copy.groupby(['scan_date', 'projectName']).size()
        
        # Build top projects per date from pre-computed data
        for scan_date in all_dates:
            if scan_date in date_project_counts.index:
                top_projects = date_project_counts.loc[scan_date].nlargest(15).to_dict()
                result['projects_by_date'][str(scan_date)] = top_projects
        
        # Calculate for successful scans only
        if 'is_success' in data_copy.columns:
            success_data = data_copy[data_copy['is_success'] == True]
            if len(success_data) > 0:
                if 'scanCount' in success_data.columns:
                    success_date_counts = success_data.groupby(['scan_date', 'projectName'])['scanCount'].sum()
                else:
                    success_date_counts = success_data.groupby(['scan_date', 'projectName']).size()
                
                for scan_date in all_dates:
                    if scan_date in success_date_counts.index:
                        top_projects = success_date_counts.loc[scan_date].nlargest(15).to_dict()
                        result['projects_by_date_success'][str(scan_date)] = top_projects
        
        # Calculate for failed scans only
        if 'is_failure' in data_copy.columns:
            failed_data = data_copy[data_copy['is_failure'] == True]
            if len(failed_data) > 0:
                if 'scanCount' in failed_data.columns:
                    failed_date_counts = failed_data.groupby(['scan_date', 'projectName'])['scanCount'].sum()
                else:
                    failed_date_counts = failed_data.groupby(['scan_date', 'projectName']).size()
                
                for scan_date in all_dates:
                    if scan_date in failed_date_counts.index:
                        top_projects = failed_date_counts.loc[scan_date].nlargest(15).to_dict()
                        result['projects_by_date_failed'][str(scan_date)] = top_projects
    
    except Exception as e:
        print(f"Warning: Could not calculate projects by date: {e}")
    
    return result


def calculate_projects_by_scan_type_and_date(data):
    """
    Calculate top projects for each combination of scan type and date.
    
    Args:
        data: DataFrame with 'hour_parsed', 'scanType', and 'projectName' columns,
              optionally with 'is_success' and 'is_failure' columns
        
    Returns:
        dict: Dictionary with projects_by_scan_type_and_date, 
              projects_by_scan_type_and_date_success, projects_by_scan_type_and_date_failed
              Format: {scan_type: {date: {project: count}}}
    """
    result = {
        'projects_by_scan_type_and_date': {},
        'projects_by_scan_type_and_date_success': {},
        'projects_by_scan_type_and_date_failed': {}
    }
    
    if data is None or len(data) == 0:
        return result
    
    if 'hour_parsed' not in data.columns or 'projectName' not in data.columns or 'scanType' not in data.columns:
        return result
    
    try:
        # Extract date from hour_parsed
        data_copy = data.copy()
        data_copy['scan_date'] = data_copy['hour_parsed'].dt.date
        
        # OPTIMIZED: Pre-compute all scanType-date-project aggregations at once
        if 'scanCount' in data_copy.columns:
            type_date_project_counts = data_copy.groupby(['scanType', 'scan_date', 'projectName'])['scanCount'].sum()
        else:
            type_date_project_counts = data_copy.groupby(['scanType', 'scan_date', 'projectName']).size()
        
        # Build nested dict from pre-computed data
        for (scan_type, scan_date), project_counts in type_date_project_counts.groupby(level=[0, 1]):
            if scan_type not in result['projects_by_scan_type_and_date']:
                result['projects_by_scan_type_and_date'][scan_type] = {}
            # Drop the first two index levels to get only projectName as key
            top_projects = project_counts.droplevel([0, 1]).nlargest(15).to_dict()
            result['projects_by_scan_type_and_date'][scan_type][str(scan_date)] = top_projects
        
        # Calculate for successful scans only
        if 'is_success' in data_copy.columns:
            success_data = data_copy[data_copy['is_success'] == True]
            if len(success_data) > 0:
                if 'scanCount' in success_data.columns:
                    success_type_date_counts = success_data.groupby(['scanType', 'scan_date', 'projectName'])['scanCount'].sum()
                else:
                    success_type_date_counts = success_data.groupby(['scanType', 'scan_date', 'projectName']).size()
                
                for (scan_type, scan_date), project_counts in success_type_date_counts.groupby(level=[0, 1]):
                    if scan_type not in result['projects_by_scan_type_and_date_success']:
                        result['projects_by_scan_type_and_date_success'][scan_type] = {}
                    # Drop the first two index levels to get only projectName as key
                    top_projects = project_counts.droplevel([0, 1]).nlargest(15).to_dict()
                    result['projects_by_scan_type_and_date_success'][scan_type][str(scan_date)] = top_projects
        
        # Calculate for failed scans only
        if 'is_failure' in data_copy.columns:
            failed_data = data_copy[data_copy['is_failure'] == True]
            if len(failed_data) > 0:
                if 'scanCount' in failed_data.columns:
                    failed_type_date_counts = failed_data.groupby(['scanType', 'scan_date', 'projectName'])['scanCount'].sum()
                else:
                    failed_type_date_counts = failed_data.groupby(['scanType', 'scan_date', 'projectName']).size()
                
                for (scan_type, scan_date), project_counts in failed_type_date_counts.groupby(level=[0, 1]):
                    if scan_type not in result['projects_by_scan_type_and_date_failed']:
                        result['projects_by_scan_type_and_date_failed'][scan_type] = {}
                    # Drop the first two index levels to get only projectName as key
                    top_projects = project_counts.droplevel([0, 1]).nlargest(15).to_dict()
                    result['projects_by_scan_type_and_date_failed'][scan_type][str(scan_date)] = top_projects
    
    except Exception as e:
        print(f"Warning: Could not calculate projects by scan type and date: {e}")
    
    return result


def calculate_scan_types_by_status(data):
    """
    Calculate scan type distributions for all scans, successful scans only, and failed scans only.
    Sums the scanCount column per scan type (falls back to row count if scanCount column is absent).
    
    Args:
        data: DataFrame with 'scanType' and 'scanCount' columns, and optionally 'is_success' and 'is_failure' columns
        
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
    
    # Calculate scan types for all scans - sum scanCount column (sorted alphabetically)
    if 'scanCount' in data.columns:
        scan_types_dict = data.groupby('scanType')['scanCount'].sum().to_dict()
    else:
        # Fallback to row count if scanCount column doesn't exist
        scan_types_dict = data['scanType'].value_counts().to_dict()
    result['scan_types'] = dict(sorted(scan_types_dict.items(), key=lambda x: x[0].upper()))
    
    # Calculate scan types for successful scans only (sorted alphabetically)
    if 'is_success' in data.columns:
        success_data = data[data['is_success'] == True]
        if len(success_data) > 0:
            if 'scanCount' in success_data.columns:
                success_dict = success_data.groupby('scanType')['scanCount'].sum().to_dict()
            else:
                success_dict = success_data['scanType'].value_counts().to_dict()
            result['scan_types_success'] = dict(sorted(success_dict.items(), key=lambda x: x[0].upper()))
    
    # Calculate scan types for failed scans only (sorted alphabetically)
    if 'is_failure' in data.columns:
        failed_data = data[data['is_failure'] == True]
        if len(failed_data) > 0:
            if 'scanCount' in failed_data.columns:
                failed_dict = failed_data.groupby('scanType')['scanCount'].sum().to_dict()
            else:
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
    
    # Calculate top projects for all scans (sum scanCount per project)
    result['top_projects'] = _top_projects_by_scan_count(data)
    
    # Calculate top projects for successful scans only
    if 'is_success' in data.columns:
        success_data = data[data['is_success'] == True]
        if len(success_data) > 0 and 'projectName' in success_data.columns:
            result['top_projects_success'] = _top_projects_by_scan_count(success_data)
    
    # Calculate top projects for failed scans only
    if 'is_failure' in data.columns:
        failed_data = data[data['is_failure'] == True]
        if len(failed_data) > 0 and 'projectName' in failed_data.columns:
            result['top_projects_failed'] = _top_projects_by_scan_count(failed_data)
    
    return result


def analyze_data(dataframes, start_year=None, end_year=None):
    """
    Analyze the data and prepare statistics for visualization.
    
    Args:
        dataframes: Dictionary of DataFrames
        start_year: Optional integer to filter data from this year onwards
        end_year: Optional integer to filter data up to and including this year
        
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
            'projects_by_date': {},
            'projects_by_date_success': {},
            'projects_by_date_failed': {},
            'available_dates': [],
            'projects_by_scan_type_and_date': {},
            'projects_by_scan_type_and_date_success': {},
            'projects_by_scan_type_and_date_failed': {},
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
    
    # Apply year filter if specified
    if all_data is not None and (start_year is not None or end_year is not None):
        if 'hour' in all_data.columns:
            all_data['year_temp'] = pd.to_datetime(all_data['hour']).dt.year
            rows_before = len(all_data)
            mask = pd.Series([True] * len(all_data), index=all_data.index)
            if start_year is not None:
                mask = mask & (all_data['year_temp'] >= start_year)
            if end_year is not None:
                mask = mask & (all_data['year_temp'] <= end_year)
            all_data = all_data[mask].copy()
            all_data = all_data.drop('year_temp', axis=1)
            rows_after = len(all_data)
            if rows_before > rows_after:
                range_desc = []
                if start_year:
                    range_desc.append(f">= {start_year}")
                if end_year:
                    range_desc.append(f"<= {end_year}")
                print(f"  Filtered to rows where year {' and '.join(range_desc)} ({rows_after}/{rows_before} rows kept)")
    
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
                    'total_scans': int(year_data['scanCount'].sum()) if 'scanCount' in year_data.columns else len(year_data),
                    'successful_scans': int(year_data[year_data['is_success'] == True]['scanCount'].sum()) if 'is_success' in year_data.columns and 'scanCount' in year_data.columns else (year_data['is_success'].sum() if 'is_success' in year_data.columns else 0),
                    'failed_scans': int(year_data[year_data['is_failure'] == True]['scanCount'].sum()) if 'is_failure' in year_data.columns and 'scanCount' in year_data.columns else (year_data['is_failure'].sum() if 'is_failure' in year_data.columns else 0)
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
        
        # Optimized: Pre-compute ALL project statistics using vectorized operations
        print("Analyzing projects...")
        
        # Pre-compute scan counts per project using vectorized groupby
        if 'scanCount' in all_data.columns:
            project_total_scans = all_data.groupby('projectName')['scanCount'].sum()
            
            # Pre-compute success/fail counts per project
            success_data = all_data[all_data['is_success'] == True] if 'is_success' in all_data.columns else pd.DataFrame()
            failure_data = all_data[all_data['is_failure'] == True] if 'is_failure' in all_data.columns else pd.DataFrame()
            
            if len(success_data) > 0 and 'scanCount' in success_data.columns:
                project_success_scans = success_data.groupby('projectName')['scanCount'].sum()
            else:
                project_success_scans = pd.Series(dtype=int)
            
            if len(failure_data) > 0 and 'scanCount' in failure_data.columns:
                project_failure_scans = failure_data.groupby('projectName')['scanCount'].sum()
            else:
                project_failure_scans = pd.Series(dtype=int)
            
            # Pre-compute scan types per project (vectorized)
            project_scan_types = all_data.groupby(['projectName', 'scanType'])['scanCount'].sum().sort_index()
            if len(success_data) > 0:
                project_scan_types_success = success_data.groupby(['projectName', 'scanType'])['scanCount'].sum().sort_index()
            else:
                project_scan_types_success = pd.Series(dtype=int)
            if len(failure_data) > 0:
                project_scan_types_failed = failure_data.groupby(['projectName', 'scanType'])['scanCount'].sum().sort_index()
            else:
                project_scan_types_failed = pd.Series(dtype=int)
        else:
            # Fallback to row counts
            project_total_scans = all_data.groupby('projectName').size()
            project_success_scans = all_data[all_data['is_success'] == True].groupby('projectName').size() if 'is_success' in all_data.columns else pd.Series(dtype=int)
            project_failure_scans = all_data[all_data['is_failure'] == True].groupby('projectName').size() if 'is_failure' in all_data.columns else pd.Series(dtype=int)
            project_scan_types = all_data.groupby(['projectName', 'scanType']).size().sort_index()
            project_scan_types_success = all_data[all_data['is_success'] == True].groupby(['projectName', 'scanType']).size().sort_index() if 'is_success' in all_data.columns else pd.Series(dtype=int)
            project_scan_types_failed = all_data[all_data['is_failure'] == True].groupby(['projectName', 'scanType']).size().sort_index() if 'is_failure' in all_data.columns else pd.Series(dtype=int)
        
        # Build project stats from pre-computed aggregations
        for project_name in tqdm(all_projects_list, desc="Analyzing projects", unit="project"):
            if pd.notna(project_name) and project_name in project_total_scans.index:
                # Get pre-computed values
                total_scans = int(project_total_scans.loc[project_name])
                successful_scans = int(project_success_scans.loc[project_name]) if project_name in project_success_scans.index else 0
                failed_scans = int(project_failure_scans.loc[project_name]) if project_name in project_failure_scans.index else 0
                
                # Build scan types dict from pre-computed multi-index series
                scan_types = {}
                scan_types_success = {}
                scan_types_failed = {}
                
                if project_name in project_scan_types.index:
                    for scan_type, count in project_scan_types.loc[project_name].items():
                        scan_types[scan_type] = int(count)
                
                if project_name in project_scan_types_success.index:
                    for scan_type, count in project_scan_types_success.loc[project_name].items():
                        scan_types_success[scan_type] = int(count)
                
                if project_name in project_scan_types_failed.index:
                    for scan_type, count in project_scan_types_failed.loc[project_name].items():
                        scan_types_failed[scan_type] = int(count)
                
                project_stats = {
                    'total_scans': total_scans,
                    'successful_scans': successful_scans,
                    'failed_scans': failed_scans,
                    'scan_types': dict(sorted(scan_types.items(), key=lambda x: x[0].upper())),
                    'scan_types_success': dict(sorted(scan_types_success.items(), key=lambda x: x[0].upper())),
                    'scan_types_failed': dict(sorted(scan_types_failed.items(), key=lambda x: x[0].upper()))
                }
                
                # Skip expensive busy/quiet hours calculation for individual projects (not critical for UI)
                # Can be re-enabled if needed, but adds significant processing time
                
                analysis['by_project'][project_name] = project_stats
        
        # Generate year+project combinations - fully vectorized
        if available_years and 'hour' in all_data.columns:
            print("Analyzing year-project combinations...")
            
            # Pre-compute ALL year-project statistics using vectorized operations
            if 'scanCount' in all_data.columns:
                # Create multi-index groupby for year and project
                yp_total = all_data.groupby(['year', 'projectName'])['scanCount'].sum()
                
                # Success/failure counts
                if 'is_success' in all_data.columns:
                    yp_success = all_data[all_data['is_success'] == True].groupby(['year', 'projectName'])['scanCount'].sum()
                    yp_failure = all_data[all_data['is_failure'] == True].groupby(['year', 'projectName'])['scanCount'].sum()
                else:
                    yp_success = pd.Series(dtype=int)
                    yp_failure = pd.Series(dtype=int)
                
                # Scan types per year-project
                yp_scan_types = all_data.groupby(['year', 'projectName', 'scanType'])['scanCount'].sum().sort_index()
                if 'is_success' in all_data.columns and len(all_data[all_data['is_success'] == True]) > 0:
                    yp_scan_types_success = all_data[all_data['is_success'] == True].groupby(['year', 'projectName', 'scanType'])['scanCount'].sum().sort_index()
                else:
                    yp_scan_types_success = pd.Series(dtype=int)
                if 'is_failure' in all_data.columns and len(all_data[all_data['is_failure'] == True]) > 0:
                    yp_scan_types_failed = all_data[all_data['is_failure'] == True].groupby(['year', 'projectName', 'scanType'])['scanCount'].sum().sort_index()
                else:
                    yp_scan_types_failed = pd.Series(dtype=int)
            else:
                # Fallback to row counts
                yp_total = all_data.groupby(['year', 'projectName']).size()
                yp_success = all_data[all_data['is_success'] == True].groupby(['year', 'projectName']).size() if 'is_success' in all_data.columns else pd.Series(dtype=int)
                yp_failure = all_data[all_data['is_failure'] == True].groupby(['year', 'projectName']).size() if 'is_failure' in all_data.columns else pd.Series(dtype=int)
                yp_scan_types = all_data.groupby(['year', 'projectName', 'scanType']).size().sort_index()
                yp_scan_types_success = all_data[all_data['is_success'] == True].groupby(['year', 'projectName', 'scanType']).size().sort_index() if 'is_success' in all_data.columns else pd.Series(dtype=int)
                yp_scan_types_failed = all_data[all_data['is_failure'] == True].groupby(['year', 'projectName', 'scanType']).size().sort_index() if 'is_failure' in all_data.columns else pd.Series(dtype=int)
            
            # Build the nested dict structure from pre-computed data
            for (year, project_name), total_scans in tqdm(yp_total.items(), total=len(yp_total), desc="Year-project analysis", unit="combo"):
                if pd.notna(project_name):
                    year_str = str(year)
                    if year_str not in analysis['by_year_project']:
                        analysis['by_year_project'][year_str] = {}
                    
                    # Get pre-computed values
                    successful_scans = int(yp_success.loc[(year, project_name)]) if (year, project_name) in yp_success.index else 0
                    failed_scans = int(yp_failure.loc[(year, project_name)]) if (year, project_name) in yp_failure.index else 0
                    
                    # Build scan types dicts from pre-computed multi-index series
                    scan_types = {}
                    scan_types_success = {}
                    scan_types_failed = {}
                    
                    if (year, project_name) in yp_scan_types.index:
                        for scan_type, count in yp_scan_types.loc[(year, project_name)].items():
                            scan_types[scan_type] = int(count)
                    
                    if (year, project_name) in yp_scan_types_success.index:
                        for scan_type, count in yp_scan_types_success.loc[(year, project_name)].items():
                            scan_types_success[scan_type] = int(count)
                    
                    if (year, project_name) in yp_scan_types_failed.index:
                        for scan_type, count in yp_scan_types_failed.loc[(year, project_name)].items():
                            scan_types_failed[scan_type] = int(count)
                    
                    project_year_stats = {
                        'total_scans': int(total_scans),
                        'successful_scans': successful_scans,
                        'failed_scans': failed_scans,
                        'scan_types': dict(sorted(scan_types.items(), key=lambda x: x[0].upper())),
                        'scan_types_success': dict(sorted(scan_types_success.items(), key=lambda x: x[0].upper())),
                        'scan_types_failed': dict(sorted(scan_types_failed.items(), key=lambda x: x[0].upper()))
                    }
                    
                    # Skip expensive busy/quiet hours calculation for year-project combos
                    
                    analysis['by_year_project'][year_str][project_name] = project_year_stats
        
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
                top_projects = _top_projects_by_scan_count(scan_type_data)
                analysis['aggregated']['projects_by_scan_type'][scan_type] = top_projects
                
                # Successful scans of this type
                if 'is_success' in all_data.columns:
                    success_scan_type_data = all_data[(all_data['scanType'] == scan_type) & (all_data['is_success'] == True)]
                    if len(success_scan_type_data) > 0:
                        top_projects_success = _top_projects_by_scan_count(success_scan_type_data)
                        analysis['aggregated']['projects_by_scan_type_success'][scan_type] = top_projects_success
                
                # Failed scans of this type
                if 'is_failure' in all_data.columns:
                    failed_scan_type_data = all_data[(all_data['scanType'] == scan_type) & (all_data['is_failure'] == True)]
                    if len(failed_scan_type_data) > 0:
                        top_projects_failed = _top_projects_by_scan_count(failed_scan_type_data)
                        analysis['aggregated']['projects_by_scan_type_failed'][scan_type] = top_projects_failed
        
        # Top projects by time block (all, success, failed)
        if 'hour_parsed' in all_data.columns and 'projectName' in all_data.columns:
            print("Calculating top projects by time block...")
            time_block_projects = calculate_projects_by_time_block(all_data)
            analysis['aggregated'].update(time_block_projects)
        
        # Top projects by date (all, success, failed)
        if 'hour_parsed' in all_data.columns and 'projectName' in all_data.columns:
            print("Calculating top projects by date...")
            date_projects = calculate_projects_by_date(all_data)
            analysis['aggregated'].update(date_projects)
        
        # Top projects by scan type AND date combined (all, success, failed)
        if 'hour_parsed' in all_data.columns and 'projectName' in all_data.columns and 'scanType' in all_data.columns:
            print("Calculating top projects by scan type and date...")
            scan_type_date_projects = calculate_projects_by_scan_type_and_date(all_data)
            analysis['aggregated'].update(scan_type_date_projects)
        
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
                'total_files': 1,
                'total_rows': len(file_data),
                'unique_projects': file_data['projectName'].nunique() if 'projectName' in file_data.columns else 0,
                'total_scans': int(file_data['scanCount'].sum()) if 'scanCount' in file_data.columns else len(file_data),
                'successful_scans': int(file_data[file_data['is_success'] == True]['scanCount'].sum()) if 'is_success' in file_data.columns and 'scanCount' in file_data.columns else (file_data['is_success'].sum() if 'is_success' in file_data.columns else 0),
                'failed_scans': int(file_data[file_data['is_failure'] == True]['scanCount'].sum()) if 'is_failure' in file_data.columns and 'scanCount' in file_data.columns else (file_data['is_failure'].sum() if 'is_failure' in file_data.columns else 0),
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
                            'total_scans': int(year_data['scanCount'].sum()) if 'scanCount' in year_data.columns else len(year_data),
                            'successful_scans': int(year_data[year_data['is_success'] == True]['scanCount'].sum()) if 'is_success' in year_data.columns and 'scanCount' in year_data.columns else (year_data['is_success'].sum() if 'is_success' in year_data.columns else 0),
                            'failed_scans': int(year_data[year_data['is_failure'] == True]['scanCount'].sum()) if 'is_failure' in year_data.columns and 'scanCount' in year_data.columns else (year_data['is_failure'].sum() if 'is_failure' in year_data.columns else 0)
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
                        'total_scans': int(project_data['scanCount'].sum()) if 'scanCount' in project_data.columns else len(project_data),
                        'successful_scans': int(project_data[project_data['is_success'] == True]['scanCount'].sum()) if 'is_success' in project_data.columns and 'scanCount' in project_data.columns else (project_data['is_success'].sum() if 'is_success' in project_data.columns else 0),
                        'failed_scans': int(project_data[project_data['is_failure'] == True]['scanCount'].sum()) if 'is_failure' in project_data.columns and 'scanCount' in project_data.columns else (project_data['is_failure'].sum() if 'is_failure' in project_data.columns else 0)
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
                                        'total_scans': int(year_project_data['scanCount'].sum()) if 'scanCount' in year_project_data.columns else len(year_project_data),
                                        'successful_scans': int(year_project_data[year_project_data['is_success'] == True]['scanCount'].sum()) if 'is_success' in year_project_data.columns and 'scanCount' in year_project_data.columns else (year_project_data['is_success'].sum() if 'is_success' in year_project_data.columns else 0),
                                        'failed_scans': int(year_project_data[year_project_data['is_failure'] == True]['scanCount'].sum()) if 'is_failure' in year_project_data.columns and 'scanCount' in year_project_data.columns else (year_project_data['is_failure'].sum() if 'is_failure' in year_project_data.columns else 0)
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
    analysis['summary']['total_rows'] = len(all_data) if all_data is not None else 0
    if all_data is not None:
        analysis['summary']['unique_projects'] = all_data['projectName'].nunique() if 'projectName' in all_data.columns else 0
        
        # Total scans: sum of scanCount column (fallback to row count if column doesn't exist)
        if 'scanCount' in all_data.columns:
            analysis['summary']['total_scans'] = int(all_data['scanCount'].sum())
        else:
            analysis['summary']['total_scans'] = len(all_data)
        
        # Use pre-computed success/failure flags and sum scanCount for each category
        if 'is_success' in all_data.columns and 'scanCount' in all_data.columns:
            analysis['summary']['successful_scans'] = int(all_data[all_data['is_success'] == True]['scanCount'].sum())
            analysis['summary']['failed_scans'] = int(all_data[all_data['is_failure'] == True]['scanCount'].sum())
        elif 'is_success' in all_data.columns:
            # Fallback to row count if scanCount column doesn't exist
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


def generate_chart_data(dataframes, min_scans=10, skip_detailed=False, max_projects=1000, start_year=None, end_year=None, capacity_sph=None, sph_warning_pct=80):
    """
    Generate data for charts and trend visualization.
    
    Args:
        dataframes: Dictionary of DataFrames
        min_scans: Minimum number of scans for a project to be included in trend charts (default: 10)
        skip_detailed: Skip year+project combination charts to reduce file size (default: False)
        max_projects: Maximum number of projects to include in per-project charts (default: 1000, 0 = unlimited)
        start_year: Optional integer; only include rows from this year onwards before generating charts
        end_year: Optional integer; only include rows up to and including this year before generating charts
        capacity_sph: Hosted environment capacity in Scans Per Hour (default: None)
        sph_warning_pct: Percentage of capacity_sph that triggers a warning (default: 80)
        
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
    
    # Apply year range filter to each individual dataframe so per-file loops also see filtered data
    if start_year is not None or end_year is not None:
        filtered_dataframes = {}
        for fname, df in dataframes.items():
            if 'hour' in df.columns:
                year_col = pd.to_datetime(df['hour'], errors='coerce').dt.year
                mask = pd.Series([True] * len(df), index=df.index)
                if start_year is not None:
                    mask = mask & (year_col >= start_year)
                if end_year is not None:
                    mask = mask & (year_col <= end_year)
                filtered_dataframes[fname] = df[mask].copy()
            else:
                filtered_dataframes[fname] = df
        dataframes = filtered_dataframes
        range_parts = []
        if start_year:
            range_parts.append(f"from {start_year}")
        if end_year:
            range_parts.append(f"up to {end_year}")
        print(f"  Chart data: using rows {' '.join(range_parts)} only")

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
                    # Number of scans over time (sum of scanCount per hour)
                    if 'scanCount' in data_sorted.columns:
                        time_trend = data_sorted.groupby('hour', sort=False)['scanCount'].sum().reset_index(name='count')
                    else:
                        time_trend = data_sorted.groupby('hour', sort=False).size().reset_index(name='count')
                    
                    # Sample data if too many points (> 100) to reduce HTML size
                    if len(time_trend) > 100:
                        # Keep every nth point to get approximately 100 points
                        step = len(time_trend) // 100
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
                        if len(size_trend) > 100:
                            step = len(size_trend) // 100
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
                    
                    # Filter projects by minimum scan count (use scanCount sum for consistency)
                    if 'scanCount' in all_data.columns:
                        project_scan_counts = all_data.groupby('projectName')['scanCount'].sum()
                    else:
                        project_scan_counts = all_data.groupby('projectName').size()
                    projects_for_charts = [p for p in all_projects if project_scan_counts.get(p, 0) >= min_scans]
                    
                    # Optional cap on number of projects to prevent browser performance issues
                    MAX_PROJECTS_FOR_CHARTS = max_projects if max_projects and max_projects > 0 else None
                    if MAX_PROJECTS_FOR_CHARTS and len(projects_for_charts) > MAX_PROJECTS_FOR_CHARTS:
                        # Sort by scan count descending and take top N
                        projects_with_counts = [(p, project_scan_counts.get(p, 0)) for p in projects_for_charts]
                        projects_with_counts.sort(key=lambda x: x[1], reverse=True)
                        projects_for_charts = [p for p, _ in projects_with_counts[:MAX_PROJECTS_FOR_CHARTS]]
                        print(f"  ⚠ Limiting to top {MAX_PROJECTS_FOR_CHARTS} projects (out of {len(all_projects)}) for browser performance")
                    
                    if len(projects_for_charts) < len(all_projects):
                        print(f"  Filtered to {len(projects_for_charts)}/{len(all_projects)} projects with >= {min_scans} scans")
                    else:
                        print(f"  All {len(all_projects)} projects have >= {min_scans} scans")
                    
                    # Generate charts by project - OPTIMIZED: Pre-compute all project-hour aggregations at once
                    print("Generating charts by project...")
                    
                    # Filter to only projects we want charts for
                    chart_data = all_data_sorted[all_data_sorted['projectName'].isin(projects_for_charts)]
                    
                    # Pre-compute time series aggregations for all projects at once (vectorized)
                    if 'scanCount' in chart_data.columns:
                        # All scans
                        project_hour_all = chart_data.groupby(['projectName', 'hour'], sort=False)['scanCount'].sum()
                        # Success scans
                        if 'is_success' in chart_data.columns:
                            success_chart_data = chart_data[chart_data['is_success'] == True]
                            project_hour_success = success_chart_data.groupby(['projectName', 'hour'], sort=False)['scanCount'].sum() if len(success_chart_data) > 0 else pd.Series(dtype=int)
                        else:
                            project_hour_success = pd.Series(dtype=int)
                        # Failed scans
                        if 'is_failure' in chart_data.columns:
                            failed_chart_data = chart_data[chart_data['is_failure'] == True]
                            project_hour_failed = failed_chart_data.groupby(['projectName', 'hour'], sort=False)['scanCount'].sum() if len(failed_chart_data) > 0 else pd.Series(dtype=int)
                        else:
                            project_hour_failed = pd.Series(dtype=int)
                    else:
                        # Fallback to row counts
                        project_hour_all = chart_data.groupby(['projectName', 'hour'], sort=False).size()
                        project_hour_success = chart_data[chart_data['is_success'] == True].groupby(['projectName', 'hour'], sort=False).size() if 'is_success' in chart_data.columns else pd.Series(dtype=int)
                        project_hour_failed = chart_data[chart_data['is_failure'] == True].groupby(['projectName', 'hour'], sort=False).size() if 'is_failure' in chart_data.columns else pd.Series(dtype=int)
                    
                    # Build chart data from pre-computed aggregations (fast dict lookups)
                    for project in tqdm(projects_for_charts, desc="Charts by project", unit="project"):
                        if pd.notna(project):
                            charts['time_series_by_project'][project] = {}
                            
                            # All scans time series
                            if project in project_hour_all.index:
                                time_data = project_hour_all.loc[project].reset_index()
                                time_data.columns = ['hour', 'count']
                                # Sample if too many points
                                if len(time_data) > 100:
                                    step = len(time_data) // 100
                                    time_data = time_data.iloc[::step]
                                charts['time_series_by_project'][project]['time_series'] = [{
                                    'name': 'Number of Scans Over Time',
                                    'x': time_data['hour'].tolist(),
                                    'y': time_data['count'].tolist(),
                                    'type': 'scatter'
                                }]
                            else:
                                charts['time_series_by_project'][project]['time_series'] = []
                            
                            # Success scans time series
                            if project in project_hour_success.index:
                                time_data = project_hour_success.loc[project].reset_index()
                                time_data.columns = ['hour', 'count']
                                if len(time_data) > 100:
                                    step = len(time_data) // 100
                                    time_data = time_data.iloc[::step]
                                charts['time_series_by_project'][project]['time_series_success'] = [{
                                    'name': 'Number of Scans Over Time',
                                    'x': time_data['hour'].tolist(),
                                    'y': time_data['count'].tolist(),
                                    'type': 'scatter'
                                }]
                            else:
                                charts['time_series_by_project'][project]['time_series_success'] = []
                            
                            # Failed scans time series
                            if project in project_hour_failed.index:
                                time_data = project_hour_failed.loc[project].reset_index()
                                time_data.columns = ['hour', 'count']
                                if len(time_data) > 100:
                                    step = len(time_data) // 100
                                    time_data = time_data.iloc[::step]
                                charts['time_series_by_project'][project]['time_series_failed'] = [{
                                    'name': 'Number of Scans Over Time',
                                    'x': time_data['hour'].tolist(),
                                    'y': time_data['count'].tolist(),
                                    'type': 'scatter'
                                }]
                            else:
                                charts['time_series_by_project'][project]['time_series_failed'] = []
                    
                    # Generate time series by year+project - OPTIMIZED: Pre-compute all year-project-hour aggregations
                    if not skip_detailed:
                        print("Generating charts by year-project combinations...")
                        
                        # Filter to only projects we want charts for
                        chart_data = all_data_sorted[all_data_sorted['projectName'].isin(projects_for_charts)]
                        
                        # Pre-compute ALL year-project-hour aggregations at once (vectorized)
                        if 'scanCount' in chart_data.columns:
                            yp_hour_all = chart_data.groupby(['year', 'projectName', 'hour'], sort=False)['scanCount'].sum()
                        else:
                            yp_hour_all = chart_data.groupby(['year', 'projectName', 'hour'], sort=False).size()
                        
                        # Build chart data from pre-computed aggregations
                        total_combinations = 0
                        for (year, project), time_data_series in tqdm(yp_hour_all.groupby(level=[0, 1]), desc="Year-project charts", unit="combo"):
                            if pd.notna(project):
                                year_str = str(year)
                                if year_str not in charts['time_series_by_year_project']:
                                    charts['time_series_by_year_project'][year_str] = {}
                                
                                # Convert to DataFrame for easier manipulation
                                time_data = time_data_series.reset_index(level=2)
                                time_data.columns = ['hour', 'count']
                                
                                # Sample if too many points
                                if len(time_data) > 100:
                                    step = len(time_data) // 100
                                    time_data = time_data.iloc[::step]
                                
                                charts['time_series_by_year_project'][year_str][project] = [{
                                    'name': 'Number of Scans Over Time',
                                    'x': time_data['hour'].tolist(),
                                    'y': time_data['count'].tolist(),
                                    'type': 'scatter'
                                }]
                                total_combinations += 1
                        
                        print(f"  Generated charts for {total_combinations} year-project combinations")
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
                                if 'scanCount' in scan_type_data.columns:
                                    time_trend = scan_type_data.groupby('hour', sort=False)['scanCount'].sum().reset_index(name='count')
                                else:
                                    time_trend = scan_type_data.groupby('hour', sort=False).size().reset_index(name='count')
                                
                                # Sample data if too many points (> 50 per scan type)
                                if len(time_trend) > 50:
                                    step = len(time_trend) // 50
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
                
                # Scan type evolution by project - OPTIMIZED: Pre-compute all project-scantype-hour aggregations
                if 'projectName' in all_data.columns and 'scanType' in all_data.columns:
                    print("Generating scan type evolution by project...")
                    
                    # Filter to only projects we want charts for
                    chart_data = all_data_sorted[all_data_sorted['projectName'].isin(projects_for_charts)]
                    
                    # Pre-compute scan type evolution for all projects at once (vectorized)
                    if 'scanCount' in chart_data.columns:
                        # All scans: group by project, scanType, hour
                        pst_all = chart_data.groupby(['projectName', 'scanType', 'hour'], sort=False)['scanCount'].sum().sort_index()
                        # Success scans
                        if 'is_success' in chart_data.columns:
                            success_chart_data = chart_data[chart_data['is_success'] == True]
                            pst_success = success_chart_data.groupby(['projectName', 'scanType', 'hour'], sort=False)['scanCount'].sum().sort_index() if len(success_chart_data) > 0 else pd.Series(dtype=int)
                        else:
                            pst_success = pd.Series(dtype=int)
                        # Failed scans
                        if 'is_failure' in chart_data.columns:
                            failed_chart_data = chart_data[chart_data['is_failure'] == True]
                            pst_failed = failed_chart_data.groupby(['projectName', 'scanType', 'hour'], sort=False)['scanCount'].sum().sort_index() if len(failed_chart_data) > 0 else pd.Series(dtype=int)
                        else:
                            pst_failed = pd.Series(dtype=int)
                    else:
                        # Fallback to row counts
                        pst_all = chart_data.groupby(['projectName', 'scanType', 'hour'], sort=False).size().sort_index()
                        pst_success = chart_data[chart_data['is_success'] == True].groupby(['projectName', 'scanType', 'hour'], sort=False).size().sort_index() if 'is_success' in chart_data.columns else pd.Series(dtype=int)
                        pst_failed = chart_data[chart_data['is_failure'] == True].groupby(['projectName', 'scanType', 'hour'], sort=False).size().sort_index() if 'is_failure' in chart_data.columns else pd.Series(dtype=int)
                    
                    # Build evolution data from pre-computed aggregations
                    for project in tqdm(projects_for_charts, desc="Scan type by project", unit="project"):
                        if pd.notna(project):
                            charts['scan_type_evolution_by_project'][project] = {}
                            
                            # All scans evolution
                            evolution_all = {}
                            if project in pst_all.index:
                                for scan_type in pst_all.loc[project].index.get_level_values(0).unique():
                                    scan_data = pst_all.loc[project, scan_type].reset_index()
                                    scan_data.columns = ['hour', 'count']
                                    # Sample if too many points
                                    if len(scan_data) > 50:
                                        step = len(scan_data) // 50
                                        scan_data = scan_data.iloc[::step]
                                    evolution_all[scan_type] = {
                                        'x': scan_data['hour'].tolist(),
                                        'y': scan_data['count'].tolist()
                                    }
                            charts['scan_type_evolution_by_project'][project]['scan_type_evolution'] = evolution_all
                            
                            # Success scans evolution
                            evolution_success = {}
                            if project in pst_success.index:
                                for scan_type in pst_success.loc[project].index.get_level_values(0).unique():
                                    scan_data = pst_success.loc[project, scan_type].reset_index()
                                    scan_data.columns = ['hour', 'count']
                                    if len(scan_data) > 50:
                                        step = len(scan_data) // 50
                                        scan_data = scan_data.iloc[::step]
                                    evolution_success[scan_type] = {
                                        'x': scan_data['hour'].tolist(),
                                        'y': scan_data['count'].tolist()
                                    }
                            charts['scan_type_evolution_by_project'][project]['scan_type_evolution_success'] = evolution_success
                            
                            # Failed scans evolution
                            evolution_failed = {}
                            if project in pst_failed.index:
                                for scan_type in pst_failed.loc[project].index.get_level_values(0).unique():
                                    scan_data = pst_failed.loc[project, scan_type].reset_index()
                                    scan_data.columns = ['hour', 'count']
                                    if len(scan_data) > 50:
                                        step = len(scan_data) // 50
                                        scan_data = scan_data.iloc[::step]
                                    evolution_failed[scan_type] = {
                                        'x': scan_data['hour'].tolist(),
                                        'y': scan_data['count'].tolist()
                                    }
                            charts['scan_type_evolution_by_project'][project]['scan_type_evolution_failed'] = evolution_failed
                    
                    # Scan type evolution by year+project - OPTIMIZED: Pre-compute all year-project-scantype-hour aggregations
                    if not skip_detailed:
                        print("Generating scan type evolution by year-project combinations...")
                        
                        # Filter to only projects we want charts for
                        chart_data = all_data_sorted[all_data_sorted['projectName'].isin(projects_for_charts)]
                        
                        # Pre-compute ALL year-project-scantype-hour aggregations at once (vectorized)
                        if 'scanCount' in chart_data.columns:
                            ypst_all = chart_data.groupby(['year', 'projectName', 'scanType', 'hour'], sort=False)['scanCount'].sum().sort_index()
                        else:
                            ypst_all = chart_data.groupby(['year', 'projectName', 'scanType', 'hour'], sort=False).size().sort_index()
                        
                        # Get unique year-project combinations that exist in the data
                        year_project_combos = ypst_all.index.droplevel([2, 3]).unique()
                        
                        # Build evolution data from pre-computed aggregations
                        total_combinations = 0
                        for year, project in tqdm(year_project_combos, desc="Scan type year-project", unit="combo"):
                            if pd.notna(project) and (year, project) in ypst_all.index:
                                year_str = str(year)
                                if year_str not in charts['scan_type_evolution_by_year_project']:
                                    charts['scan_type_evolution_by_year_project'][year_str] = {}
                                
                                # Get data for this year-project combination
                                yp_data = ypst_all.loc[(year, project)]
                                
                                # Get unique scan types
                                scan_types = yp_data.index.get_level_values(0).unique()
                                
                                evolution = {}
                                for scan_type in scan_types:
                                    scan_data = yp_data.loc[scan_type].reset_index()
                                    scan_data.columns = ['hour', 'count']
                                    
                                    # Sample if too many points
                                    if len(scan_data) > 50:
                                        step = len(scan_data) // 50
                                        scan_data = scan_data.iloc[::step]
                                    
                                    evolution[scan_type] = {
                                        'x': scan_data['hour'].tolist(),
                                        'y': scan_data['count'].tolist()
                                    }
                                
                                charts['scan_type_evolution_by_year_project'][year_str][project] = evolution
                                total_combinations += 1
                        
                        print(f"  Generated scan type evolution for {total_combinations} year-project combinations")
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
    if len(dataframes) > 0:
        print("Generating individual file trends...")
    for filename, df in tqdm(dataframes.items(), desc="File trends", unit="file", disable=len(dataframes) <= 1):
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
                    
                    # Generate scan type evolution for this file (OPTIMIZED: vectorized)
                    if 'scanType' in file_data.columns:
                        # Pre-compute all scan type evolution data at once
                        scan_type_hour_counts = file_data_sorted.groupby(['scanType', 'hour'], sort=False).size().reset_index(name='count')
                        
                        for scan_type in file_data_sorted['scanType'].unique():
                            if pd.notna(scan_type):
                                # Extract pre-computed data for this scan type
                                time_trend = scan_type_hour_counts[scan_type_hour_counts['scanType'] == scan_type][['hour', 'count']]
                                
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

    # Generate SPH (Scans Per Hour) license usage data from the combined dataset
    charts['sph'] = generate_sph_data(all_data, capacity_sph=capacity_sph, sph_warning_pct=sph_warning_pct)

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


def generate_sph_data(all_data, capacity_sph=None, sph_warning_pct=80):
    """
    Generate Scans Per Hour (SPH) data for capacity usage monitoring.

    Each CSV row represents a code-location scan entry for a given hour bucket.
    SPH for a given hour = sum of scanCount across all code locations in that hour.
    This is the correct metric for SPH-based Black Duck SCA licensing.

    Args:
        all_data: Combined DataFrame with 'hour' and 'scanCount' columns
        capacity_sph: Hosted environment SPH capacity ceiling, or None if not configured
        sph_warning_pct: Percentage of capacity_sph that triggers a warning (default 80)

    Returns:
        dict: SPH data including time series, flagged hours, and summary metrics,
              or None if required data is unavailable
    """
    if all_data is None or 'hour' not in all_data.columns:
        return None

    # Sum scanCount per hour bucket (use scanCount column; fall back to row count)
    if 'scanCount' in all_data.columns:
        hourly_sph = all_data.groupby('hour', sort=True)['scanCount'].sum().reset_index()
    else:
        hourly_sph = all_data.groupby('hour', sort=True).size().reset_index(name='scanCount')
    hourly_sph.columns = ['hour', 'sph']
    hourly_sph = hourly_sph.sort_values('hour').reset_index(drop=True)

    peak_sph = int(hourly_sph['sph'].max()) if len(hourly_sph) > 0 else 0

    # Compute thresholds
    _raw_warning = int(capacity_sph * sph_warning_pct / 100) if capacity_sph is not None else None
    # Only use warning threshold when it is strictly below the capacity ceiling;
    # if sph_warning_pct >= 100 the warning zone would be empty (every hour at
    # the threshold is already over capacity), so suppress it entirely.
    warning_threshold = _raw_warning if (_raw_warning is not None and _raw_warning < capacity_sph) else None

    # Flagged hours (>= warning threshold, or >= capacity_sph if no warning zone): include per-project breakdown
    flagged_hours = []
    if capacity_sph is not None:
        # Flag hours at or above the warning threshold (or over-capacity-only when no warning zone)
        effective_flag_threshold = warning_threshold if warning_threshold is not None else capacity_sph
        flag_mask = hourly_sph['sph'] >= effective_flag_threshold
        flagged_df = hourly_sph[flag_mask]

        if len(flagged_df) > 0:
            # OPTIMIZED: Pre-compute all hour-project breakdowns at once for flagged hours
            flagged_hour_vals = flagged_df['hour'].unique()
            flagged_data = all_data[all_data['hour'].isin(flagged_hour_vals)]
            
            # Pre-compute project breakdowns per hour
            if 'scanCount' in all_data.columns and 'projectName' in all_data.columns:
                hour_project_counts = flagged_data.groupby(['hour', 'projectName'])['scanCount'].sum()
            elif 'projectName' in all_data.columns:
                hour_project_counts = flagged_data.groupby(['hour', 'projectName']).size()
            else:
                hour_project_counts = pd.Series(dtype=int)
            
            # Pre-compute snippet percentages per hour
            snippet_data = {}
            if 'scanType' in all_data.columns:
                flagged_data['is_snippet'] = flagged_data['scanType'].str.upper().str.contains('SNIPPET', na=False)
                if 'scanCount' in all_data.columns:
                    hour_snippet_counts = flagged_data[flagged_data['is_snippet']].groupby('hour')['scanCount'].sum()
                else:
                    hour_snippet_counts = flagged_data[flagged_data['is_snippet']].groupby('hour').size()
                snippet_data = hour_snippet_counts.to_dict()

            for _, row in flagged_df.iterrows():
                hour_val = row['hour']
                sph_val = int(row['sph'])
                status = 'BREACH' if sph_val >= capacity_sph else 'WARNING'
                pct = round(sph_val / capacity_sph * 100, 1)

                # Extract pre-computed project breakdown for this hour
                try:
                    # Use .xs() for multi-index cross-section lookup
                    proj_series = hour_project_counts.xs(hour_val, level=0).sort_values(ascending=False).head(10)
                except (KeyError, AttributeError):
                    proj_series = pd.Series(dtype=int)

                # Extract pre-computed snippet percentage
                if sph_val > 0 and hour_val in snippet_data:
                    snippet_count = snippet_data[hour_val]
                    snippet_pct = round(snippet_count / sph_val * 100, 1)
                else:
                    snippet_pct = None

                flagged_hours.append({
                    'hour': str(hour_val),
                    'sph': sph_val,
                    'pct': pct,
                    'status': status,
                    'snippet_pct': snippet_pct,
                    'projects': {k: int(v) for k, v in proj_series.items()}
                })

            # Sort by SPH descending so worst offenders appear first
            flagged_hours.sort(key=lambda x: x['sph'], reverse=True)

    # Down-sample SPH series for chart display (max 500 points)
    step = max(1, len(hourly_sph) // 500)
    display_sph = hourly_sph.iloc[::step]
    sph_series = [
        {'hour': str(r['hour']), 'sph': int(r['sph'])}
        for _, r in display_sph.iterrows()
    ]

    breach_count = int((hourly_sph['sph'] >= capacity_sph).sum()) if capacity_sph is not None else 0
    warning_count = int(
        ((hourly_sph['sph'] >= warning_threshold) & (hourly_sph['sph'] < capacity_sph)).sum()
    ) if capacity_sph is not None else 0

    return {
        'capacity_sph': capacity_sph,
        'warning_pct': sph_warning_pct,
        'warning_threshold': warning_threshold,
        'peak_sph': peak_sph,
        'breach_count': breach_count,
        'warning_count': warning_count,
        'sph_series': sph_series,
        'flagged_hours': flagged_hours
    }


def generate_project_scan_counts_data(dataframes, start_year=None, end_year=None):
    """
    Generate project scan counts data for a dedicated report with filtering and sorting capabilities.
    
    This function aggregates scan count data by project, including scanType and date information,
    which can be filtered and sorted in the HTML report.
    
    Args:
        dataframes: Dictionary of DataFrames from CSV files
        start_year: Optional integer to filter data from this year onwards
        end_year: Optional integer to filter data up to and including this year
        
    Returns:
        tuple: (records, min_date, max_date) where:
            - records: List of dictionaries with project scan count details
            - min_date: Minimum date in the filtered data (YYYY-MM-DD) or None
            - max_date: Maximum date in the filtered data (YYYY-MM-DD) or None
    """
    if not dataframes or len(dataframes) == 0:
        return [], None, None
    
    print("  Combining dataframes...")
    # Combine all dataframes with progress bar
    all_data = pd.concat(
        list(tqdm(dataframes.values(), desc="  Processing CSV files", unit="file", leave=False)),
        ignore_index=True
    )
    
    # Check if required columns exist
    if 'projectName' not in all_data.columns:
        print("Warning: 'projectName' column not found in data")
        return [], None, None
    
    # Ensure scanCount column exists (use 1 if not present)
    if 'scanCount' not in all_data.columns:
        all_data['scanCount'] = 1
    
    # Parse datetime if hour column exists
    if 'hour' in all_data.columns:
        print("  Parsing dates...")
        try:
            all_data['hour_parsed'] = pd.to_datetime(all_data['hour'])
            
            # Apply year filter if specified
            if start_year is not None or end_year is not None:
                print("  Applying year filters...")
                all_data['year_temp'] = all_data['hour_parsed'].dt.year
                rows_before = len(all_data)
                mask = pd.Series([True] * len(all_data), index=all_data.index)
                if start_year is not None:
                    mask = mask & (all_data['year_temp'] >= start_year)
                if end_year is not None:
                    mask = mask & (all_data['year_temp'] <= end_year)
                all_data = all_data[mask].copy()
                all_data = all_data.drop('year_temp', axis=1)
                rows_after = len(all_data)
                if rows_before > rows_after:
                    range_desc = []
                    if start_year:
                        range_desc.append(f">= {start_year}")
                    if end_year:
                        range_desc.append(f"<= {end_year}")
                    print(f"    Filtered to rows where year {' and '.join(range_desc)} ({rows_after}/{rows_before} rows kept)")
            
            print("  Formatting dates...")
            all_data['scanDate'] = all_data['hour_parsed'].dt.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"Warning: Could not parse date from 'hour' column: {e}")
            all_data['scanDate'] = 'Unknown'
    else:
        all_data['scanDate'] = 'Unknown'
    
    # Ensure scanType exists
    if 'scanType' not in all_data.columns:
        all_data['scanType'] = 'Unknown'
    
    print("  Grouping data by project and date...")
    # Group by projectName, scanType, and scanDate, summing scanCount
    result_data = all_data[['projectName', 'scanType', 'scanDate', 'scanCount']].copy()
    result_data = result_data[result_data['projectName'].notna()]
    
    # Aggregate: sum scanCount for each combination of project, scanType, and date
    grouped_data = result_data.groupby(['projectName', 'scanType', 'scanDate'], as_index=False)['scanCount'].sum()
    
    # Collect scan type breakdown per project (for tooltips)
    print("  Calculating scan type breakdowns per project...")
    scan_type_data = all_data[['projectName', 'scanType', 'scanCount']].copy()
    scan_type_data = scan_type_data[scan_type_data['projectName'].notna()]
    
    # Use vectorized groupby instead of looping - much faster!
    scan_type_breakdown = scan_type_data.groupby(['projectName', 'scanType'])['scanCount'].sum().sort_index()
    
    # Convert to nested dictionary structure
    project_scan_types = {}
    for (project_name, scan_type), count in scan_type_breakdown.items():
        if project_name not in project_scan_types:
            project_scan_types[project_name] = []
        project_scan_types[project_name].append((scan_type, int(count)))
    
    # Sort each project's scan types by count (descending) then name (ascending)
    for project_name in project_scan_types:
        project_scan_types[project_name].sort(key=lambda x: (-x[1], x[0]))
    
    # Convert to list of dictionaries
    records = grouped_data.to_dict('records')
    
    # Convert types for JSON compatibility and add scan type breakdown
    print("  Converting data types and adding scan type breakdowns...")
    for record in tqdm(records, desc="  Processing records", unit="record", leave=False):
        if isinstance(record.get('scanCount'), (np.integer, np.int64)):
            record['scanCount'] = int(record['scanCount'])
        elif isinstance(record.get('scanCount'), (np.floating, np.float64)):
            record['scanCount'] = int(record['scanCount']) if not np.isnan(record['scanCount']) else 0
        
        # Add scan type breakdown for this project
        project_name = record.get('projectName')
        if project_name in project_scan_types:
            record['scanTypeBreakdown'] = project_scan_types[project_name]
        else:
            record['scanTypeBreakdown'] = []
    
    # Calculate min and max dates from the filtered data
    print("  Calculating date range...")
    min_date = None
    max_date = None
    if len(records) > 0:
        dates = [r['scanDate'] for r in records if r['scanDate'] != 'Unknown']
        if dates:
            dates.sort()
            min_date = dates[0]
            max_date = dates[-1]
    
    print(f"  ✓ Generated project scan counts data: {len(records)} records")
    if min_date and max_date:
        print(f"    Date range: {min_date} to {max_date}")
    
    return records, min_date, max_date


def generate_project_scan_counts_report(dataframes, output_path, project_group_name=None, start_year=None, end_year=None):
    """
    Generate HTML report for project scan counts with filtering and sorting.
    
    Args:
        dataframes: Dictionary of DataFrames from CSV files
        output_path: Path to save the HTML report
        project_group_name: Optional project group name to display in the report
        start_year: Optional integer to filter data from this year onwards
        end_year: Optional integer to filter data up to and including this year
    """
    # Generate scan counts data with year filtering
    scan_data, min_date, max_date = generate_project_scan_counts_data(dataframes, start_year, end_year)
    
    if not scan_data:
        print("Warning: No scan data available to generate report")
        return
    
    # Load template
    print("  Loading HTML template...")
    try:
        template_path = files('blackduck_metrics').joinpath('templates/template_project_scans.html')
        template_content = template_path.read_text(encoding='utf-8')
    except:
        # Fallback to file path (for development)
        template_path = Path(__file__).parent / 'templates' / 'template_project_scans.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    
    template = Template(template_content)
    
    # Render HTML with data
    print("  Rendering HTML report...")
    html_content = template.render(
        scan_data=scan_data,
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        project_group_name=project_group_name,
        min_date=min_date,
        max_date=max_date,
        start_year=start_year,
        end_year=end_year
    )
    
    # Write to file
    print("  Writing report to file...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Get file size
    file_size = Path(output_path).stat().st_size
    if file_size > 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{file_size / 1024:.2f} KB"
    
    print(f"  ✓ Report generated successfully ({size_str})")
    print(f"    {output_path}")


def generate_html_report(analysis, chart_data, output_path, min_scans=10, analysis_simple=None, chart_data_simple=None, project_group_name=None, simple_only=False):
    """
    Generate HTML report(s) using Jinja2 templates.
    
    Args:
        analysis: Analysis results for the full report
        chart_data: Chart data for the full report
        output_path: Path to save the HTML report
        min_scans: Minimum number of scans threshold for including projects in charts
        analysis_simple: Optional separate analysis for simple report (used when filtering by year)
        chart_data_simple: Optional separate chart data for simple report (used when filtering by year)
        project_group_name: Optional project group name to display in the report
        simple_only: If True, generate only simplified report; if False, generate only full report
    """
    # Convert all numpy/pandas types to native Python types for JSON serialization
    analysis = convert_to_json_serializable(analysis)
    chart_data = convert_to_json_serializable(chart_data)
    if analysis_simple is not None:
        analysis_simple = convert_to_json_serializable(analysis_simple)
    
    # Monkey-patch json.dumps to handle Undefined objects
    original_dumps = json.dumps
    json.dumps = lambda obj, **kw: original_dumps(obj, cls=UndefinedSafeJSONEncoder, **kw)
    
    if simple_only:
        # Generate ONLY the simplified report without filters
        try:
            template_path = files('blackduck_metrics').joinpath('templates/template_simple.html')
            template_content = template_path.read_text(encoding='utf-8')
        except:
            # Fallback to file path (for development)
            template_path = Path(__file__).parent / 'templates' / 'template_simple.html'
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        template = Template(template_content)
        
        # Use separate analysis and chart data for simple report if provided (e.g., when filtering by year)
        simple_analysis = analysis_simple if analysis_simple is not None else analysis
        simple_chart_data = chart_data_simple if chart_data_simple is not None else chart_data
        
        html_content = template.render(
            analysis=simple_analysis,
            chart_data=simple_chart_data,
            generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            min_scans=min_scans,
            project_group_name=project_group_name
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
        
        print(f"\n[SUCCESS] Simple HTML report (no filters) generated: {output_path} ({size_str})")
        return
    
    # Generate ONLY the full report with filters
    try:
        template_path = files('blackduck_metrics').joinpath('templates/template.html')
        template_content = template_path.read_text(encoding='utf-8')
    except:
        # Fallback to file path (for development)
        template_path = Path(__file__).parent / 'templates' / 'template.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    
    template = Template(template_content)
    
    html_content = template.render(
        analysis=analysis,
        chart_data=chart_data,
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        min_scans=min_scans,
        project_group_name=project_group_name
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
