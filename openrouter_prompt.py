import os
import random
import json
import csv
import re
import time
from pathlib import Path
# import google.generativeai as genai
# from google import genai
from dotenv import load_dotenv
from openai import OpenAI # type: ignore

# Load environment variables
load_dotenv()

# Configuration
INPUT_DIRS = ["Accepted", "Compile Error", "Memory Limit Exceeded", "Runtime Error", "Time Limit Exceeded"]
RESULT_CSV = "result.csv"
CODES_CSV = "codes.csv"
# model_name = "openrouter/cypher-alpha:free"
model_name = "nvidia/llama-3.3-nemotron-super-49b-v1:free"

DATASET_SIZE = 100

# Initialize Openrouter
api_key = os.getenv('OPENAI_API_KEY')

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=api_key,
)

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

def generate_prompt(code_obj):
    """Generate the prompt for Gemini, excluding the verdict field"""
    # Create a copy of the object without the verdict field
    prompt_obj = {k: v for k, v in code_obj.items() if k != "verdict"}
    
    prompt_template = """
Read the above code_tokens and predict the verdict of the code.
The verdict will be one of the following:
["Accepted", "Compile Error", "Memory Limit Exceeded", "Runtime Error", "Time Limit Exceeded"]

You can assume default memory limit as 512 mb and default time limit as 1s.
To determine if it is time/memory limit exceeded ot not, at first determine the time/space complexity of the code and determine the verdict accordingly.
A few examples is given below:

{
    "code_tokens": "import java.io.BufferedReader;\nimport java.io.IOException;\nimport java.io.InputStreamReader;\nimport java.util.ArrayDeque;\n\npublic class Main {\n\n\tpublic static void main(String[] args) throws IOException {\n\t\tBufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n\t\tString line = \"\";\n\n\t\twhile ((line = br.readLine()) != null && !line.isEmpty()) {\n\t\t\tint n = Integer.parseInt(line);\n\t\t\tif (n == 0) {\n\t\t\t\tbreak;\n\t\t\t}\n\n\t\t\tlong count = 0;\n\t\t\tArrayDeque<Integer> queue = new ArrayDeque<Integer>();\n\t\t\tqueue.offer(n - 1);\n\t\t\tqueue.offer(n - 2);\n\t\t\tqueue.offer(n - 3);\n\n\t\t\twhile (queue.size() > 0) {\n\t\t\t\tInteger step = queue.poll();\n\t\t\t\tif (step == 0) {\n\t\t\t\t\tcount++;\n\t\t\t\t} else if (step > 0) {\n\t\t\t\t\tqueue.offer(step - 1);\n\t\t\t\t\tqueue.offer(step - 2);\n\t\t\t\t\tqueue.offer(step - 3);\n\t\t\t\t}\n\t\t\t}\n\t\t\tSystem.out.println(count % 3650 == 0 ? count / 3650 : count / 3650 + 1);\n\t\t}\n\t}\n}",
    "verdict": "Memory Limit Exceeded"
}

{
    "code_tokens": "import java.util.Scanner;\n\nclass Main{\n\tpublic static void main(String args[]){\n\t\tScanner scanner = new Scanner(System.in);\n\n\t\t\tString str = new String();\n\t\t\twhile((str = scanner.next()) != null){\n\t\t\t\tint n = Integer.parseInt(str);\n\t\t\t\tif(n == 0) return;\n\n\t\t\t\tfor(int i = 0; i < n; i++){\n\t\t\t\t\tscanner.next();\n\t\t\t\t}\n\n\t\t\t}\n\t}\n}",
    "verdict": "Memory Limit Exceeded"
}

{
    "code_tokens": "import java.io.*;\nclass Xcubic {\n\tstatic void main(String[] args) {\n\t\tBufferedReader reader = new BufferedReader(new InputStreamReader(System.in));\n        try {\n        \tString line = reader.readLine();\n        \tint x = Integer.parseInt(line);\n        \tint y = (x * x * x);\n        \tif (x >= 2 && x <= 100) {\n        \t\tSystem.out.println(y);\n        \t} else {\n        \t\tSystem.out.println(\"error:number is 1 to 100\");\n        \t}\n        } catch (IOException e) {\n          System.out.println(e);\n        } \n      }\n    }",
    "verdict": "Runtime Error"
}

{
    "code_tokens": "class Main{static{int i,j;for(i=1;i<10;i++)for(j=1;j<10;)System.out.println(i+\"x\"+j+\"=\"+i*j++);}}",
    "verdict": "Runtime Error"
}

{
    "code_tokens": "import java.util.HashMap;\nimport java.util.Scanner;\n\nclass Main{\n\n\tstatic Scanner scanner = new Scanner(System.in);\n\tstatic HashMap<Integer, Integer> map;\n\n\tpublic static void main(String args[]){\n\n\t\twhile(true){\n\t\t\tint n = scanner.nextInt();\n\t\t\tmap = new HashMap<Integer, Integer>();\n\t\t\tif(n == 0) break;\n\t\t\tsolve(n);\n\t\t\tSystem.gc();\n\t\t}\n\t}\n\n\tstatic void solve(int n){\n\t\tfor(int i = 0; i < n; i++){\n\t\t\tscanner.next();\n\t\t\tif(i % 100 == 99) System.gc();\n\t\t}\n\t}\n}",
    "verdict": "Time Limit Exceeded"
}

{
    "code_tokens": "import java.util.Scanner;\n\npublic class Main {\n\tstatic long sum;\n\n\tpublic static void main(String[] args) throws Exception {\n\t\tScanner sc = new Scanner(System.in);\n\t\twhile (true) {\n\t\t\tint n = sc.nextInt();\n\t\t\tif (n == 0)\n\t\t\t\tbreak;\n\t\t\tsum = 0;\n\t\t\tsolve(n);\n\t\t\tSystem.out.println((sum / 10 + 1) / 365 + 1);\n\t\t}\n\t}\n\n\tpublic static void solve(int n) {\n\t\tif (n < 0)\n\t\t\treturn;\n\t\tif (n == 0) {\n\t\t\tsum += 1;\n\t\t\treturn;\n\t\t}\n\t\tfor (int i = 1; i <= 3; i++) {\n\t\t\tsolve(n - i);\n\t\t}\n\t}\n}",
    "verdict": "Time Limit Exceeded"
}

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
    return f"{json.dumps(prompt_obj, indent=2)}\n\n{prompt_template}"

def ask_openrouter(prompt):
    """Ask the OPENAI API a question."""

    max_retries = 5
    retry_count = 1
    wait_time = 3  # Initial wait time in seconds - reduced for Flash-Lite

    while retry_count < max_retries:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                    "role": "user",
                    "content": prompt
                    }
                ]
            )
            return completion.choices[0].message.content
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
                prompt = generate_prompt(code_obj)
                response_text = ask_openrouter(prompt)
                
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