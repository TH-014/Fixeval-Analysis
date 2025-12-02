import json
import os
from pathlib import Path

def process_json_files():
    print("Starting processing...")
    
    # Get all json files in current directory
    json_files = [f for f in os.listdir() if f.endswith('.json') and f.split('.')[0].isdigit()]
    print(f"Found {len(json_files)} JSON files to process: {json_files}")
    
    if not json_files:
        print("No JSON files found matching the pattern (0.json, 1.json, etc.)")
        return
    
    # Process each json file
    for json_file in json_files:
        print(f"\nProcessing file: {json_file}")
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding {json_file}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error reading {json_file}: {e}")
            continue
        
        if not isinstance(data, list):
            print(f"{json_file} doesn't contain an array (got {type(data)}), skipping...")
            continue
        
        print(f"Found {len(data)} arrays in {json_file}")
        
        # Group objects by verdict
        verdict_groups = {}
        total_objects = 0
        
        # Process each sub-array
        for sub_array in data:
            if not isinstance(sub_array, list):
                print(f"Found non-array element in main array: {type(sub_array)}")
                continue
            
            for obj in sub_array:
                if not isinstance(obj, dict):
                    print(f"Found non-dict object in sub-array: {type(obj)}")
                    continue
                
                if 'verdict' not in obj:
                    print("Object missing 'verdict' field:", obj.keys())
                    continue
                
                verdict = obj['verdict']
                if verdict not in verdict_groups:
                    verdict_groups[verdict] = []
                verdict_groups[verdict].append(obj)
                total_objects += 1
        
        print(f"Found {total_objects} objects across all arrays")
        print(f"Found {len(verdict_groups)} verdict groups: {list(verdict_groups.keys())}")
        
        # Write to respective verdict directories
        for verdict, objects in verdict_groups.items():
            # Create directory if it doesn't exist
            verdict_dir = Path(verdict)
            try:
                verdict_dir.mkdir(exist_ok=True)
                print(f"Created directory: {verdict_dir}")
            except Exception as e:
                print(f"Failed to create directory {verdict_dir}: {e}")
                continue
            
            # Write the objects to file
            output_file = verdict_dir / json_file
            try:
                with open(output_file, 'w') as out_f:
                    json.dump(objects, out_f, indent=2)
                print(f"Written {len(objects)} objects to {output_file}")
            except Exception as e:
                print(f"Failed to write to {output_file}: {e}")

if __name__ == "__main__":
    process_json_files()
    print("\nProcessing complete!")