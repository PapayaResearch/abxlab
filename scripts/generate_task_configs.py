import csv
import yaml
import os
import json
import argparse
from itertools import permutations, combinations

home_url = os.getenv('WA_SHOPPING')


def get_supported_nudges(intent: str, intents: list[dict[str, str]]) -> list[str]:
    for i in intents:
        if i['Intent'] == intent:
            return [n.strip() for n in i['Supported Nudges'].split(',')]
    raise ValueError(f"Intent '{intent}' not found in intents.csv")


def get_interventions_for_nudge(nudge: str, interventions: list[dict[str, str]]) -> list[dict[str, str]]:
    filtered_interventions = []

    for i in interventions:
        if i['Nudge'] == nudge:
            filtered_interventions.append(i)

    if not filtered_interventions:
        raise ValueError(f"Nudge '{nudge}' not found in interventions.csv")
    return filtered_interventions

def process_urls(urls_str: str) -> list[str]:
    # Remove quotes and split by comma
    urls = urls_str.strip('[]"').split(',')
    return [url.strip() for url in urls]

def generate_intents_from_template(template: str, intent_dict_str: str) -> list[str]:
    """Generate all possible intents from a template and its dictionary."""
    if not intent_dict_str:
        return [template]

    intent_dict = json.loads(intent_dict_str)
    generated_intents = [template]
    
    # For each variable in the dictionary, generate new intents
    for var, values in intent_dict.items():
        new_intents = []
        for intent in generated_intents:
            for value in values:
                new_intent = intent.replace(f"${{{var}}}", str(value))
                new_intents.append(new_intent)
        generated_intents = new_intents
    
    return generated_intents

def generate_task_configs(consider_order=True):
    """
    Generate task configurations.
    
    Args:
        consider_order: If True, consider the order of URLs in combinations (permutations).
                       If False, ignore order (combinations).
    """
    with open('tasks/intents.csv', newline='') as f1, \
     open('tasks/interventions.csv', newline='') as f2, \
     open('tasks/products.csv', newline='') as f3:
    
    
        intents = list(csv.DictReader(f1,quotechar='"', delimiter=',', skipinitialspace=True))
        interventions = list(csv.DictReader(f2,quotechar='"', delimiter=',', skipinitialspace=True))
        products = list(csv.DictReader(f3,quotechar='"', delimiter=',', skipinitialspace=True))

        task_counter = 1
        intent_template_counter = 1
        
        # TODO: Can be replaced with a default config
        with open('conf/task/test/bestseller_tabs.yaml', 'r') as config_file:
            base_config = yaml.safe_load(config_file)
        
        for intent in intents:
            intent_template = intent['Intent']
            intent_dict = intent['Intent Dictionary']
            starting_point = intent['Starting Point']
            
            # Generate all possible intents from the template
            generated_intents = generate_intents_from_template(intent_template, intent_dict)
            
            for generated_intent in generated_intents:
                supported_nudges = get_supported_nudges(intent_template, intents)
                
                if starting_point == 'Home':
                    start_urls = [home_url]
                    # TODO: Add evaluation URL and start_urls combinations from "product"

                elif starting_point == 'Browsing':
                    for product_index, product in enumerate(products, 1):
                        all_urls = process_urls(product['Start URLS'])
                        
                        # Only consider products with a single start URL
                        if len(all_urls) == 1:
                            # Determine all possible start_urls combinations for this product
                            start_urls_combinations = [all_urls]

                else:
                    assert starting_point == 'Product', f"Starting point '{starting_point}' not supported"
                    for product_index, product in enumerate(products, 1):
                        all_urls = process_urls(product['Start URLS'])
                        
                        if len(all_urls) > 1:
                            # Determine all possible start_urls combinations for this product
                            start_urls_combinations = []

                            # Generate all permutations or combinations of length 2 to len(all_urls)
                            for r in range(2, len(all_urls) + 1):
                                if consider_order:
                                    # Use permutations if order matters
                                    for combo in permutations(all_urls, r):
                                        start_urls_combinations.append(list(combo))
                                else:
                                    # Use combinations if order doesn't matter
                                    for combo in combinations(all_urls, r):
                                        start_urls_combinations.append(list(combo))

                        # for each start_urls combination, generate tasks
                        for start_urls in start_urls_combinations:
                            for nudge in supported_nudges:
                                filtered_interventions = get_interventions_for_nudge(nudge, interventions)
                                for intervention_index, intervention in enumerate(filtered_interventions, 1):
                                    task_name = f"Task{task_counter}_{starting_point}_{nudge}_P{product_index}_I{intervention_index}-v0"
                                    config_task_name = task_name.replace('_', '').replace(' ', '')
                                    file_name = task_name.lower().replace(' ', '_').replace('-v0', '')
                                    
                                    config = base_config.copy()
                                    config['name'] = config_task_name
                                    config['config']['task_id'] = task_counter
                                    config['config']['intent_template'] = intent_template
                                    config['config']['intent'] = generated_intent
                                    # Ensure instantiation_dict is an empty dict, not an empty string
                                    config['config']['instantiation_dict'] = {} if not intent_dict else json.loads(intent_dict)
                                    config['config']['start_urls'] = start_urls
                                    config['config']['intent_template_id'] = intent_template_counter
                                    config['config']['choices'][0]['url'] = start_urls[0] if isinstance(start_urls, list) else start_urls[0][0]
                                    config['config']['choices'][0]['functions'] = [{
                                        'module': intervention['Module'],
                                        'name': intervention['Name'],
                                        'args': {
                                            'value': intervention['Intervention']
                                        }
                                    }]
                                    
                            
                                    config_filename = f"conf/task/{file_name}.yaml"
                                    with open(config_filename, 'w') as f:
                                        yaml.dump(config, f, default_flow_style=False)
                                    print(f"Generated config {task_counter}: {config_filename}")
                                    
                                    # Increment the task counter for the next task
                                    task_counter += 1

            intent_template_counter += 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate task configurations')
    parser.add_argument('--consider-order', dest='consider_order', action='store_true',
                        help='Consider order of URLs in combinations')
    parser.add_argument('--ignore-order', dest='consider_order', action='store_false',
                        help='Ignore order of URLs in combinations (default)')
    parser.set_defaults(consider_order=False)
    args = parser.parse_args()
    
    generate_task_configs(consider_order=args.consider_order) 