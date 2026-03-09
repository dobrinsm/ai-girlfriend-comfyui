#!/usr/bin/env python3
"""
Run ComfyUI workflows via API.
Usage: python run_workflow.py <workflow_json> [comfyui_url]
"""
import json
import sys
import requests
import time

COMFYUI_URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8188"

def queue_workflow(workflow_path):
    """Queue a workflow to ComfyUI"""
    with open(workflow_path, 'r') as f:
        workflow = json.load(f)
    
    # Send to ComfyUI API
    response = requests.post(
        f"{COMFYUI_URL}/api/prompt",
        json={"prompt": workflow}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Workflow queued successfully!")
        print(f"Prompt ID: {result.get('prompt_id')}")
        return result.get('prompt_id')
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def get_history(prompt_id):
    """Get workflow execution history"""
    response = requests.get(f"{COMFYUI_URL}/api/history/{prompt_id}")
    return response.json() if response.status_code == 200 else None

def get_outputs(prompt_id):
    """Get output images from completed workflow"""
    history = get_history(prompt_id)
    if not history or prompt_id not in history:
        return None
    
    outputs = history[prompt_id].get('outputs', {})
    images = []
    for node_id, node_data in outputs.items():
        if 'images' in node_data:
            for img in node_data['images']:
                images.append({
                    'node': node_id,
                    'filename': img['filename'],
                    'subfolder': img.get('subfolder', '')
                })
    return images

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_workflow.py <workflow_json> [comfyui_url]")
        print("\nAvailable workflows:")
        print("  workflows/image-gen/flux_api.json")
        print("  workflows/video-gen/wan22_i2v_api.json")
        print("  workflows/voice-lipsync/cosyvoice_sadtalker_api.json")
        sys.exit(1)
    
    workflow_path = sys.argv[1]
    prompt_id = queue_workflow(workflow_path)
    
    if prompt_id:
        print(f"\nMonitoring workflow at {COMFYUI_URL}/view?id={prompt_id}")
        print("Press Ctrl+C to stop monitoring")
        
        try:
            while True:
                time.sleep(2)
                history = get_history(prompt_id)
                if history and prompt_id in history:
                    status = history[prompt_id].get('status', {})
                    if status.get('completed', False):
                        print("\n✓ Workflow completed!")
                        outputs = get_outputs(prompt_id)
                        if outputs:
                            print("\nOutput images:")
                            for img in outputs:
                                print(f"  - {img['filename']}")
                                print(f"    {COMFYUI_URL}/view?filename={img['filename']}&subfolder={img['subfolder']}")
                        break
                    elif status.get('err_msg'):
                        print(f"\n✗ Error: {status['err_msg']}")
                        break
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
