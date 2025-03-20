import streamlit as st
import pyodbc
from groq import Groq
import os
from dotenv import load_dotenv
import json
import pandas as pd
load_dotenv() 

def create_connection():
    """Cria a conexão com o banco de dados."""
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

def get_tables(conn):
    """Obtém a estrutura das tabelas, colunas, tipos de dados e conexões entre tabelas."""
    cursor = conn.cursor()
    data = {}
    
    # Obter todas as tabelas
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
    """)
    tables = cursor.fetchall()
    
    for schema, table in tables:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """, (schema, table))
        columns = cursor.fetchall()
        data[f"{schema}.{table}"] = {
            "columns": [(col[0], col[1]) for col in columns],
            "foreign_keys": []
        }
    
    # Obter as conexões (chaves estrangeiras)
    cursor.execute("""
        SELECT 
            fk.TABLE_SCHEMA AS SchemaName,
            fk.TABLE_NAME AS TableName,
            cu.COLUMN_NAME AS ColumnName,
            pk.TABLE_SCHEMA AS RefSchemaName,
            pk.TABLE_NAME AS RefTableName,
            cpk.COLUMN_NAME AS RefColumnName
        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk ON rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cu ON fk.CONSTRAINT_NAME = cu.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cpk ON pk.CONSTRAINT_NAME = cpk.CONSTRAINT_NAME;
    """)
    foreign_keys = cursor.fetchall()
    
    for fk in foreign_keys:
        schema, table, column, ref_schema, ref_table, ref_column = fk
        key = f"{schema}.{table}"
        if key in data:
            data[key]["foreign_keys"].append({
                "column": column,
                "references": f"{ref_schema}.{ref_table}({ref_column})"
            })
    
    cursor.close()
    return data



def model(query, data, client):
    """Gera a query SQL a partir de uma pergunta em linguagem natural."""

    chat_completion = client.chat.completions.create(
        #
        # Required parameters
        #
        messages=[
            # Set an optional system message. This sets the behavior of the
            # assistant and can be used to provide specific instructions for
            # how it should behave throughout the conversation.
            {
                "role": "system",
                "content": "you are a helpful assistant."
            },
            # Set a user message for the assistant to respond to.
            {
                "role": "user",
                "content": f"Convert the following statement: {query} into SQL Query, tables schema: {data}, SQL Server."
            }
        ],

        # The language model which will generate the completion.
        model="llama-3.3-70b-versatile",

        #
        # Optional parameters
        #

        # Controls randomness: lowering results in less random completions.
        # As the temperature approaches zero, the model will become deterministic
        # and repetitive.
        temperature=0.2,

        # The maximum number of tokens to generate. Requests can use up to
        # 32,768 tokens shared between prompt and completion.
        max_completion_tokens=1024,

        # Controls diversity via nucleus sampling: 0.5 means half of all
        # likelihood-weighted options are considered.
        top_p=1,

        # A stop sequence is a predefined or user-specified text string that
        # signals an AI to stop generating content, ensuring its responses
        # remain focused and concise. Examples include punctuation marks and
        # markers like "[end]".
        stop=None,

        # If set, partial message deltas will be sent.
        stream=False,
    )

    return chat_completion.choices[0].message.content

def generate_query(msg):
    """Gera a query SQL a partir de uma pergunta em linguagem natural."""
    query = ""
    inside_sql_block = False
    for line in msg.split("\n"):
        if line.strip().startswith("```sql"):
            inside_sql_block = True
            continue
        if line.strip().startswith("```") and inside_sql_block:
            inside_sql_block = False
            continue
        if inside_sql_block:
            query += line + "\n"
    # tiver um ; na query so quero o que esta ate esse ;
    if ";" in query:
        query = query.split(";")[0]
    return query.strip()

def execute_query_report(query, conn):
    """
    Executes a SQL query and returns both DataFrame and raw data formats.
    
    Args:
        query (str): SQL query to execute
        conn: Database connection object
        
    Returns:
        tuple: (pandas DataFrame, raw data, column names)
    """
    cursor = conn.cursor()
    cursor.execute(query)
    
    # Get column names from cursor description
    columns = [column[0] for column in cursor.description]
    
    # Fetch raw data
    raw_data = cursor.fetchall()
    
    # Convert to pandas DataFrame for formatted display
    df = pd.DataFrame.from_records(raw_data, columns=columns)
    
    cursor.close()
    
    return df, raw_data, columns

def execute_query_chart(query, conn):
    """Gera um gráfico a partir de uma query SQL."""
    pass

def process_command(command, option):
    """Process special commands that start with /"""

    if command == "/explain":
        # TODO: Parte do /explain que explica os resultados anteriores 
        if option in ["Report Generation", "Chart Generation"]:
            return {
                "role": "assistant", 
                "content": "**AskSQL Explanation**\n\nThis app helps you query databases using natural language. Just type your question about the data, and I'll generate the SQL query for you. For example, try asking 'Show me the students who are enrolled in the Database Systems course'.\n\nYou can choose between three modes:\n1. **Report Generation**: Get results in a table format\n2. **Chart Generation**: Visualize your data\n3. **SQL Query Generation**: Just see the SQL query without running it"
            }
        else:
            return {
                "role": "assistant", 
                "content": "The /explain command is only available in Report Generation and Chart Generation modes."
            }
    elif command == "/reset":
        st.session_state[f"messages_{option}"] = []
        st.session_state[f"messages_{option}"].append({"role": "assistant", "content": "Chat history has been reset.\n How can I help you today?"})
        st.rerun()
    else:
        available_commands = "Available commands:\n\n"
        if option in ["Report Generation", "Chart Generation"]:
            available_commands += "- **/explain <your prompt>**: Get explanation about the app and how to use it.\n"
        
        available_commands += "- **/help**: Display this help message.\n- **/reset**: Reset the conversation history."
        
        return {
            "role": "assistant", 
            "content": f"**AskSQL Explanation**\n\nThis app helps you query databases using natural language. Just type your question about the data, and I'll generate the SQL query for you. For example, try asking 'Show me the students who are enrolled in the Database Systems course'.\n\nYou can choose between three modes:\n1. **Report Generation**: Get results in a table format\n2. **Chart Generation**: Visualize your data\n3. **SQL Query Generation**: Just see the SQL query without running it \n\n{available_commands}"
        }

