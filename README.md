# AskSQL - Transform Natural Language into SQL and Reports

## Project Description

**AskSQL** is a tool that converts natural language queries into optimized SQL statements, enabling the generation of dynamic reports and charts. This allows users without advanced database experience to gain insights from intuitive questions, speeding up data analysis.

## Features
- **Natural Language to SQL Conversion**: Translate simple questions into efficient SQL queries.
- **Query Execution**: Integrate with databases to run the generated queries directly.
- **Report Generation**: Create dynamic reports based on the returned data.
- **Chart Creation**: Visualize data through customizable charts.
- **Intuitive Interface**: Simplified experience to make it easy for any user.


## How to Use

1. **Create account on Groq.ai**: Sign up for an account on [Groq.com](https://groq.com).
2. **Get API Key**: After signing up, obtain your API key from the Groq dashboard.

3. **Clone the repository**:
   ```bash
   git clone git@github.com:cristiano-nicolau/AskSQL.git
   cd AskSQL
   ```

4. **Create a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

5. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
6. **Set up environment variables**: Create a `.env` file in the root directory and add your database connection details and Groq.ai API key:
   ```plaintext
   user=db_user
   PASSWORD=db_password
   HOST=db_host
   PORT=db_port
   DATABASE=db_name

   API_KEY=your_groq_api_key
   ```

7. **Run the application**:
   ```bash
   streamlit run app.py
   ```

8. **Access the application**: Open your web browser and go to `http://localhost:8501` to access the AskSQL interface.

## Contributing
We welcome contributions! If you have suggestions or improvements, please fork the repository and submit a pull request.




