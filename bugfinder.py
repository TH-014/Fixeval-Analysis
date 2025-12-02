# model_name = "qwen/qwen3-30b-a3b:free"
import os
import random
import json
import csv
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI # type: ignore
from datetime import datetime

# Load environment variables
load_dotenv()

# Configuration
INPUT_DIRS = ["Accepted", "Compile Error", "Memory Limit Exceeded", "Runtime Error", "Time Limit Exceeded"]
RESULT_CSV = "multiagent_results.csv"
CODES_CSV = "multiagent_codes.csv"
OUTPUT_DIR = "bug_analysis_reports"
model_name = "qwen/qwen3-30b-a3b:free"

DATASET_SIZE = 50
PROMPTS_PER_KEY = 30
API_KEYS_FILE = "openaikeys.txt"
MAX_ITERATIONS = 3  # Maximum refinement iterations

# Global variables for key management
api_keys = []
current_key_index = 0
current_prompt_count = 0
client = None

def load_api_keys():
    """Load API keys from the text file"""
    global api_keys
    try:
        with open(API_KEYS_FILE, 'r') as f:
            api_keys = [line.strip() for line in f.readlines() if line.strip()]
        print(f"Loaded {len(api_keys)} API keys from {API_KEYS_FILE}")
        return True
    except FileNotFoundError:
        print(f"Error: {API_KEYS_FILE} not found")
        return False
    except Exception as e:
        print(f"Error loading API keys: {e}")
        return False

def get_current_client():
    """Get the OpenAI client with the current API key"""
    global client, current_key_index, current_prompt_count, api_keys
    
    if current_prompt_count >= PROMPTS_PER_KEY:
        current_key_index += 1
        current_prompt_count = 0
        client = None
        
        if current_key_index >= len(api_keys):
            print("All API keys have been exhausted!")
            return None
        
        print(f"Switching to API key {current_key_index + 1}/{len(api_keys)}")
    
    if client is None:
        if current_key_index >= len(api_keys):
            return None
            
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_keys[current_key_index],
        )
    
    return client

def get_random_file(directory):
    """Get a random JSON file from the specified directory"""
    files = [f for f in os.listdir(directory) if f.endswith('.json')]
    if not files:
        return None
    return os.path.join(directory, random.choice(files))

def get_random_object(file_path):
    """Get a random object from a JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                return None
            return random.choice(data)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading {file_path}: {e}")
        return None

def generate_static_analyzer_prompt(code_obj):
    """Generate prompt for Static Analyzer Agent"""
    code_tokens = code_obj.get('code_tokens', '')
    
    prompt = f"""You are a Static Analyzer Agent in a multi-agent bug detection system. Your role is to perform static analysis to detect compilation errors and runtime vulnerabilities without code execution.

ANALYSIS TARGET:
```
{code_tokens}
```

RESPONSIBILITIES:
- Language-specific syntax error detection
- Unsafe operation identification (null pointers, division by zero, array bounds)
- Code pattern analysis for runtime risks
- Line-by-line analysis for potential issues

ANALYSIS PARAMETERS:
- Assume competitive programming environment
- Focus on C++, Java, Python common syntax issues
- Look for uninitialized variables, out-of-bounds access, type mismatches
- Check for missing imports, incorrect function signatures

OUTPUT FORMAT (JSON only):
{{
    "bugs": [
        {{
            "bug_type": "Compilation Error | Runtime Risk",
            "line": <line_number>,
            "description": "Detailed description of the issue",
            "confidence": <0.0 to 1.0>
        }}
    ]
}}

If no bugs are found, return: {{"bugs": []}}

Provide ONLY the JSON output, no additional explanation."""

    return prompt

def generate_complexity_profiler_prompt(code_obj):
    """Generate prompt for Complexity Profiler Agent"""
    code_tokens = code_obj.get('code_tokens', '')
    
    prompt = f"""You are a Complexity Profiler Agent in a multi-agent bug detection system. Your role is to analyze algorithms and data structures to predict TLE and MLE issues based on competitive programming constraints.

ANALYSIS TARGET:
```
{code_tokens}
```

ANALYSIS PARAMETERS:
- Standard assumptions: 10^8 operations/second, 256MB memory limit
- Time limit: 1 second (unless specified otherwise)
- Calculate Big O notation complexity
- Identify algorithm and data structure usage
- Consider input size constraints typical in competitive programming

