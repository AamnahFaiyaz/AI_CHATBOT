import streamlit as st
import snowflake.connector
import google.generativeai as genai
import os
import json

# 1. Page Configuration & Title Styling
st.set_page_config(page_title="Industrial Data Workspace", layout="wide", page_icon="🏭")
st.title("🏭 Multi-Table Enterprise Chatbot Workspace")
st.markdown("### Querying live factory assets, machine states, telemetry streams, and operational metrics across all 9 tables.")
st.markdown("---")

# 2. Verified Complete Database Schema Catalog (Passed directly to Gemini System Prompt)
DATABASE_SCHEMA_CATALOG = """
You are a master Text-to-SQL translator for an enterprise manufacturing database.
You must generate highly accurate, executable Snowflake SQL statements based strictly on the following 9 verified tables/views.

CRITICAL NAMING NOTE: Depending on database configuration, tables/views in Snowflake may be capitalized and prefixed with 'V_' (e.g., V_DEVIATION, V_SUMMARIZE_GASCUTTING_MACHINE, V_MACHINES, V_USER, V_PERIODIC_DATA_INTERVAL2, V_MACHINE_DERIVED, V_MACHINE_TYPE, V_SUMMARIZE_CLAD_DETAILS_INFO, V_SUMMARIZE_NONGASCUT_MACHINE). Generate SQL using the correct names requested by context.

Table Registries and Columns:

1. machine_type (or V_MACHINE_TYPE)
   - mtid (Numeric, Primary Key) -> Look up for machine categories
   - type (Text) -> Descriptive classification name of the machine type (e.g., GMAW, CLAD, GASCUTTING)
   - created_at, updated_at (Timestamp)

2. machines (or V_MACHINES)
   - mid (Numeric, Primary Key) -> Unique machine asset identifier
   - name (Text) -> Physical name assigned to the industrial machine asset (e.g., Rectifier1, GasCutting1)
   - hardware_id (Text) -> Unique hexadecimal mac/hardware address linking tracking units
   - des, msid, mtid, hid, orgid, mcsid, mcid (Relational link identifiers)
   - rpm_multiplication_factor (Numeric)
   - notify, deleted (Boolean flags)
   - created_at, updated_at (Timestamp)

3. deviation (or V_DEVIATION)
   - hardware_id, oid, shid (Identifiers)
   - start_tm, end_tm (Timestamp tracking window boundaries)
   - span (Numeric value highlighting scale or magnitude of calibration variance)
   - type, parameter (Text tracking monitored environmental parameter classifications like current, voltage, pressure)

4. machine_derived (or V_MACHINE_DERIVED)
   - mdid, mid, shift_id, oid, datekey, timekey, orgid (Relational keys)
   - target_arc_time, active, idle, inrepair, breakdown (Numeric state runtimes in minutes)
   - target_deposit, deposit, actualcost (Production and cost metrics)
   - partsneedcheckup (Maintenance indicators)
   - ts, period_start, period_end, business_date (Temporal logging fields)
   - hour_of_shift, shift_name (Roster contexts)
   - Operational parameters: avg_weld_volt, avg_weld_cur, avg_gas_consumption, avg_motor_volt, avg_motor_cur
   - System thresholds: temp_hs_threshold, temp_amb_threshold, high_weld_volt_threshold, low_weld_volt_threshold, high_weld_cur_threshold, low_weld_cur_threshold, etc.
   - Sensor summaries: hs_temp_count, amb_temp_count, all_temp_count, target_arc_time_actual

5. periodic_data_interval2 (or V_PERIODIC_DATA_INTERVAL2)
   - pdid, hardware_id, oid (Primary keys and logging trackers)
   - business_date (Date), tm (Timestamp element tracking streaming data)
   - shift_name, machine_type, machine_name, job_name, mstatus, dis, position (Text dimensions)
   - network (Numeric connection parameter)
   - Live streaming metrics: weld_cur, weld_volt, weld_gas, motor_cur, motor_volt, hs_temp, amb_temp, rpm
   - Metric flows: travel_in_mm, lpg_flow, o2_flow_meter1, o2_flow_meter2, thickness, cut_mm_mtr, weight
   - Accumulated volumes: total_lpg_consumption, total_o2_consumption_meter1, total_o2_consumption_meter2
   - Device Diagnostics: health_status_lpg_flow_meter, health_status_o2_flow_meter1, health_status_o2_flow_meter2
   - created_at (Timestamp)

6. summarize_gascutting_machine (or V_SUMMARIZE_GASCUTTING_MACHINE)
   - business_date (Date tracking production execution)
   - shift_name (Roster label tracker)
   - machine_type, machine_name (Descriptive tags)
   - on_time, off_time (Timestamp intervals tracking asset operations)
   - time_span, mm_per_min, thickness, cut_mm_mtr (Dimensions and speed calculations)
   - net_travel_in_mm (Total linear movement track accumulated by cutting torch)
   - net_lpg_consumption, net_o2_consumption_meter1, net_o2_consumption_meter2 (Utility gas meter volumes)

7. summarize_clad_details_info (or V_SUMMARIZE_CLAD_DETAILS_INFO)
   - business_date (Date mapping production cycle)
   - shift_name, oid, machine_type, machine_name (Relational tags)
   - ontime, offtime (Timestamps representing process runs)
   - time_span (Interval string logging active duration)
   - Electrical variables: on_cur, off_cur, avg_weld_cur, on_volt, off_volt, avg_weld_volt
   - Mass measurement variables: on_weight, off_weight, loss_weight

8. summarize_nongascut_machine (or V_SUMMARIZE_NONGASCUT_MACHINE)
   - business_date, shift_name, machine_type, machine_name (Process contexts)
   - on_time, off_time (Operation interval boundaries)
   - time_span, mm_per_min (Runtimes and feed speed parameters)
   - total_lpg_cons, total_heating_o2, net_travel_in_mm (Aggregated utility metrics)

9. user (or V_USER)
   - uid (Numeric operational employee roster reference key)
   - name, email, phno, username, password (Identity profile attributes)
   - roleid, hid, orgid, opid, operator_rfid, certificate_id, identification_no (Authorization variables)
   - active_status, deleted (System activity boolean flags)
   - current_session_token, csrf_token, token_created_at, created_at, updated_at (Session temporal metrics)

SQL Generation Protocol:
- Return ONLY the clean, executable SQL syntax enclosed inside markdown formatting backticks (```sql ... ```). Do not append introductory greetings or text postscript descriptions.
- Check user input attributes to cross-reference the correct target views precisely.
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
user_prompt = st.text_input("Enter factory question or operational analytics prompt:", placeholder="e.g., Show average hs_temp from periodic logs or list all user names")

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
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=DATABASE_SCHEMA_CATALOG
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
