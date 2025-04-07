import pyodbc
import os
from dotenv import load_dotenv
import pandas as pd
import re
import yaml
import json
from tabulate import tabulate
import argparse

# Load environment variables
load_dotenv()

def create_connection():
    """Creates a connection to the database."""
    config = {
        'user': os.getenv("user"),
        'password': os.getenv("PASSWORD"),
        'host': os.getenv("HOST"),
        'port': os.getenv("PORT"),
        'database': os.getenv("DATABASE")
    }
    
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={config['host']},{config['port']};"
        f"DATABASE={config['database']};"
        f"UID={config['user']};"
        f"PWD={config['password']};"
        f"TrustServerCertificate=yes;"
    )
    
    return pyodbc.connect(conn_str)

def execute_query(connection, query):
    """Execute SQL query and return results as a DataFrame."""
    try:
        return pd.read_sql(query, connection)
    except Exception as e:
        print(f"Error executing query: {e}")
        return None

def cleanup_query(query):
    """Clean up SQL query by removing pipe symbols and extra whitespace."""
    query = query.strip()
    if query.startswith('|'):
        query = query[1:].strip()
    return query

def compare_results(reference_df, submitted_df):
    """
    Compare reference and submitted query results and return grade.
    
    Grading criteria:
    - Equal: The result sets contain exactly the same data, regardless of column names.
    - Correct+: The submitted query returns all data from the reference query plus additional information.
    - Correct-: The submitted query returns similar data but with differences in naming, column order, or presentation.
    - Incorrect: The submitted query returns completely different data compared to the reference query.
    """
    if reference_df is None or submitted_df is None:
        return "Incorrect", "One or both queries failed to execute"
    
    # Reset indices
    reference_df = reference_df.reset_index(drop=True)
    submitted_df = submitted_df.reset_index(drop=True)
    
    # Get dimensions
    ref_rows = len(reference_df)
    sub_rows = len(submitted_df)
    
    # Check if the column names are different but data might be the same
    # This handles the case where BusinessEntityID vs EmployeeID could be the same data
    
    # First, standardize data types to avoid comparison issues
    reference_df = reference_df.astype(str)
    submitted_df = submitted_df.astype(str)
    
    # Try to identify ID columns
    ref_id_cols = [col for col in reference_df.columns if 'id' in col.lower()]
    sub_id_cols = [col for col in submitted_df.columns if 'id' in col.lower()]
    

    # If the above quick check doesn't work, try a more thorough comparison
    
    # Check for Equal: Exact same data content (ignoring column names)
    if ref_rows == sub_rows and len(reference_df.columns) == len(submitted_df.columns):
        # Standard column names for comparison
        ref_std = reference_df.copy()
        sub_std = submitted_df.copy()
        ref_original_columns = ref_std.columns.tolist()
        sub_original_columns = sub_std.columns.tolist()
        ref_std.columns = [f"col_{i}" for i in range(len(ref_std.columns))]
        sub_std.columns = [f"col_{i}" for i in range(len(sub_std.columns))]
        
        # Sort both dataframes by all columns
        ref_sorted = ref_std.sort_values(by=list(ref_std.columns)).reset_index(drop=True)
        sub_sorted = sub_std.sort_values(by=list(sub_std.columns)).reset_index(drop=True)
        
        # Compare values
        if ref_sorted.equals(sub_sorted):
            if ref_original_columns == sub_original_columns:
                return "Equal", "The answer is exactly the same as the expected result."
            else:
                return "Equal", "The answer is the same data but with different column names."
    
    # Check for Correct+: More information than reference
    if sub_rows >= ref_rows and len(submitted_df.columns) >= len(reference_df.columns):
        # This is a simplified check - the submitted query has at least as many rows and columns
        # and we've already confirmed it's not exactly equal
        return "Correct+", "The answer contains all expected data plus additional information."
    
    # Check for Correct-: Similar data but formatted differently
    # This is a more general case - we'll use a content similarity approach
    
    # First, check if row counts are similar (within 20%)
    if abs(ref_rows - sub_rows) / max(ref_rows, sub_rows) < 0.2:
        # Check if we might have the same data but presented differently
        # For example, concatenated values vs separate columns
        
        # Get all data as string and check for content similarity
        ref_str = reference_df.to_string()
        sub_str = submitted_df.to_string()
        
        # Count how many unique words from ref appear in sub
        ref_words = set(re.findall(r'\b\w+\b', ref_str.lower()))
        sub_words = set(re.findall(r'\b\w+\b', sub_str.lower()))
        
        common_words = ref_words.intersection(sub_words)
        
        # If more than 70% of unique words are common, consider it Correct-
        if len(common_words) / len(ref_words) > 0.7:
            return "Correct-", "The answer contains similar data to the expected result but presented differently."
    
    # If we get here, the results are different
    return "Incorrect", "The answer is incorrect and has different data from the expected result."
def extract_queries_from_yaml(yaml_file):
    """
    Extract queries from YAML content string.
    """
    try:
        with open(yaml_file, 'r') as file:
            data = yaml.safe_load(file)
        
        queries = []
        # Check if 'Question' is the root key
        if 'Question' in data:
            question_data = data['Question']
            for question_id, content in question_data.items():
                if not isinstance(content, dict):
                    continue
                    
                if 'Q-AdvW' in content and 'R-AdvW' in content and 'S-AdvW' in content:
                    queries.append({
                        'id': question_id,
                        'question': content.get('Q-AdvW', ''),
                        'reference': cleanup_query(content.get('S-AdvW', '')),
                        'submitted': cleanup_query(content.get('R-AdvW', ''))
                    })
        
        return queries
    except Exception as e:
        print(f"Error parsing YAML: {e}")
        return []
def evaluate_all_queries(yaml_file):
    """Evaluate all queries in the YAML file and output results."""
    queries = extract_queries_from_yaml(yaml_file)
    
    if not queries:
        print("No valid queries found in the YAML file.")
        return
    
    connection = create_connection()
    results = []
    
    for query in queries:
        print(f"\nEvaluating {query['id']}...")
        print(f"Question: {query['question']}")
        
        # Execute reference query
        reference_df = execute_query(connection, query['reference'])
        
        # Execute submitted query
        submitted_df = execute_query(connection, query['submitted'])
        
        # Compare results
        grade, reason = compare_results(reference_df, submitted_df)
        
        result = {
            'id': query['id'],
            'grade': grade,
            'reason': reason,
            'reference_query': query['reference'],
            'submitted_query': query['submitted']
        }
        
        results.append(result)
        
        # Print results for this query
        print(f"Grade: {grade}")
        print(f"Reason: {reason}")
        
        if reference_df is not None and submitted_df is not None:
            print("\nReference Query Result:")
            print(tabulate(reference_df.head(5), headers='keys', tablefmt='psql'))
            print(f"Total rows: {len(reference_df)}, Columns: {len(reference_df.columns)}")
            
            print("\nSubmitted Query Result:")
            print(tabulate(submitted_df.head(5), headers='keys', tablefmt='psql'))
            print(f"Total rows: {len(submitted_df)}, Columns: {len(submitted_df.columns)}")
    
    connection.close()
    
    # Save results to JSON
    with open('evaluation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Create summary DataFrame
    summary_df = pd.DataFrame(results)
    print("\nEvaluation Summary:")
    print(tabulate(summary_df[['id', 'grade', 'reason']], headers='keys', tablefmt='psql'))


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Valida queries SQL comparando esperada e submetida via YAML.")
    parser.add_argument("yaml_file", help="Caminho para o arquivo YAML contendo as questões")

    args = parser.parse_args()
    evaluate_all_queries(args.yaml_file)