FOCUS AREAS:
- Nested loops and their complexity
- Recursive functions and potential exponential growth
- Large data structure allocations
- Memory-intensive operations

OUTPUT FORMAT (JSON only):
{{
    "risks": [
        {{
            "risk_type": "TLE | MLE",
            "line": <line_number>,
            "reason": "Detailed explanation of complexity issue",
            "confidence": <0.0 to 1.0>
        }}
    ]
}}

If no risks are found, return: {{"risks": []}}

Provide ONLY the JSON output, no additional explanation."""

    return prompt

def generate_execution_simulator_prompt(code_obj):
    """Generate prompt for Execution Simulator Agent"""
    code_tokens = code_obj.get('code_tokens', '')
    
    prompt = f"""You are an Execution Simulator Agent in a multi-agent bug detection system. Your role is to act as an adversarial tester, simulating code execution with edge cases to uncover hidden runtime errors.

ANALYSIS TARGET:
```
{code_tokens}
```

TESTING STRATEGY:
- Generate edge-case inputs (zero, negative, empty, maximum values)
- Perform step-by-step execution tracing mentally
- Identify potential crash points
- Consider boundary conditions and invalid inputs

FOCUS AREAS:
- Division by zero scenarios
- Array/string index out of bounds
- Null pointer dereferences  
- Integer overflow/underflow
- Infinite loops or recursion
- Input validation failures

OUTPUT FORMAT (JSON only):
{{
    "errors": [
        {{
            "error_type": "Runtime Error",
            "line": <line_number>,
            "description": "Description of the runtime error",
            "triggering_input": "Input that would cause this error",
            "confidence": <0.0 to 1.0>
        }}
    ]
}}

If no errors are found, return: {{"errors": []}}

Provide ONLY the JSON output, no additional explanation."""

    return prompt

def generate_validator_prompt(static_result, complexity_result, execution_result, code_obj):
    """Generate prompt for Validator Agent"""
    code_tokens = code_obj.get('code_tokens', '')
    
    prompt = f"""You are a Validator Agent in a multi-agent bug detection system. Your role is quality control - cross-reference findings from all analysis agents for accuracy and consistency.

ORIGINAL CODE:
```
{code_tokens}
```

AGENT FINDINGS TO VALIDATE:

STATIC ANALYZER RESULTS:
{json.dumps(static_result, indent=2)}

COMPLEXITY PROFILER RESULTS:
{json.dumps(complexity_result, indent=2)}

EXECUTION SIMULATOR RESULTS:
{json.dumps(execution_result, indent=2)}

VALIDATION CRITERIA:
- Check for contradictions between agent reports
- Assess plausibility of each finding
- Verify consistency across analyses
- Identify false positives or missed issues

OUTPUT FORMAT (JSON only):
{{
    "validation_summary": [
        {{
            "agent": "Static Analyzer | Complexity Profiler | Execution Simulator",
            "finding": {{"original finding object"}},
            "is_valid": "true | false",
            "disagreement_reason": "brief reasoning if is_valid is false"
        }}
    ],
    "needs_re_analysis": "true | false"
}}

Provide ONLY the JSON output, no additional explanation."""

    return prompt

def generate_consolidator_prompt(validated_results, code_obj):
    """Generate prompt for Bug Consolidator Agent"""
    code_tokens = code_obj.get('code_tokens', '')
    
    prompt = f"""You are a Bug Consolidator Agent in a multi-agent bug detection system. Your role is to synthesize validated reports into a clean, prioritized final output.

ORIGINAL CODE:
```
{code_tokens}
```

VALIDATED RESULTS:
{json.dumps(validated_results, indent=2)}

PROCESSING REQUIREMENTS:
1. Merge findings from all validated reports
2. Remove duplicate entries
3. Prioritize by severity: Compilation Error → Runtime Error → TLE → MLE
4. Generate final verdict prediction

VERDICT OPTIONS:
- "Accepted" - No significant issues found
- "Compile Error" - Syntax or compilation issues
- "Runtime Error" - Runtime crashes or exceptions
- "Time Limit Exceeded" - Algorithm too slow
- "Memory Limit Exceeded" - Memory usage too high

OUTPUT FORMAT (JSON only):
{{
    "final_verdict": "Accepted | Compile Error | Runtime Error | Time Limit Exceeded | Memory Limit Exceeded",
    "primary_issue_line": <line_number or 0>,
    "consolidated_issues": [
        {{
            "type": "issue type",
            "line": <line_number>,
            "description": "consolidated description",
            "severity": "High | Medium | Low"
        }}
    ],
    "confidence": <0.0 to 1.0>
}}