def main():
    if 'conn' not in st.session_state:
        with st.spinner("Trying to connect to the database and fetch the tables schema..."):
            st.session_state.conn = create_connection()
            st.session_state.data = get_tables(st.session_state.conn)
            st.session_state.client = Groq(api_key=os.getenv("API_KEY"))
            st.toast("Connected to the database and fetched the tables schema.", icon="✅")
    
    initial_message = {"role": "assistant", "content": "Hello! I'm AskSQL, your assistant. How can I help you today?"}
    
    with st.sidebar:
        st.title("AskSQL")
        st.caption("AskSQL is a tool that allows the conversion of natural language queries into optimized SQL queries, enabling the generation of dynamic reports and charts. This allows users without advanced database experience to gain insights from intuitive questions, accelerating data analysis.\n")
        
        st.title("What do you want to do?")
        option = st.selectbox("Select the option that best fits your needs", 
                              ["Report Generation", "Chart Generation", "SQL Query Generation"],
                              key="option_select")
        st.title("How does it work?")
        st.markdown("1. **Ask a question**: Enter a question in natural language, such as 'List all students who are subscrived in the Sistemas de Base de Dados and are born in 2003.'")
        st.markdown("2. **Get the SQL query**: The tool will generate the SQL query based on the question asked.")
        st.markdown("3. **Generate reports and charts**: Use the generated SQL query to generate reports and charts based on the data in your database.")   

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Reset Chat"):
                st.session_state.messages = []
                for option in ["Report Generation", "Chart Generation", "SQL Query Generation"]:
                    st.session_state[f"messages_{option}"] = [initial_message]
                

        st.title("Database DDL")
        # put hear the data from the database
        for table, info in st.session_state.data.items():
            st.subheader(table)
            for col, dtype in info["columns"]:
                st.write(f"- {col} ({dtype})")
            for fk in info["foreign_keys"]:
                st.write(f"- FOREIGN KEY ({fk['column']}) REFERENCES {fk['references']}")
            st.write("---")
        st.caption("This is the schema of the tables in your database. Use this information to ask questions about the data in your database.")


    st.markdown("""
        <style>
        .command-tag {
            color: #00b894;
            font-weight: bold;
        }
        </style>
     """, unsafe_allow_html=True)

    if f"messages_{option}" not in st.session_state:
        st.session_state[f"messages_{option}"] = [initial_message]

    for msg in st.session_state[f"messages_{option}"]:
        if "raw_data" in msg:
            st.dataframe(msg["raw_data"])
            with st.expander("View Raw Data"):
                st.write(msg["content"])
        else:
            content = msg["content"]
            if msg["role"] == "user" and content.startswith("/"):
                command = content.split()[0]
                styled_content = f'<span class="command-tag">{command}</span> {content[len(command):]}'
                st.chat_message(msg["role"]).markdown(styled_content, unsafe_allow_html=True)
            else:
                st.chat_message(msg["role"]).write(content)

    prompt = st.chat_input("Ask me a question")

    if prompt:
        st.session_state[f"messages_{option}"].append({"role": "user", "content": prompt})

        if prompt.startswith("/"):
            command = prompt.split()[0]
            styled_prompt = f'<span class="command-tag">{command}</span> {prompt[len(command):]}'
            st.chat_message("user").markdown(styled_prompt, unsafe_allow_html=True)
        else:
            st.chat_message("user").write(prompt)
        
        if prompt.startswith("/"):
            command = prompt.split()[0]
            command_response = process_command(command, option)
            
            if command_response:
                st.session_state[f"messages_{option}"].append(command_response)
                st.chat_message("assistant").write(command_response["content"])

        else:
            if option == "SQL Query Generation":
                sql_query = model(prompt, st.session_state.data, st.session_state.client)
                st.session_state[f"messages_{option}"].append({"role": "assistant", "content": f"Here is the SQL query:\n{sql_query}\n"})
                st.chat_message("assistant").write(f"Here is the SQL query:\n{sql_query}\n")

            elif option == "Report Generation":
                sql_query = model(prompt, st.session_state.data, st.session_state.client)
                clean_query = generate_query(sql_query)
                try:
                    df, raw_data, columns = execute_query_report(clean_query, st.session_state.conn)
                    st.dataframe(df)
                    with st.expander("View Raw Data"):
                        st.write(raw_data)
                    st.session_state[f"messages_{option}"].append({"role": "assistant", "content": raw_data, "raw_data": df})
                except Exception as e:
                    error_message = f"Error executing query: {str(e)}\n\nGenerated query:\n```sql\n{clean_query}\n```"
                    st.session_state[f"messages_{option}"].append({"role": "assistant", "content": error_message})
                    st.chat_message("assistant").write(error_message)
                    
            elif option == "Chart Generation":
                pass
if __name__ == "__main__":
    main()
