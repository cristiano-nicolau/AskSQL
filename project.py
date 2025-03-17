import pyodbc
from groq import Groq
import os
from dotenv import load_dotenv
load_dotenv() 

# Definição dos parâmetros de conexão
config = {
    'user': os.getenv("user"),
    'password': os.getenv("PASSWORD"),
    'host': os.getenv("HOST"),
    'port': os.getenv("PORT"),
    'database': os.getenv("DATABASE")
}

# String de conexão
conn_str = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={config['host']},{config['port']};"
    f"DATABASE={config['database']};"
    f"UID={config['user']};"
    f"PWD={config['password']};"
    f"TrustServerCertificate=yes;"
)

try:
    # Criar conexão

    conn = pyodbc.connect(conn_str)
    print("Conexão bem-sucedida!")
    
    # Criar cursor
    cursor = conn.cursor()

    data = {}
    cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    tables = cursor.fetchall()

    for schema, table in tables:
        cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?", (schema, table))
        columns = cursor.fetchall()
        for columns_name, data_type in columns:
            if f"{schema}.{table}" not in data:
                data[f"{schema}.{table}"] = []
            data[f"{schema}.{table}"].append(columns_name)

    print(data)
    
    # Fechar conexão
    cursor.close()
    conn.close()

    query = ["List all students who are subscrived in the Database Systems and are born in 2003.",
             "List names of employees who have a salary greater than $1300, work in the city of Oporto and are younger than 30 years."]

    # import api key from .env file
    client = Groq(api_key= os.getenv("API_KEY"))

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
        temperature=0.5,

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

    # Print the completion returned by the LLM.
    print(chat_completion.choices[0].message.content)
    def generate_query(msg):
        # Vamos receber toda a resposta do Groq e retornar apenas a query, quero só do ```sql ... ```
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
        return query
    print(generate_query(chat_completion.choices[0].message.content))

except Exception as e:
    print("Erro ao conectar:", e)