Provide ONLY the JSON output, no additional explanation."""

    return prompt

def ask_openrouter(prompt):
    """Ask the OpenAI API a question"""
    global current_prompt_count
    
    current_client = get_current_client()
    if current_client is None:
        print("No more API keys available")
        return None

    max_retries = 3
    retry_count = 0
    wait_time = 2

    while retry_count < max_retries:
        try:
            completion = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            
            current_prompt_count += 1
            print(f"Used key {current_key_index + 1}: {current_prompt_count}/{PROMPTS_PER_KEY} prompts")
            
            return completion.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            print(f"Error during API call: {error_msg}")
            
            if "429" in error_msg:
                retry_seconds = 20 + random.randint(1, 5)
                print(f"Rate limit hit. Waiting for {retry_seconds} seconds...")
                time.sleep(retry_seconds)
                retry_count += 1
            else:
                return None
    
    print(f"Maximum retries exceeded. Skipping this request.")
    return None

def parse_json_response(response_text):
    """Parse JSON response from AI model"""
    try:
        # Clean the response
        cleaned_response = response_text.strip()
        cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
        cleaned_response = re.sub(r'```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()
        
        # Parse JSON
        return json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Original response: {response_text}")
        return None

def create_markdown_report(case_no, code_obj, analysis_results, filename):
    """Create a detailed markdown report for the analysis"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    report_path = os.path.join(OUTPUT_DIR, f"case_{case_no:03d}_analysis.md")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Bug Analysis Report - Case {case_no}\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Source File**: {filename}\n")
        f.write(f"**Submission ID**: {code_obj.get('submission_id', 'N/A')}\n")
        f.write(f"**Actual Verdict**: {code_obj.get('verdict', 'N/A')}\n\n")
        
        # Original Code
        f.write("## Original Code\n\n")
        f.write("```\n")
        f.write(code_obj.get('code_tokens', ''))
        f.write("\n```\n\n")
        
        # Analysis Results
        f.write("## Multi-Agent Analysis Results\n\n")
        
        for iteration in range(len(analysis_results)):
            f.write(f"### Iteration {iteration + 1}\n\n")
            iteration_data = analysis_results[iteration]
            
            # Static Analyzer
            f.write("#### Static Analyzer Agent\n\n")
            f.write("**Prompt:**\n")
            f.write("```\n")
            f.write(iteration_data['static_prompt'])
            f.write("\n```\n\n")
            f.write("**Response:**\n")
            f.write("```json\n")
            f.write(json.dumps(iteration_data['static_result'], indent=2))
            f.write("\n```\n\n")
            
            # Complexity Profiler
            f.write("#### Complexity Profiler Agent\n\n")
            f.write("**Prompt:**\n")
            f.write("```\n")
            f.write(iteration_data['complexity_prompt'])
            f.write("\n```\n\n")
            f.write("**Response:**\n")
            f.write("```json\n")
            f.write(json.dumps(iteration_data['complexity_result'], indent=2))
            f.write("\n```\n\n")
            
            # Execution Simulator
            f.write("#### Execution Simulator Agent\n\n")
            f.write("**Prompt:**\n")
            f.write("```\n")
            f.write(iteration_data['execution_prompt'])
            f.write("\n```\n\n")
            f.write("**Response:**\n")
            f.write("```json\n")
            f.write(json.dumps(iteration_data['execution_result'], indent=2))
            f.write("\n```\n\n")
            
            # Validator
            f.write("#### Validator Agent\n\n")
            f.write("**Prompt:**\n")
            f.write("```\n")
            f.write(iteration_data['validator_prompt'])
            f.write("\n```\n\n")
            f.write("**Response:**\n")
            f.write("```json\n")
            f.write(json.dumps(iteration_data['validator_result'], indent=2))
            f.write("\n```\n\n")
            
            if 'consolidator_prompt' in iteration_data:
                # Bug Consolidator (final iteration only)
                f.write("#### Bug Consolidator Agent\n\n")
                f.write("**Prompt:**\n")
                f.write("```\n")
                f.write(iteration_data['consolidator_prompt'])
                f.write("\n```\n\n")
                f.write("**Response:**\n")
                f.write("```json\n")
                f.write(json.dumps(iteration_data['consolidator_result'], indent=2))
                f.write("\n```\n\n")
        
        # Final Summary
        final_result = analysis_results[-1].get('consolidator_result', {})
        f.write("## Final Analysis Summary\n\n")
        f.write(f"**Predicted Verdict**: {final_result.get('final_verdict', 'Unknown')}\n")
        f.write(f"**Primary Issue Line**: {final_result.get('primary_issue_line', 0)}\n")
        f.write(f"**Confidence**: {final_result.get('confidence', 0.0)}\n")
        f.write(f"**Accuracy**: {'✓ Correct' if final_result.get('final_verdict') == code_obj.get('verdict') else '✗ Incorrect'}\n\n")
        
        if final_result.get('consolidated_issues'):
            f.write("**Identified Issues:**\n")
            for issue in final_result['consolidated_issues']:
                f.write(f"- **Line {issue.get('line', 0)}**: {issue.get('description', '')} (Severity: {issue.get('severity', 'Unknown')})\n")

