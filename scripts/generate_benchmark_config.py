#!/usr/bin/env python3
import os
import yaml
import re
from pathlib import Path



def fix_existing_task_files(task_dir='conf/task'):
    """
    Scan task files for space issues in the name field and fix them.
    """
    fixed_files = 0
    
    for file in os.listdir(task_dir):
        if file.endswith('.yaml'):
            file_path = os.path.join(task_dir, file)
        
            # Read the file
            with open(file_path, 'r') as f:
                content = f.read()
                yaml_content = yaml.safe_load(content)
            
            # Check if the name has spaces
            if 'name' in yaml_content and ' ' in yaml_content['name']:
                # Fix the name
                old_name = yaml_content['name']
                new_name = old_name.replace(' ', '')
                
                # Replace in the content string to preserve formatting
                updated_content = content.replace(f"name: {old_name}", f"name: {new_name}")
                
                # Write back to the file
                with open(file_path, 'w') as f:
                    f.write(updated_content)
                
                fixed_files += 1

    
    return fixed_files

def generate_benchmark_config():
    """
    Scan for task configurations and generate a benchmark YAML file that includes all tasks.
    """
    # First fix any existing task files with spaces in names
    fix_existing_task_files()
    
    # Load the template benchmark config
    benchmark_template_path = 'conf/benchmark/nudgingarena_tiny.yaml'
    output_path = 'conf/benchmark/nudgingarena_all_tasks.yaml'
    
    with open(benchmark_template_path, 'r') as f:
        benchmark_config = yaml.safe_load(f)
    
    # Default task entry template
    task_entry_template = {
        'task_seed': 0,
        'max_steps': 6,
        'headless': True,
        'record_video': False,
        'wait_for_user_message': False,
        'viewport': None,
        'slow_mo': None,
        'storage_state': None,
        'task_kwargs': None
    }
    
    # Find all task YAML files
    task_dir = 'conf/task'
    env_args_list = []
    
    # Skip these task files (they're template files)
    exclude_files = ['bestseller_product.yaml', 'default.yaml']
    
    # Scan the directory for task files
    for file in os.listdir(task_dir):
        if file.endswith('.yaml') and file not in exclude_files:

            # Load the task config to get the actual task name with proper case
            task_file_path = os.path.join(task_dir, file)
            with open(task_file_path, 'r') as f:
                task_config = yaml.safe_load(f)
            
            # Get the task name from the config
            if 'name' in task_config:
                task_name = task_config['name']

                # Use the name from the config for environment registration
                env_id = task_name.replace(' ', '')
                
                task_entry = {
                    'task_name': f'nudgingarena.{env_id}',
                    **task_entry_template
                }
                env_args_list.append(task_entry)
                print(f"task_name: {task_name} → {env_id} (task: {file})")



    benchmark_config['env_args_list'] = env_args_list
    
    if 'task_metadata' in benchmark_config and 'data' in benchmark_config['task_metadata']:
        benchmark_config['task_metadata']['data'] = []
        
        for task_entry in env_args_list:
            task_name = task_entry['task_name']
            benchmark_config['task_metadata']['data'].append({
                'task_name': task_name,
                'task_category': 'shopping',
                'browsergym_split': 'train'
            })
    
    with open(output_path, 'w') as f:
        yaml.dump(benchmark_config, f, default_flow_style=False)
    
    print(f"\nGenerated benchmark config with {len(env_args_list)} tasks: {output_path}")


if __name__ == '__main__':
    generate_benchmark_config() 