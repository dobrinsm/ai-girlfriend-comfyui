#!/usr/bin/env python3
"""
Script to convert ComfyUI workflows from UI format to API format
Run this in ComfyUI directory or use the API directly
"""

import json
import sys
import os

def convert_to_api_format(workflow_path):
    """Convert UI format workflow to API format"""
    with open(workflow_path, 'r') as f:
        workflow = json.load(f)
    
    # API format is a flat dict with node_id -> node config
    api_workflow = {}
    
    nodes = workflow.get('nodes', [])
    for node in nodes:
        node_id = str(node['id'])
        api_node = {
            'inputs': {},
            'class_type': node['type']
        }
        
        # Add widgets_values
        if 'widgets_values' in node:
            api_node['widgets_values'] = node['widgets_values']
        
        # Convert inputs to proper format
        for inp in node.get('inputs', []):
            if 'link' in inp:
                # This input is linked to another node
                link_id = inp['link']
                # Find the source of this link
                for link in workflow.get('links', []):
                    if link[0] == link_id:
                        source_node_id = str(link[1])
                        source_slot = link[2]
                        output_name = link[5]
                        if source_node_id not in api_node['inputs']:
                            api_node['inputs'][inp['name']] = [output_name, [source_node_id, source_slot]]
                        break
            elif 'widget' in inp:
                # This input has a widget value
                pass  # Widget values are handled separately
        
        api_workflow[node_id] = api_node
    
    return api_workflow

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python convert_workflows.py <workflow_file.json>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = input_file.replace('.json', '_api.json')
    
    result = convert_to_api_format(input_file)
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Converted {input_file} -> {output_file}")