def run_multiagent_analysis(code_obj):
    """Run the complete multi-agent analysis pipeline"""
    analysis_results = []
    iteration = 0
    
    while iteration < MAX_ITERATIONS:
        print(f"  Running iteration {iteration + 1}...")
        iteration_data = {}
        
        # Step 1: Static Analyzer
        static_prompt = generate_static_analyzer_prompt(code_obj)
        static_response = ask_openrouter(static_prompt)
        static_result = parse_json_response(static_response) if static_response else {"bugs": []}
        
        iteration_data.update({
            'static_prompt': static_prompt,
            'static_result': static_result
        })
        
        time.sleep(1)  # Rate limiting
        
        # Step 2: Complexity Profiler
        complexity_prompt = generate_complexity_profiler_prompt(code_obj)
        complexity_response = ask_openrouter(complexity_prompt)
        complexity_result = parse_json_response(complexity_response) if complexity_response else {"risks": []}
        
        iteration_data.update({
            'complexity_prompt': complexity_prompt,
            'complexity_result': complexity_result
        })
        
        time.sleep(1)
        
        # Step 3: Execution Simulator
        execution_prompt = generate_execution_simulator_prompt(code_obj)
        execution_response = ask_openrouter(execution_prompt)
        execution_result = parse_json_response(execution_response) if execution_response else {"errors": []}
        
        iteration_data.update({
            'execution_prompt': execution_prompt,
            'execution_result': execution_result
        })
        
        time.sleep(1)
        
        # Step 4: Validator
        validator_prompt = generate_validator_prompt(static_result, complexity_result, execution_result, code_obj)
        validator_response = ask_openrouter(validator_prompt)
        validator_result = parse_json_response(validator_response) if validator_response else {"validation_summary": [], "needs_re_analysis": "false"}
        
        iteration_data.update({
            'validator_prompt': validator_prompt,
            'validator_result': validator_result
        })
        
        time.sleep(1)
        
        # Check if re-analysis is needed
        needs_re_analysis_value = validator_result.get("needs_re_analysis", False)
        if isinstance(needs_re_analysis_value, bool):
            needs_re_analysis = needs_re_analysis_value
        elif isinstance(needs_re_analysis_value, str):
            needs_re_analysis = needs_re_analysis_value.lower() == "true"
        else:
            needs_re_analysis = False
        
        if not needs_re_analysis or iteration == MAX_ITERATIONS - 1:
            # Final step: Bug Consolidator
            consolidator_prompt = generate_consolidator_prompt(validator_result, code_obj)
            consolidator_response = ask_openrouter(consolidator_prompt)
            consolidator_result = parse_json_response(consolidator_response) if consolidator_response else {
                "final_verdict": "Accepted",
                "primary_issue_line": 0,
                "consolidated_issues": [],
                "confidence": 0.5
            }
            
            iteration_data.update({
                'consolidator_prompt': consolidator_prompt,
                'consolidator_result': consolidator_result
            })
            
            analysis_results.append(iteration_data)
            break
        else:
            analysis_results.append(iteration_data)
            iteration += 1
            print(f"  Validator requested re-analysis. Starting iteration {iteration + 1}...")
    
    return analysis_results

