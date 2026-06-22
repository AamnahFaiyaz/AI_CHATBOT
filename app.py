import streamlit as st
import snowflake.connector
import google.generativeai as genai
import os
import json

# 1. Page Configuration & Title Styling
st.set_page_config(page_title="Industrial Data Workspace", layout="wide", page_icon="🏭")
st.title("🏭 Multi-Table Enterprise Chatbot Workspace")
st.markdown("### Querying live factory assets, machine states, telemetry streams, and operational metrics across all 9 database views.")
st.markdown("---")

# 2. Comprehensive Database Schema Catalog (The absolute system context map for Gemini)
DATABASE_SCHEMA_CATALOG = """
You are a master Text-to-SQL translator for an enterprise manufacturing database.
You must generate highly accurate, executable Snowflake SQL statements based strictly on these 9 UPPERCASE views. 
CRITICAL RULE: Every single view name MUST begin with the 'V_' prefix. Never omit the 'V_' prefix.

Table Registries and Columns:

1. V_MACHINE_TYPE
   - MTID (Numeric, Primary Key) -> Look up for machine categories
   - TYPE (Text) -> Descriptive classification name of the machine type (e.g., GMAW, CLAD, GASCUTTING)
   - CREATED_AT, UPDATED_AT (Timestamp)

2. V_MACHINES
   - MID (Numeric, Primary Key) -> Unique machine asset identifier
   - NAME (Text) -> Physical name assigned to the industrial machine asset (e.g., Rectifier1, GasCutting1)
   - HARDWARE_ID (Text) -> Unique hexadecimal mac/hardware address linking tracking units
   - DES, MSID, MTID, HID, ORGID, MCSID, MCID (Relational link identifiers)
   - RPM_MULTIPLICATION_FACTOR (Numeric)
   - NOTIFY, DELETED (Boolean flags)
   - CREATED_AT, UPDATED_AT (Timestamp)

3. V_DEVIATION
   - HARDWARE_ID, OID, SHID (Identifiers)
   - START_TM, END_TM (Timestamp tracking window boundaries)
   - SPAN (Numeric value highlighting scale or magnitude of calibration variance)
   - TYPE, PARAMETER (Text tracking monitored environmental parameter classifications like current, voltage, pressure)

4. V_MACHINE_DERIVED
   - MDID, MID, SHIFT_ID, OID, DATEKEY, TIMEKEY, ORGID (Relational keys)
   - TARGET_ARC_TIME, ACTIVE, IDLE, INREPAIR, BREAKDOWN (Numeric state runtimes in minutes)
   - TARGET_DEPOSIT, DEPOSIT, ACTUALCOST (Production and cost metrics)
   - PARTSNEEDCHECKUP (Maintenance indicators)
   - TS, PERIOD_START, PERIOD_END, BUSINESS_DATE (Temporal logging fields)
   - HOUR_OF_SHIFT, SHIFT_NAME (Roster contexts)
   - Operational parameters: AVG_WELD_VOL, AVG_WELD_CUR, AVG_GAS_CONSUMPTION, AVG_MOTOR_VOL, AVG_MOTOR_CUR
   - System thresholds: TEMP_HS_THRESHOLD, TEMP_AMB_THRESHOLD, HIGH_WELD_VOL_THRESHOLD, LOW_WELD_VOL_THRESHOLD, HIGH_WELD_CUR_THRESHOLD, LOW_WELD_CUR_THRESHOLD, etc.
   - Sensor summaries: HS_TEMP_COUNT, AMB_TEMP_COUNT, ALL_TEMP_COUNT, TARGET_ARC_TIME_ACTUAL

5. V_PERIODIC_DATA_INTERVAL2
   - PDID, HARDWARE_ID, OID (Primary keys and logging trackers)
   - BUSINESS_DATE (Date), TM (Timestamp element tracking streaming data)
   - SHIFT_NAME, MACHINE_TYPE, MACHINE_NAME, JOB_NAME, MSTATUS, DIS, POSITION (Text dimensions)
   - NETWORK (Numeric connection parameter)
   - Live streaming metrics: WELD_CUR, WELD_VOL, WELD_GAS, MOTOR_CUR, MOTOR_VOL, HS_TEMP, AMB_TEMP, RPM
   - Metric flows: TRAVEL_IN_MM, LPG_FLOW, O2_FLOW_METER1, O2_FLOW_METER2, THICKNESS, CUT_MM_MTR, WEIGHT
   - Accumulated volumes: TOTAL_LPG_CONSUMPTION, TOTAL_O2_CONSUMPTION_METER1, TOTAL_O2_CONSUMPTION_METER2
   - Device Diagnostics: HEALTH_STATUS_LPG_FLOW_METER, HEALTH_STATUS_O2_FLOW_METER1, HEALTH_STATUS_O2_FLOW_METER2
   - CREATED_AT (Timestamp)

6. V_SUMMARIZE_GASCUTTING_MACHINE
   - BUSINESS_DATE (Date tracking production execution)
   - SHIFT_NAME (Roster label tracker)
   - MACHINE_TYPE, MACHINE_NAME (Descriptive tags)
   - ON_TIME, OFF_TIME (Timestamp intervals tracking asset operations)
   - TIME_SPAN, MM_PER_MIN, THICKNESS, CUT_MM_MTR (Dimensions and speed calculations)
   - NET_TRAVEL_IN_MM (Total linear movement track accumulated by cutting torch)
   - NET_LPG_CONSUMPTION, NET_O2_CONSUMPTION_METER1, NET_O2_CONSUMPTION_METER2 (Utility gas meter volumes)

7. V_SUMMARIZE_CLAD_DETAILS_INFO
   - BUSINESS_DATE (Date mapping production cycle)
   - SHIFT_NAME, OID, MACHINE_TYPE, MACHINE_NAME (Relational strings)
   - ONTIME, OFFTIME (Timestamps representing process runs)
   - TIME_SPAN (Interval string logging active duration)
   - Electrical variables: ON_CUR, OFF_CUR, AVG_WELD_CUR, ON_VOL, OFF_VOL, AVG_WELD_VOL
   - Material mass tracking parameters: ON_WEIGHT, OFF_WEIGHT, LOSS_WEIGHT

8. V_SUMMARIZE_NONGASCUT_MACHINE
   - BUSINESS_DATE, SHIFT_NAME, MACHINE_TYPE, MACHINE_NAME (Process contexts)
   - ON_TIME, OFF_TIME (Operation interval boundaries)
   - TIME_SPAN, MM_PER_MIN (Runtimes and feed speed parameters)
   - TOTAL_LPG_CONS, TOTAL_HEATING_O2, NET_TRAVEL_IN_MM (Aggregated utility metrics)

9. V_USER
   - UID (Numeric operational employee roster reference key)
   - NAME, EMAIL, PHNO, USERNAME, PASSWORD (Identity profile attributes)
   - ROLEID, HID, ORGID, OPID, OPERATOR_RFID, CERTIFICATE_ID, IDENTIFICATION_NO (Authorization variables)
   - ACTIVE_STATUS, DELETED (System activity boolean flags)
   - CURRENT_SESSION_TOKEN, CSRF_TOKEN, TOKEN_CREATED_AT, CREATED_AT, UPDATED_AT (Session temporal metrics)

SQL Generation Protocol:
- Return ONLY the clean, executable SQL syntax enclosed inside markdown formatting backticks (```sql ... ```). Do not append introductory greetings or text postscript descriptions.
- All view names and column names must be written in strict UPPERCASE exactly as shown above.
- Every single view name in the FROM statement MUST have 'V_' explicitly attached to the front (e.g., SELECT * FROM V_SUMMARIZE_GASCUTTING_MACHINE).
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
user_prompt = st.text_input("Enter factory question or operational analytics prompt:", placeholder="e.g., Show all unique machine names")

if user_prompt:
    target_sql = None
    
    # 5. Manifest Static Pass Caching Check
    if os.path.exists("manifest.json"):
        with open("manifest.json", "r") as f:
            try:
                manifest = json.load(f)
                for q in manifest.get("saved_questions", []):
                    if user_prompt.strip().lower() == q["prompt_pattern"].lower():
                        target_sql = q["cached_sql"]
                        st.success("🎯 Direct configuration cache hit! Query pulled immediately.")
                        break
            except Exception:
                pass

    # 6. Dynamic Generative Translation Path
    if not target_sql:
        try:
            # Explicitly command uppercase view generation to the system context layer
            UPPERCASE_STRICT_PROMPT = DATABASE_SCHEMA_CATALOG + "\nCRITICAL: ALL view names must begin with 'V_' and all columns must be strict UPPERCASE. Example: SELECT DISTINCT MACHINE_NAME FROM V_SUMMARIZE_GASCUTTING_MACHINE"
            
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=UPPERCASE_STRICT_PROMPT
            )
            response = model.generate_content(user_prompt)
            raw_response = response.text.strip()
            
            # Formatting sanitation block extraction
            if "```sql" in raw_response:
                target_sql = raw_response.split("```sql")[1].split("```")[0].strip()
            elif "```" in raw_response:
                target_sql = raw_response.split("```")[1].split("```")[0].strip()
            else:
                target_sql = raw_response
                
            # FORCE FIX 1: Ensure uppercase structural integration
            target_sql = target_sql.upper()
            
            # FORCE FIX 2: Safeguard step to make sure 'V_' is never missed out
            raw_views = [
                "SUMMARIZE_GASCUTTING_MACHINE", "DEVIATION", "MACHINE_DERIVED", 
                "MACHINE_TYPE", "MACHINES", "PERIODIC_DATA_INTERVAL2", 
                "SUMMARIZE_CLAD_DETAILS_INFO", "SUMMARIZE_NONGASCUT_MACHINE", "USER"
            ]
            for view_base in raw_views:
                if view_base in target_sql and f"V_{view_base}" not in target_sql:
                    target_sql = target_sql.replace(view_base, f"V_{view_base}")
                    
            # FORCE FIX 3: Strip out double quotes that mess up Snowflake's compiler
            target_sql = target_sql.replace('"', '')
            
        except Exception as e:
            st.error(f"GenAI Translation Engine Error: {e}")

    # 7. Database Fetching and Rendering Workspace
    if target_sql:
        st.markdown("#### 🛠️ Generated Target Query")
        st.code(target_sql, language="sql")
        
        try:
            conn = get_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute(target_sql)
            
            columns = [col[0] for col in cursor.description]
            data_results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            if data_results:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("#### 📊 Real-time Log Stream")
                    st.dataframe(data_results, columns=columns, use_container_width=True)
                
                with col2:
                    st.markdown("#### ℹ️ Metrics Analytics Summary")
                    st.metric(label="Total Data Rows Fetched", value=len(data_results))
                    
                    # Automated Chart Evaluation Rendering Engine
                    if len(columns) >= 2 and len(data_results) > 1:
                        import pandas as pd
                        df = pd.DataFrame(data_results, columns=columns)
                        numeric_col = next((c for c in columns if df[c].dtype in ['float64', 'int64']), None)
                        text_col = next((c for c in columns if df[c].dtype == 'object'), columns[0])
                        
                        if numeric_col:
                            st.markdown(f"**Visual Distribution Matrix ({numeric_col}):**")
                            st.bar_chart(data=df, x=text_col, y=numeric_col)
            else:
                st.info("Query compiled and delivered successfully, but Snowflake returned an empty dataset state.")
                
        except Exception as err:
            st.error(f"Database Query Execution Failure: {err}")
