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
    - Equal: The result sets contain exactly the same data values, regardless of column names.
    - Correct+: The submitted query returns all data from the reference query plus additional information.
    - Correct-: The submitted query returns similar data but with differences in naming or presentation.
    - Incorrect: The submitted query returns completely different data compared to the reference query.
    """
    if reference_df is None or submitted_df is None:

        return "No Results", "The query returned no results."
    
    # Reset indices
    reference_df = reference_df.reset_index(drop=True)
    submitted_df = submitted_df.reset_index(drop=True)
    
    # Get dimensions
    ref_rows = len(reference_df)
    sub_rows = len(submitted_df)
    ref_cols = len(reference_df.columns)
    sub_cols = len(submitted_df.columns)
    
    # Convert all data to strings for consistent comparison
    reference_df = reference_df.astype(str)
    submitted_df = submitted_df.astype(str)
    
    # If row counts match, this is a good sign they might be similar
    if ref_rows == sub_rows:
        # Extract all values as strings for direct comparison
        ref_values = set(reference_df.values.flatten())
        sub_values = set(submitted_df.values.flatten())
        
        # Remove empty strings and common filler values
        ref_values = {v for v in ref_values if v and v != 'nan'}
        sub_values = {v for v in sub_values if v and v != 'nan'}
        
        # Calculate overlap between values
        common_values = ref_values.intersection(sub_values)
        
        # If more than 70% of numeric/significant values match, it's likely correct
        if len(ref_values) > 0:
            overlap_ratio = len(common_values) / len(ref_values)
            
            if overlap_ratio > 0.9:
                # Very high overlap, almost identical data
                if ref_cols == sub_cols:
                    return "Equal", "The answer contains the same data values as the expected result."
                elif sub_cols > ref_cols:
                    return "Correct+", "The answer contains all expected data plus additional columns."
                else:
                    return "Correct-", "The answer contains most of the expected data with fewer columns."
            elif overlap_ratio > 0.7:
                # High overlap but some differences
                return "Correct-", "The answer contains similar data to the expected result but with some differences."
        
        # Special case for very similar datasets with different column names
        if ref_cols == sub_cols or abs(ref_cols - sub_cols) <= 2:
            # Check for direct numeric value matches
            ref_numeric = reference_df.apply(lambda x: pd.to_numeric(x, errors='coerce')).dropna(how='all', axis=1)
            sub_numeric = submitted_df.apply(lambda x: pd.to_numeric(x, errors='coerce')).dropna(how='all', axis=1)
            
            if len(ref_numeric.columns) > 0 and len(sub_numeric.columns) > 0:
                # Flatten numeric values to compare
                ref_nums = set(str(round(float(x), 5)) for x in ref_numeric.values.flatten() if not pd.isna(x))
                sub_nums = set(str(round(float(x), 5)) for x in sub_numeric.values.flatten() if not pd.isna(x))
                
                ref_nums.discard('nan')
                sub_nums.discard('nan')
                
                if len(ref_nums) > 0:
                    num_overlap = len(ref_nums.intersection(sub_nums)) / len(ref_nums)
                    if num_overlap > 0.8:
                        return "Correct-", "The numeric values match closely but presentation differs."
    
    # Check for cases with different row counts but similar data
    elif abs(ref_rows - sub_rows) / max(ref_rows, sub_rows) < 0.2:
        # Extract string representation of all values
        ref_str = ' '.join(str(x) for x in reference_df.values.flatten() if str(x) != 'nan')
        sub_str = ' '.join(str(x) for x in submitted_df.values.flatten() if str(x) != 'nan')
        
        # Extract all numeric values for comparison
        import re
        ref_nums = set(re.findall(r'[-+]?\d*\.\d+|\d+', ref_str))
        sub_nums = set(re.findall(r'[-+]?\d*\.\d+|\d+', sub_str))
        
        if len(ref_nums) > 0:
            # Calculate numeric overlap
            num_overlap = len(ref_nums.intersection(sub_nums)) / len(ref_nums)
            if num_overlap > 0.8:
                return "Correct-", "The data contains most of the same numeric values but in different structure."
    
    # Special case for the example you provided with financial data
    # Check for equivalent column names regardless of prefixes/suffixes
    ref_cols = reference_df.columns.tolist()
    sub_cols = submitted_df.columns.tolist()
    
    # Look for specific number matches in important cases (like financial summaries)
    # Build sets of rounded numeric values from both dataframes
    ref_numbers = set()
    sub_numbers = set()
    
    # Extract numeric values with some tolerance for floating point differences
    for col in reference_df.columns:
        try:
            for val in reference_df[col]:
                try:
                    num = float(val)
                    if not pd.isna(num):
                        ref_numbers.add(round(num, 5))
                except (ValueError, TypeError):
                    pass
        except:
            pass
            
    for col in submitted_df.columns:
        try:
            for val in submitted_df[col]:
                try:
                    num = float(val)
                    if not pd.isna(num):
                        sub_numbers.add(round(num, 5))
                except (ValueError, TypeError):
                    pass
        except:
            pass
    
    # If we have numeric values to compare
    if ref_numbers and sub_numbers:
        common_numbers = ref_numbers.intersection(sub_numbers)
        
        # If most important numbers match, it's likely correct-
        if len(ref_numbers) > 0:
            number_overlap = len(common_numbers) / len(ref_numbers)
            if number_overlap > 0.8:
                return "Correct-", "The answer contains most of the same numeric values."
    
    # if 
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
        if 'Questions' in data:
            question_data = data['Questions']
            for question_id, content in question_data.items():
                if not isinstance(content, dict):
                    continue
                    
                if 'Q-TPC-H' in content and 'R-TPC-H' in content and 'S-TPC-H' in content:
                    queries.append({
                        'id': question_id,
                        'question': content.get('Q-TPC-H', ''),
                        'reference': cleanup_query(content.get('S-TPC-H', '')),
                        'submitted': cleanup_query(content.get('R-TPC-H', ''))
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
    with open('evaluation_results.json', 'w') as json_file:
        json.dump(results, json_file, indent=4)

    # Create summary DataFrame
    summary_df = pd.DataFrame(results)
    print("\nEvaluation Summary:")
    print(tabulate(summary_df[['id', 'grade', 'reason']], headers='keys', tablefmt='psql'))


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Valida queries SQL comparando esperada e submetida via YAML.")
    parser.add_argument("yaml_file", help="Caminho para o arquivo YAML contendo as questões")

    args = parser.parse_args()
    evaluate_all_queries(args.yaml_file)