def main():
    # Load API keys
    if not load_api_keys() or len(api_keys) == 0:
        print("Failed to load API keys. Exiting.")
        return
    
    print(f"Starting Multi-Agent Bug Detection System with {len(api_keys)} API keys")
    
    # Initialize CSV files
    csv_exists = os.path.exists(RESULT_CSV)
    codes_exists = os.path.exists(CODES_CSV)
    
    with open(RESULT_CSV, 'a', newline='') as result_file, \
         open(CODES_CSV, 'a', newline='') as codes_file:
        
        # Result CSV writer
        result_fieldnames = [
            'case_no', 'filename', 'submission_id', 'actual_verdict',
            'predicted_verdict', 'primary_issue_line', 'confidence',
            'iterations_used', 'analysis_time'
        ]
        result_writer = csv.DictWriter(result_file, fieldnames=result_fieldnames)
        
        # Codes CSV writer
        codes_fieldnames = ['case_no', 'code_token']
        codes_writer = csv.DictWriter(codes_file, fieldnames=codes_fieldnames)
        
        # Write headers if files don't exist
        if not csv_exists:
            result_writer.writeheader()
        if not codes_exists:
            codes_writer.writeheader()
        
        # Process cases
        case_counter = 1
        matched_verdict_count = 0
        
        while case_counter <= DATASET_SIZE:
            try:
                if current_key_index >= len(api_keys):
                    print("All API keys exhausted. Stopping.")
                    break
                
                # Select random directory and file
                selected_dir = random.choice(INPUT_DIRS)
                if not os.path.exists(selected_dir):
                    print(f"Directory {selected_dir} not found")
                    break
                
                file_path = get_random_file(selected_dir)
                if not file_path:
                    print(f"No files found in {selected_dir}")
                    continue
                
                code_obj = get_random_object(file_path)
                if not code_obj:
                    continue
                
                print(f"\nProcessing Case {case_counter}/{DATASET_SIZE}")
                print(f"File: {os.path.basename(file_path)}")
                print(f"Actual Verdict: {code_obj.get('verdict', 'Unknown')}")
                
                # Record start time
                start_time = time.time()
                
                # Run multi-agent analysis
                analysis_results = run_multiagent_analysis(code_obj)
                
                # Calculate analysis time
                analysis_time = time.time() - start_time
                
                # Extract final results
                final_result = analysis_results[-1].get('consolidator_result', {})
                predicted_verdict = final_result.get('final_verdict', 'Unknown')
                primary_line = final_result.get('primary_issue_line', 0)
                confidence = final_result.get('confidence', 0.0)
                
                print(f"Predicted Verdict: {predicted_verdict}")
                print(f"Analysis Time: {analysis_time:.2f}s")
                print(f"Iterations Used: {len(analysis_results)}")
                
                # Check accuracy
                if predicted_verdict == code_obj.get('verdict', ''):
                    matched_verdict_count += 1
                    print("✓ Prediction Correct")
                else:
                    print("✗ Prediction Incorrect")
                
                # Write to CSV files
                result_data = {
                    'case_no': case_counter,
                    'filename': os.path.basename(file_path),
                    'submission_id': code_obj.get('submission_id', ''),
                    'actual_verdict': code_obj.get('verdict', ''),
                    'predicted_verdict': predicted_verdict,
                    'primary_issue_line': primary_line,
                    'confidence': confidence,
                    'iterations_used': len(analysis_results),
                    'analysis_time': round(analysis_time, 2)
                }
                result_writer.writerow(result_data)
                
                codes_data = {
                    'case_no': case_counter,
                    'code_token': code_obj.get('code_tokens', '')
                }
                codes_writer.writerow(codes_data)
                
                # Create markdown report
                create_markdown_report(case_counter, code_obj, analysis_results, os.path.basename(file_path))
                
                # Flush files
                result_file.flush()
                codes_file.flush()
                
                case_counter += 1
                
                # Brief pause between cases
                time.sleep(2)
                
            except KeyboardInterrupt:
                print("\nProcess interrupted by user")
                break
            except Exception as e:
                print(f"Unexpected error in case {case_counter}: {str(e)}")
                case_counter += 1
                continue
        
        # Final statistics
        total_cases = min(case_counter - 1, DATASET_SIZE)
        accuracy = (matched_verdict_count * 100) / total_cases if total_cases > 0 else 0
        
        print(f"\n{'='*50}")
        print("MULTI-AGENT BUG DETECTION SYSTEM - FINAL RESULTS")
        print(f"{'='*50}")
        print(f"Total Cases Processed: {total_cases}")
        print(f"Correct Predictions: {matched_verdict_count}")
        print(f"Overall Accuracy: {accuracy:.2f}%")
        print(f"Results saved to: {RESULT_CSV}")
        print(f"Code data saved to: {CODES_CSV}")
        print(f"Detailed reports saved to: {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()