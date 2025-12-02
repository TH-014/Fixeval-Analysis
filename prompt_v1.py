import os
import random
import json
import csv
import time
from pathlib import Path
# import google.generativeai as genai
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
INPUT_DIRS = ["Accepted", "Compile Error"]
RESULT_CSV = "result.csv"
CODES_CSV = "codes.csv"
model_name = 'gemini-2.5-flash-preview-04-17' 

DATASET_SIZE = 50

# Initialize Gemini
api_key = os.getenv('GEMINI_API_KEY')
# if not api_key:
#     raise ValueError("GEMINI_API_KEY not found in .env file")
# genai.configure(api_key=api_key)
# model = genai.GenerativeModel(GEMINI_MODEL)

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

def generate_prompt_1(code_obj):
    """Generate the prompt for Gemini, excluding the verdict field"""
    # Create a copy of the object without the verdict field
    prompt_obj = {k: v for k, v in code_obj.items() if k != "verdict"}
    
    prompt_template = """
Read the above code_tokens. Provide a short explanation for each statements.
"""
    return f"{json.dumps(prompt_obj, indent=2)}\n\n{prompt_template}"

def generate_prompt_2(code_obj, explanation):
    """Generate the prompt for Gemini, excluding the verdict field"""
    # Create a copy of the object without the verdict field
    prompt_obj = {k: v for k, v in code_obj.items() if k != "verdict"}
    
    prompt_template = """
Read the above code_tokens and predict the verdict of the code.
A short explanation of the code is also attached. Check the code along with the explanation carefully to predict the correct verdict.
The verdict will be either "Accepted" or "Compile Error"
If you can find any error in a line mention the line number (mention 0 if no error is found).

YOUR RESPONSE MUST BE OF THE FOLLOWING FORM:
{
    "verdict":"Accepted"
    "line_number":"0"
} 
or
{
    "verdict":"Compile Error"
    "line_number":"12"
} 

NO FURTHER EXPLANATION IS NEEDED.
"""
    return f"{json.dumps(prompt_obj, indent=2)}\n\nShort Explanation:{explanation}\n\n{prompt_template}"

def ask_gemini(prompt):
    """Ask the Gemini API a question."""
    client = genai.Client(api_key=api_key)

    max_retries = 5
    retry_count = 1
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

def parse_response(response_text):
    """Parse Gemini response into verdict and line number"""
    try:
        # Remove all markdown code block markers
        cleaned_response = response_text.strip()
        cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
        
        # Handle case where response might have extra whitespace or newlines
        cleaned_response = cleaned_response.strip()
        
        # Parse the JSON
        response_data = json.loads(cleaned_response)
        return response_data.get("verdict", ""), response_data.get("line_number", "0")
    except json.JSONDecodeError as e:
        # Fallback to regex parsing if standard parsing fails
        try:
            verdict_match = re.search(r'"verdict"\s*:\s*"([^"]*)"', response_text)
            line_match = re.search(r'"line_number"\s*:\s*"([^"]*)"', response_text)
            
            verdict = verdict_match.group(1) if verdict_match else ""
            line_number = line_match.group(1) if line_match else "0"
            
            return verdict, line_number
        except Exception as e:
            print(f"Failed to parse Gemini response: {e}")
            print(f"Original response: {response_text}")
            return "", "0"

def main():
    # Initialize CSV file
    csv_exists = os.path.exists(RESULT_CSV)
    codes_exists = os.path.exists(CODES_CSV)
    
    with open(RESULT_CSV, 'a', newline='') as result_file, \
         open(CODES_CSV, 'a', newline='') as codes_file:
        
        # Result CSV writer
        result_fieldnames = [
            'filename', 'submission_id', 'actual_verdict',
            'predicted_verdict', 'predicted_line_number'
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
        
        # Process files
        case_counter =1
        matched_verdict_count = 0
        while case_counter <= DATASET_SIZE:
            try:
                # Randomly select a directory
                selected_dir = random.choice(INPUT_DIRS)
                if not os.path.exists(selected_dir):
                    print(f"Directory {selected_dir} not found")
                    break
                
                # Get random file
                file_path = get_random_file(selected_dir)
                if not file_path:
                    print(f"No files found in {selected_dir}")
                    continue
                
                # Get random object
                code_obj = get_random_object(file_path)
                if not code_obj:
                    continue
                
                # Prepare data for result.csv
                result_data = {
                    'filename': os.path.basename(file_path),
                    'submission_id': code_obj.get('submission_id', ''),
                    'actual_verdict': code_obj.get('verdict', '')
                }
                
                # Write to codes.csv
                codes_data = {
                    'case_no': case_counter,
                    'code_token': code_obj.get('code_tokens', '')
                }
                codes_writer.writerow(codes_data)
                
                print(f"\nProcessing case {case_counter} - {result_data['filename']} - {result_data['submission_id']}")
                print(f"Actual verdict: {result_data['actual_verdict']}")
                
                # Generate and send prompt
                prompt_1 = generate_prompt_1(code_obj)
                response_text_1 = ask_gemini(prompt_1)
                # print(response_text_1)
                prompt_2 = generate_prompt_2(code_obj, response_text_1)
                response_text = ask_gemini(prompt_2)
                
                if response_text:
                    predicted_verdict, line_number = parse_response(response_text)
                    result_data.update({
                        'predicted_verdict': predicted_verdict,
                        'predicted_line_number': line_number
                    })
                    
                    print(f"Predicted verdict: {predicted_verdict}")
                    print(f"Line number: {line_number}")

                    if(predicted_verdict == code_obj.get('verdict', '')):
                        matched_verdict_count += 1;
                else:
                    result_data.update({
                        'predicted_verdict': 'ERROR',
                        'predicted_line_number': '-1'
                    })
                    print("Failed to get response from Gemini")
                
                # Write to result.csv
                result_writer.writerow(result_data)
                
                # Flush both files to ensure data is written
                result_file.flush()
                codes_file.flush()
                
                # Increment case counter
                case_counter += 1
                
                # Wait before next request to avoid rate limiting
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nProcess interrupted by user")
                break
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                continue

        accuracy = (matched_verdict_count*100)/DATASET_SIZE
        print("Accuracy: ", accuracy)

if __name__ == "__main__":
    main()
    print("Processing completed. Results saved to", RESULT_CSV)