import pandas as pd
import google.generativeai as genai # type: ignore
# from google import genai
import os
import random
import csv
import re
import time
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

relative_path = "CodRep-master/Datasets/Merged/Dataset1"
results_csv = 'results.csv'
model_name=''
api_key=''
total_files = 100
output_matched = 0

def config_gemini(model_number=19):
    """Configure the Gemini API client."""

    global model_name, api_key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        exit()

    # List models
    # model_list = []
    # for m in genai.list_models():
    #     # Filter for models capable of text generation and typically used for content
    #     if 'generateContent' in m.supported_generation_methods:
    #         model_list.append(m.name)
    #         # print(f"{m.name} (Description: {m.description})")
    # # print(model_list)
    # # model_name = 'gemini-2.5-flash-preview-04-17'  # Specify the model name
    # if(model_number < 0 or model_number >= len(model_list)):
    #     print("Error: Invalid model number. Model set to default.")
    #     model_name = 'gemini-2.5-flash-preview-04-17'
    # else:
    #     model_name = model_list[model_number]
    model_name = 'gemini-2.5-flash-preview-04-17'  # Default model name
    return model_name, api_key

def ask_gemini(model_name, api_key, prompt):
    """Ask the Gemini API a question."""
    client = genai.Client(api_key=api_key)

    max_retries = 5
    retry_count = 0
    wait_time = 3  # Initial wait time in seconds - reduced for Flash-Lite

    while retry_count < max_retries:
        try:
            # response = model.generate_content([prompt])
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            print(f"Error during API call: {error_msg}")
            
            # Check if it's a rate limit error (429)
            if "429" in error_msg and "quota" in error_msg.lower():
                # Try to extract wait time from error message
                retry_seconds = 30  # Default to 30 seconds if we can't parse the wait time (reduced from 60)
                match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', error_msg)
                if match:
                    retry_seconds = int(match.group(1)) + random.randint(1, 3)  # Add some random jitter (reduced)
                
                print(f"Rate limit hit. Waiting for {retry_seconds} seconds before retrying...")
                time.sleep(retry_seconds)
                retry_count += 1
                wait_time = min(wait_time * 2, 120)  # Exponential backoff, but max 2 minutes (reduced from 5)
            else:
                # Some other error, not rate limiting
                return None
    
    print(f"Maximum retries ({max_retries}) exceeded. Skipping this instance.")
    return None

prompt_suffix = f"""This code contains bug in atmost 1 line.
If you can identify the bug then just print the buggy line number (e.g. 111).
If there is no bug then print 0.
Don't print any unnecessary output or explanation."""


