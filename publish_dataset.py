import json
import os
import sys

from datasets import Dataset

# Make sure we can import scenarios
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scenarios.registry import SCENARIOS

def extract_dataset():
    """Convert all scenarios into a flat list of dicts suitable for huggingface."""
    records = []
    
    for s_id, scenario in SCENARIOS.items():
        # Flatten scenario object to dictionary
        record = {
            "scenario_id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "difficulty": scenario.difficulty,
            "tasks": scenario.tasks,
            "stage": scenario.stage,
            "pipeline_config": scenario.pipeline_config,
            # Serialize logs correctly
            "logs_build": scenario.logs.get("build", ""),
            "logs_test": scenario.logs.get("test", ""),
            "logs_deploy": scenario.logs.get("deploy", ""),
            "logs_config": scenario.logs.get("config", ""),
            "error_summary": scenario.error_summary,
            "root_cause": scenario.root_cause,
            "diagnosis_keywords": scenario.diagnosis_keywords,
            "expected_fix_file": scenario.expected_fix_file,
            "expected_fix": scenario.expected_fix,
        }
        records.append(record)
        
    return records

def export_jsonl(records, filename="scenarios.jsonl"):
    """Export the raw records to JSONL."""
    with open(filename, 'w') as f:
        for r in records:
            f.write(json.dumps(r) + '\n')
    print(f"Exported {len(records)} scenarios to {filename}")

def publish_to_hub(repo_id: str):
    """Publish to the Hugging Face hub."""
    print(f"Publishing to Hugging Face Hub dataset: {repo_id}...")
    records = extract_dataset()
    
    # 1. Export locally just in case
    export_jsonl(records)
    
    # 2. Build the HuggingFace Dataset object
    # datasets takes a dict of lists
    ds_dict = {key: [r[key] for r in records] for key in records[0].keys()}
    dataset = Dataset.from_dict(ds_dict)
    
    # 3. Push to hub
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("ERROR: HF_TOKEN environment variable is not set.")
        print("Please run: export HF_TOKEN='your_token'")
        sys.exit(1)
        
    try:
        dataset.push_to_hub(repo_id, token=token)
        print(f"Successfully published dataset to https://huggingface.co/datasets/{repo_id}")
    except Exception as e:
        print(f"Failed to publish to hub: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python publish_dataset.py <huggingface-username/repo-name>")
        print("Example: python publish_dataset.py shreeyanshi03/cicd-scenarios")
        
        # We will just export to JSONL if no repo provided
        print("\nNo repository provided. Defaulting to local export only.")
        records = extract_dataset()
        export_jsonl(records)
        sys.exit(0)
        
    repo_id = sys.argv[1]
    publish_to_hub(repo_id)
