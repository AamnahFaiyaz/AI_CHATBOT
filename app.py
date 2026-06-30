import streamlit as st
import snowflake.connector
import google.generativeai as genai
import os
import json
import pandas as pd

# 1. Page Configuration & Title Styling
st.set_page_config(page_title="Tata SNTI AI Chatbot", layout="wide", page_icon="🤖")
st.title("🤖 Tata SNTI AI Chatbot")
st.markdown("### Natural Language Interface for IoT Manufacturing Analytics")
st.markdown("---")

# 2. Comprehensive Database Schema Catalog (The absolute system context map for Gemini)
DATABASE_SCHEMA_CATALOG = """
You are an expert Oracle and Snowflake SQL translation engine for Tata Steel. 
You must follow these strict database, syntax, and routing rules:

1. TARGET TABLE ROUTING RULES:
- Use V_PERIODIC_DATA_INTERVAL2 ONLY for raw, instantaneous telemetry values:
  * weld_cur, weld_volt, weld_gas, motor_cur, motor_volt, rpm, weight, thickness, business_date, shift_name, machine_name, machine_type, job_name
- Use V_MACHINE_DERIVED ONLY for summarized, aggregated efficiency, or calculated operational metrics:
  * active, idle, inrepair, breakdown, avg_weld_cur, avg_weld_volt, avg_gas_consumption, avg_motor_cur, avg_motor_volt, target_arc_time_actual, period_start, period_end, machine_name, machine_type, shift_name
  * NOTE: TARGET_ARC_TIME_ACTUAL represents the actual accumulated welding arc time calculated by the system. Use this column whenever the user asks for target arc time, actual arc time, welding arc time, or arc utilization.
- Use V_DEVIATION ONLY for deviation, fault, error, or anomaly related queries:
  * start_tm, end_tm, span, type, parameter, hardware_id, oid, shid
- Only use columns that actually exist in the schema mappings defined below.

2. SYNTAX CRITICAL RULES:
- NEVER use the 'AS' keyword when creating table or view aliases. (e.g., 'FROM table_name t1', NOT 'FROM table_name AS t1').
- Standard column names are case-insensitive, but do not append fake aliases like 'T1.MID' if they do not exist.

View Registries, Precise Snowflake Types, and Columns:

1. V_MACHINE_TYPE
   - CREATED_AT (TIMESTAMP_NTZ(9))
   - MTID (NUMBER(38,0), Primary Key)
   - TYPE (VARCHAR(16777216))
   - UPDATED_AT (TIMESTAMP_NTZ(9))

2. V_MACHINES
   - MID (NUMBER(38,0), Primary Key)
   - NAME (VARCHAR(16777216))
   - HARDWARE_ID (VARCHAR(16777216))
   - DES, MSID, HID, ORGID, MCSID, MCID (VARCHAR(16777216))
   - MTID (NUMBER(38,0))
   - RPM_MULTIPLICATION_FACTOR (NUMBER(38,0))
   - NOTIFY, DELETED (BOOLEAN)
   - CREATED_AT, UPDATED_AT (TIMESTAMP_NTZ(9))

3. V_DEVIATION
   - END_TM (TIMESTAMP_NTZ(9))
   - HARDWARE_ID, OID, PARAMETER, SHID, TYPE (VARCHAR(16777216))
   - SPAN (NUMBER(38,0))
   - START_TM (TIMESTAMP_NTZ(9))

4. V_MACHINE_DERIVED
   - ACTIVE (NUMBER(38,0))
   - IDLE (NUMBER(38,0))
   - INREPAIR (NUMBER(38,0))
   - BREAKDOWN (NUMBER(38,0))
   - AVG_WELD_CUR (NUMBER(38,0))
   - AVG_WELD_VOLT (NUMBER(38,0))
   - AVG_GAS_CONSUMPTION (NUMBER(38,0))
   - AVG_MOTOR_CUR (NUMBER(38,0))
   - AVG_MOTOR_VOLT (NUMBER(38,0))
   - TARGET_ARC_TIME_ACTUAL (NUMBER(38,0))
   - BUSINESS_DATEKEY (TIMESTAMP_NTZ(9))
   - PERIOD_START (VARCHAR(16777216))
   - PERIOD_END (VARCHAR(16777216))
   - MACHINE_NAME (VARCHAR(16777216))
   - MACHINE_TYPE (VARCHAR(16777216))
   - SHIFT_NAME (VARCHAR(16777216))
   - OID (NUMBER(38,0))

5. V_PERIODIC_DATA_INTERVAL2
   - BUSINESS_DATE (DATE)
   - CUT_MM_MTR, MOTOR_CUR, MOTOR_VOLT, RPM, THICKNESS, WEIGHT, WELD_CUR, WELD_GAS, WELD_VOLT (NUMBER(38,0))
   - JOB_NAME, MACHINE_NAME, MACHINE_TYPE, SHIFT_NAME (VARCHAR(16777216))

6. V_SUMMARIZE_GASCUTTING_MACHINE
   - BUSINESS_DATE (DATE)
   - MACHINE_NAME, MACHINE_TYPE, SHIFT_NAME, TIME_SPAN, TIME_SPAN_MIN, TOTAL_O2 (VARCHAR(16777216))
   - MM_PER_MINUTE (NUMBER(38,15))
   - NET_LPG_CONSUMPTION, NET_O2_CONSUMPTION_METER1, NET_O2_CONSUMPTION_METER2, NET_TRAVEL_IN_MM (NUMBER(38,6))
   - OFF_TIME, ON_TIME (TIMESTAMP_NTZ(9))

7. V_SUMMARIZE_CLAD_DETAILS_INFO
   - AVG_WELD_CUR (NUMBER(38,15))
   - AVG_WELD_VOLT (NUMBER(38,17))
   - BUSINESS_DATE (DATE)
   - LOSS_WEIGHT (NUMBER(38,2))
   - MACHINE_NAME, MACHINE_TYPE, OFF_CUR, OFF_VOLT, OFF_WEIGHT, ON_CUR, ON_VOLT, ON_WEIGHT, SHIFT_NAME (VARCHAR(16777216))
   - OFFTIME, ONTIME (TIMESTAMP_NTZ(9))
   - OID (NUMBER(38,0))
   - TIME_SPAN (TIME(9))

8. V_SUMMARIZE_NONGASCUT_MACHINE
   - BUSINESS_DATE (DATE)
   - MACHINE_NAME, MACHINE_TYPE, SHIFT_NAME (VARCHAR(16777216))
   - MM_PER_MINUTE (NUMBER(38,20))
   - NET_TRAVEL_IN_MM (NUMBER(38,6))
   - OFF_TIME, ON_TIME (TIMESTAMP_NTZ(9))
   - TIME_SPAN (TIME(9))
   - TOTAL_HEATING_O2, TOTAL_LPG_CONS (NUMBER(38,0))

9. V_USER
   - ACTIVE_STATUS, DELETED (BOOLEAN)
   - CERTIFICATE_ID, CSRF_TOKEN, CURRENT_SESSION_TOKEN, IDENTIFICATION_NO, NAME, OPERATOR_RFID, OPID, PASSWORD, SESSION_EXPIRY, USERNAME (VARCHAR(16777216))
   - CREATED_AT, LAST_LOGIN, TOKEN_CREATED_AT, UPDATED_AT (TIMESTAMP_NTZ(9))
   - HID, ORGID, PHNO, ROLEID, UID (NUMBER(38,0), UID is Primary Key)

CRITICAL USER INTENT ROUTING & VOCABULARY RULES:
- Translate conversational terms to data constraints cleanly:
  1. 'Welding' / 'Welding Machine' -> matches string context value 'GMAW' or rows matching 'weld'.
  2. 'Cladding' / 'Clad Machine' -> matches string value 'CLAD'.
  3. 'Gas Cutting' / 'Gas Cutting Machine' -> matches string value 'GASCUTTING'.
  
- Casing Isolation: Always generate case-insensitive comparisons via LOWER() and LIKE (e.g., WHERE LOWER(machine_type) LIKE '%gmaw%').

SQL Generation Protocol:
- Return ONLY the clean, executable SQL syntax enclosed inside markdown formatting backticks (```sql ... ```). Do not append introductory greetings or descriptive summaries.
"""

