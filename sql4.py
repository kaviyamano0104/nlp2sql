"""
adding chromadb and own openai
using pydantic for validation
 
"""
 
import streamlit as st
import mysql.connector
from pydantic import ValidationError
from func4 import login_with_firebase, generate_automated_documentation, get_schema, clear_trained_data, engineer_prompt, auth, vn, SQLQuery
 
# Custom CSS for background color and centered login form
st.markdown("""
    <style>
        body {
            background-color: #f0f2f6;
        }
        .login-form {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .login-title {
            text-align: center;
            margin-bottom: 1rem;
        }
        .login-input {
            margin-bottom: 1rem;
        }
        .stButton button {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .stButton button:hover {
            background-color: #0056b3;
        }
    </style>
""", unsafe_allow_html=True)
 
# Streamlit app code
st.title("Welcome to NL2SQL Training App")
 
# Initialize session state
if 'user' not in st.session_state:
    st.session_state.user = None
if 'token' not in st.session_state:
    st.session_state.token = None
if 'selected_db' not in st.session_state:
    st.session_state.selected_db = None
if 'training_completed' not in st.session_state:
    st.session_state.training_completed = False
if 'db_params' not in st.session_state:
    st.session_state.db_params = {}
if 'schema' not in st.session_state:
    st.session_state.schema = {}
if 'table_names' not in st.session_state:
    st.session_state.table_names = []
if 'database_list' not in st.session_state:
    st.session_state.database_list = []
 
# Check if the user is logged in
logged_in = st.session_state.user is not None
 
if not logged_in:
    st.markdown('<h2 class="login-title">Login Page</h2>', unsafe_allow_html=True)
    email = st.text_input("Email", key="email")
    password = st.text_input("Password", type="password", key="password")
    if st.button("Login"):
        if login_with_firebase(email, password):
            st.success("Login successful!")
            st.experimental_rerun()  # Refresh the page to reflect login state
else:
    # Add the list of tables to the sidebar
    with st.sidebar:
        if st.button("Logout"):
            auth.current_user = None
            st.session_state.user = None
            st.session_state.token = None
            st.session_state.selected_db = None
            st.session_state.training_completed = False
            st.session_state.table_names = []  # Clear the table names
            st.session_state.database_list = []  # Clear the database list
            st.session_state.schema = {}
            clear_trained_data()
            st.sidebar.success("Logout successful!")
            st.experimental_rerun()  # Refresh the page to reflect logout state
 
        st.header("Database Tables")
        if st.session_state.table_names:
            st.write("Tables in the database:")
            for table in st.session_state.table_names:
                st.write(f"- {table}")
        else:
            st.write("No tables available")
 
    if logged_in and not st.session_state.training_completed:
        st.markdown('<h2 class="login-title">Select Database and Start Training</h2>', unsafe_allow_html=True)
       
        # Connect to the MySQL server to retrieve the list of databases
        host = st.text_input("MySQL Host", value="localhost")
        user = st.text_input("MySQL User", value="root")
        password = st.text_input("MySQL Password", type="password")
        port = st.number_input("Port", value=3306)
 
        if st.button("Fetch Databases"):
            try:
                conn = mysql.connector.connect(
                    host=host,
                    user=user,
                    password=password,
                    port=port
                )
                cursor = conn.cursor()
                cursor.execute("SHOW DATABASES")
                databases = cursor.fetchall()
                st.session_state.database_list = [db[0] for db in databases if db[0] not in ('information_schema', 'performance_schema', 'mysql', 'sys')]
                cursor.close()
                conn.close()
                st.write("Databases fetched successfully.")
            except mysql.connector.Error as e:
                st.error(f"Database connection failed: {e}")
 
        selected_db = st.selectbox("Select a Database", st.session_state.database_list)
 
        if st.button("Start Training"):
            if selected_db:
                try:
                    # Store database connection parameters in session state
                    st.session_state.db_params = {
                        'host': host,
                        'user': user,
                        'password': password,
                        'dbname': selected_db,
                        'port': port
                    }
                   
                    # Connect to the specified database
                    conn = mysql.connector.connect(
                        host=host,
                        user=user,
                        password=password,
                        database=selected_db,
                        port=port
                    )
                   
                    cursor = conn.cursor()
                    # Ensure we are working with the correct database
                    cursor.execute(f"USE {selected_db}")
                   
                    # Connect Vanna to the specified database
                    vn.connect_to_mysql(host=host, dbname=selected_db, user=user, password=password, port=port)
                   
                    # Retrieve the information schema
                    df_information_schema = vn.run_sql(f"""
                        SELECT *
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = '{selected_db}'
                    """)
                   
                    # Break up the information schema into bite-sized chunks for the model
                    plan = vn.get_training_plan_generic(df_information_schema)
                    st.write("Training Plan Generated:")
                    st.write(plan)
                    with st.spinner("Training the model and generating documentation. Please wait..."):
                        # Train the model
                        vn.train(plan=plan)
                   
                        # Generate automated documentation
                        st.session_state.schema = get_schema(st.session_state.db_params)
                        documentation = generate_automated_documentation(st.session_state.schema)
                        st.write("Automated Documentation Generated:")
                        st.write(documentation)
                   
                    # Train the Vanna model with the generated documentation
                    vn.train(documentation=documentation)
                   
                    st.session_state.training_completed = True
                    st.success(f"Training completed for database: {selected_db}")
                   
                    # Debug statement to check if table names are stored
                    st.write(f"Table names stored in session state: {st.session_state.table_names}")
                   
                    cursor.close()
                    conn.close()
                except mysql.connector.Error as e:
                    st.error(f"Database connection failed: {e}")
                except Exception as e:
                    st.error(f"An error occurred during training: {e}")
            else:
                st.warning("Please select a database to train.")
 
    if logged_in and st.session_state.training_completed:
        st.markdown('<h2 class="login-title">Chatbot Interface</h2>', unsafe_allow_html=True)
 
        question = st.text_input("Ask a question about your data")
 
        if st.button("Submit Question"):
            db_params = st.session_state.db_params
            successful_execution = False
           
 
            for _ in range(5):  # Retry up to 5 times
                try:
                    # Generate SQL query from the question
                    engineered_question = engineer_prompt(question, st.session_state.db_params['dbname'],st.session_state.schema)
                    sql = vn.generate_sql(engineered_question)
                   
 
                    # Validate SQL query using Pydantic
                    try:
                        query = SQLQuery(sql=sql)
                    except ValidationError as e:
                        break
 
                    # Connect to the database and execute the query
                    vn.connect_to_mysql(
                        host=db_params['host'],
                        dbname=db_params['dbname'],
                        user=db_params['user'],
                        password=db_params['password'],
                        port=db_params['port']
                    )
                    df = vn.run_sql(sql)
                    st.write(f"Generated SQL Query: {sql}")
 
                    # Run the SQL query
                   
                    code = vn.generate_plotly_code(question=question, sql=sql, df=df)
 
                   
                    fig = vn.get_plotly_figure(plotly_code=code, df=df)
 
                    # Display the question and the resulting dataframe
                    st.text(question)
                    st.dataframe(df, use_container_width=True)
                    st.plotly_chart(fig, use_container_width=True)
                    successful_execution = True
                    break  # Exit the retry loop on success
                except Exception:
                    pass  # Ignore the error and retry
 
            if not successful_execution:
                st.write("Please modify your question or Check your token")
                st.write("Note: You can only view the data from the database; modification of the data is not allowed.")
    else:
        st.write("Please login to access the application.")
 
 
 
 