def extract_source_code_and_solution(file_path):
    """
    Extract source code and solution from a markdown file.
    
    Args:
        file_path (str): Path to the markdown file
        
    Returns:
        tuple: (src_code, soln) where src_code contains the source code
               and soln contains the solution line number
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        src_code = ""
        soln = ""
        
        # Find the start of source code
        src_start_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == "Source Code:":
                src_start_idx = i
                break
        
        if src_start_idx == -1:
            print(f"Warning: 'Source Code:' not found in {file_path}")
            return None, None
        
        # Find the end of source code (before "### Solution")
        src_end_idx = -1
        solution_line_idx = -1
        for i in range(src_start_idx + 1, len(lines)):
            if "### Solution" in lines[i]:
                src_end_idx = i
                solution_line_idx = i
                break
        
        if src_end_idx == -1:
            print(f"Warning: '### Solution' not found in {file_path}")
            return None, None
        
        # Extract source code from start line to before solution line
        src_code = "".join(lines[src_start_idx:src_end_idx])
        
        # Extract solution (line x+5 where x is the line with "### Solution")
        soln_line_idx = solution_line_idx + 5
        if soln_line_idx < len(lines):
            soln = lines[soln_line_idx].strip()
            # Remove markdown code block markers if present
            soln = re.sub(r'^```.*$', '', soln).strip()
        else:
            print(f"Warning: Solution line index {soln_line_idx} out of range in {file_path}")
            return src_code, ""
        
        return src_code, soln
    
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")
        return None, None

def find_md_files(root_path):
    """
    Find all .md files in the given directory and its subdirectories.
    
    Args:
        root_path (str): Root directory path
        
    Returns:
        list: List of paths to .md files
    """
    md_files = []
    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.endswith('.md'):
                md_files.append(os.path.join(root, file))
    return md_files

def read():
    # Define the relative path
    global relative_path
    # Check if the directory exists
    if not os.path.exists(relative_path):
        print(f"Error: Directory '{relative_path}' does not exist.")
        print("Please make sure the directory path is correct.")
        return
    
    # Find all .md files
    print(f"Searching for .md files in {relative_path}...")
    md_files = find_md_files(relative_path)
    
    if len(md_files) == 0:
        print(f"No .md files found in {relative_path}")
        return
    
    print(f"Found {len(md_files)} .md files")
    
    # Randomly select 100 files (or all files if less than 100)
    num_files_to_select = min(100, len(md_files))
    selected_files = random.sample(md_files, num_files_to_select)
    
    print(f"Selected {num_files_to_select} files randomly")
    
    # Process each selected file
    # results = []
    # successful_extractions = 0
    # global output_matched
    
    # for file_path in selected_files:
    #     filename = os.path.basename(file_path)
    #     try:
    #         src_code, soln = extract_source_code_and_solution(file_path)
    #         if src_code is not None and soln is not None:
    #             prompt = f"{src_code}\n\n{prompt_suffix}"
    #             res = ask_gemini(model_name, api_key, prompt)
    #             results.append({
    #                 'filename': filename,
    #                 'answer': soln,
    #                 'response': res
    #             })
    #             if res is None:
    #                 print(f"Error: No response from Gemini API for {filename}")
    #                 continue
    #             res = res.strip()
    #             is_match = False
    #             if res == prompt:
    #                 output_matched += 1
    #                 is_match = True
    #             successful_extractions += 1
    #             print(f"{filename} extraction completed successfully, match: {is_match}")
    #         else:
    #             print(f"Skipping {filename} due to extraction errors")
    #     except Exception as e:
    #         print(f"Error processing file {file_path}: {str(e)}")
    #         continue
    
    # print(f"Successfully processed {successful_extractions} files")
    # print(f"Total output matched: {output_matched} out of {len(selected_files)} files")
    
    # # Create results.csv
    # global results_csv
    # try:
    #     with open(results_csv, 'w', newline='', encoding='utf-8') as csvfile:
    #         fieldnames = ['filename', 'answer', 'response']
    #         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
    #         writer.writeheader()
    #         for result in results:
    #             writer.writerow(result)
        
    #     print(f"Results saved to {results_csv}")
    #     print(f"CSV contains {len(results)} rows (excluding header)")
        
    # except Exception as e:
    #     print(f"Error writing CSV file: {str(e)}")
    global output_matched, results_csv
    output_matched = 0
    successful_extractions = 0

    # Open the CSV once, write header, and keep the file open
    with open(results_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['filename', 'answer', 'response']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each selected file, updating CSV as we go
        for file_path in selected_files:
            filename = os.path.basename(file_path)
            try:
                src_code, soln = extract_source_code_and_solution(file_path)
                if src_code is None or soln is None:
                    print(f"Skipping {filename} due to extraction errors")
                    continue

                prompt = f"{src_code}\n\n{prompt_suffix}"
                res = ask_gemini(model_name, api_key, prompt)
                if res is None:
                    print(f"Error: No response from Gemini API for {filename}")
                    continue

                res = res.strip()
                is_match = False
                if res == prompt:
                    output_matched += 1
                    is_match = True

                successful_extractions += 1
                print(f"{filename} extraction completed successfully, match: {is_match}")

                # Immediately write this result to the CSV
                writer.writerow({
                    'filename': filename,
                    'answer': soln,
                    'response': res
                })
                # Ensure it’s flushed to disk (optional but safer if the script crashes)
                csvfile.flush()

            except Exception as e:
                print(f"Error processing file {filename}: {str(e)}")
                continue

    # Summary prints after closing CSV
    print(f"Successfully processed {successful_extractions} files")
    print(f"Total output matched: {output_matched} out of {len(selected_files)} files")
    print(f"Results are being saved incrementally to {results_csv}")



if __name__ == "__main__":
    model_name, api_key = config_gemini()
    prompt = "I'm using the Gemini API to generate content for the first time. Can you list all the Gemini models that I can use to generate content from my code using my API key?"
    # response_text = ask_gemini(model_name, api_key, prompt)
    # print(response_text)  # Print the response from the Gemini API
    random.seed(42)
    read()