# 3. Connection Routing Setup
def get_snowflake_connection():
    return snowflake.connector.connect(
        user=st.secrets["SNOWFLAKE_USER"],
        password=st.secrets["SNOWFLAKE_PASSWORD"],
        account=st.secrets["SNOWFLAKE_ACCOUNT"],
        warehouse=st.secrets["SNOWFLAKE_WAREHOUSE"],
        database=st.secrets["SNOWFLAKE_DATABASE"],
        schema=st.secrets["SNOWFLAKE_SCHEMA"]
    )

# Configure Gemini Context
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 4. User Interaction Interface Widget
user_prompt = st.text_input("Enter factory question or operational analytics prompt:", placeholder="e.g., What is average current usage of Welding Machine?")

if user_prompt:
    target_sql = None
    prompt_clean = user_prompt.lower().strip()
    
    # 5. Manifest Static Pass Caching Check (Improved Substring Matching)
    if os.path.exists("manifest.json"):
        with open("manifest.json", "r") as f:
            try:
                manifest = json.load(f)
                for q in manifest.get("saved_questions", []):
                    if q["prompt_pattern"].lower() in prompt_clean:
                        target_sql = q["cached_sql"]
                        st.success("🎯 Direct configuration cache hit! Query pulled immediately.")
                        break
            except Exception:
                pass

    # 6. Dynamic Generative Translation Path
    if not target_sql:
        try:
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=DATABASE_SCHEMA_CATALOG
            )
            response = model.generate_content(user_prompt)
            raw_response = response.text.strip()
            
            # Robust Parsing and Block Sanitation Extraction Engine
            if "```sql" in raw_response:
                target_sql = raw_response.split("```sql")[1].split("```")[0].strip()
            elif "```" in raw_response:
                target_sql = raw_response.split("```")[1].split("```")[0].strip()
            else:
                target_sql = raw_response.strip()
                    
            # Complete Text Sanitization & Whitespace Cleanup Loop
            target_sql = (
                target_sql
                .replace('"', "")
                .replace("`", "")
                .strip()
                .rstrip(";")
            )
            
            # Safeguard Guardrail: Block non-SQL conversational explanations
            if not target_sql.lower().startswith(("select", "with")):
                st.error("Gemini did not return valid SQL text context.")
                st.stop()
            
        except Exception as e:
            st.error(f"GenAI Translation Engine Error: {e}")

    # 7. Database Fetching and Rendering Workspace
    if target_sql:
        st.markdown("#### 🛠️ Generated Target Query")
        st.code(target_sql, language="sql")
        
        try:
            # Query runs dynamically directly against your live Snowflake instance
            conn = get_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute(target_sql)
            
            columns = [col[0] for col in cursor.description]
            data_results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            if data_results:
                df_display = pd.DataFrame(data_results, columns=columns)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("#### 📊 Real-time Log Stream")
                    st.dataframe(df_display, use_container_width=True)
                
                with col2:
                    st.markdown("#### ℹ️ Metrics Analytics Summary")
                    st.metric(label="Total Data Rows Fetched", value=len(df_display))
                    
                    if len(columns) >= 2 and len(df_display) > 1:
                        numeric_col = next((c for c in columns if df_display[c].dtype in ['float64', 'int64']), None)
                        text_col = next((c for c in columns if df_display[c].dtype == 'object'), columns[0])
                        
                        if numeric_col:
                            st.markdown(f"**Visual Distribution Matrix ({numeric_col}):**")
                            st.bar_chart(data=df_display, x=text_col, y=numeric_col)
            else:
                st.info("Query compiled cleanly, but Snowflake returned an empty dataset structure.")
                
        except Exception as err:
            st.error("❌ Database Query Execution Failure")
            st.code(str(err))
