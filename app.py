import streamlit as st
import snowflake.connector
import google.generativeai as genai
import os
import json
import pandas as pd
import re

# 1. Page Configuration & Title Styling
st.set_page_config(page_title="Tata SNTI AI Chatbot", layout="wide", page_icon="🤖")
st.title("🤖 Tata SNTI AI Chatbot")
st.markdown("### Natural Language Interface for IoT Manufacturing Analytics")
st.markdown("---")

# 2. Comprehensive Database Schema Catalog (The absolute system context map for Gemini)
DATABASE_SCHEMA_CATALOG = """
You are a master Text-to-SQL translator for an enterprise manufacturing database.
You must generate highly accurate, executable Snowflake SQL statements based strictly on these 9 views.

CRITICAL CASING RULES:
1. Every view name MUST be uppercase and begin with the 'V_' prefix (e.g., FROM V_PERIODIC_DATA_INTERVAL2).
2. All column names inside the SELECT, WHERE, and GROUP BY clauses MUST be written in the exact lowercase/uppercase formatting specified below. Snowflake is case-sensitive for these specific column identifiers.

Table Registries and Columns:

1. V_MACHINE_TYPE
   - mtid (Numeric, Primary Key)
   - type (Text)
   - created_at, updated_at (Timestamp)

2. V_MACHINES
   - mid (Numeric, Primary Key)
   - name (Text)
   - hardware_id (Text)
   - des, msid, mtid, hid, orgid, mcsid, mcid (Identifiers)
   - rpm_multiplication_factor (Numeric)
   - notify, deleted (Boolean)
   - created_at, updated_at (Timestamp)

3. V_DEVIATION
   - hardware_id, oid, shid (Identifiers)
   - start_tm, end_tm (Timestamp)
   - span (Numeric)
   - type, parameter (Text)

4. V_MACHINE_DERIVED
   - mdid, mid, shift_id, oid, datekey, timekey, orgid (Identifiers)
   - target_arc_time, active, idle, inrepair, breakdown (Numeric)
   - target_deposit, deposit, actualcost, partsneedcheckup (Metrics)
   - ts, period_start, period_end, business_date (Temporal)
   - hour_of_shift, shift_name (Text)
   - Operational parameters: avg_weld_volt, avg_weld_cur, avg_gas_consumption, avg_motor_volt, avg_motor_cur
   - System thresholds: temp_hs_threshold, temp_amb_threshold, high_weld_volt_threshold, low_weld_volt_threshold, high_weld_cur_threshold, low_weld_cur_threshold, etc.
   - Sensor summaries: hs_temp_count, amb_temp_count, all_temp_count, target_arc_time_actual

5. V_PERIODIC_DATA_INTERVAL2
   - pdid, hardware_id, oid (Identifiers)
   - business_date (Date), tm (Timestamp)
   - shift_name, machine_type, machine_name, job_name, mstatus, dis, position (Text)
   - network (Numeric)
   - Live metrics: weld_cur, weld_volt, weld_gas, motor_cur, motor_volt, hs_temp, amb_temp, rpm
   - Metric flows: travel_in_mm, lpg_flow, o2_flow_meter1, o2_flow_meter2, thickness, cut_mm_mtr, weight
   - Accumulated volumes: total_lpg_consumption, total_o2_consumption_meter1, total_o2_consumption_meter2
   - Device Diagnostics: health_status_lpg_flow_meter, health_status_o2_flow_meter1, health_status_o2_flow_meter2
   - created_at (Timestamp)

6. V_SUMMARIZE_GASCUTTING_MACHINE
   - business_date (Date)
   - shift_name (Text)
   - machine_type, machine_name (Text)
   - on_time, off_time (Timestamp)
   - time_span, mm_per_min, thickness, cut_mm_mtr (Metrics)
   - net_travel_in_mm (Numeric)
   - net_lpg_consumption, net_o2_consumption_meter1, net_o2_consumption_meter2 (Metrics)

7. V_SUMMARIZE_CLAD_DETAILS_INFO
   - business_date (Date)
   - shift_name, oid, machine_type, machine_name (Text)
   - ontime, offtime (Timestamp)
   - time_span (Text)
   - Electrical variables: on_cur, off_cur, avg_weld_cur, on_volt, off_volt, avg_weld_volt
   - Material mass tracking parameters: on_weight, off_weight, loss_weight

8. V_SUMMARIZE_NONGASCUT_MACHINE
   - business_date, shift_name, machine_type, machine_name (Text)
   - on_time, off_time (Timestamp)
   - time_span, mm_per_min (Metrics)
   - total_lpg_cons, total_heating_o2, net_travel_in_mm (Metrics)

9. V_USER
   - uid (Numeric)
   - name, email, phno, username, password (Text)
   - roleid, hid, orgid, opid, operator_rfid, certificate_id, identification_no (Identifiers)
   - active_status, deleted (Boolean)
   - current_session_token, csrf_token, token_created_at, created_at, updated_at (Temporal)

SQL Generation Protocol:
- Return ONLY the clean, executable SQL syntax enclosed inside markdown formatting backticks (```sql ... ```). Do not append introductory greetings or text postscript descriptions.
- Keep table columns in their exact lowercase state as written above, but keep view names uppercase with the V_ prefix.
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
            
            # SAFE FORCE FIX 1: Only add 'V_' if the view name is preceded by FROM, JOIN, or whitespace boundary
            raw_views = [
                "SUMMARIZE_GASCUTTING_MACHINE", "DEVIATION", "MACHINE_DERIVED", 
                "MACHINE_TYPE", "MACHINES", "PERIODIC_DATA_INTERVAL2", 
                "SUMMARIZE_CLAD_DETAILS_INFO", "SUMMARIZE_NONGASCUT_MACHINE", "USER"
            ]
            
            for view_base in raw_views:
                # Use regex boundaries to match the table target without matching column substrings
                pattern = rf"\b(?<!V_){view_base}\b"
                target_sql = re.sub(pattern, f"V_{view_base}", target_sql, flags=re.IGNORECASE)
                    
            # FORCE FIX 2: Strip out accidental double quotes that lock case matches incorrectly
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
                df_display = pd.DataFrame(data_results, columns=columns)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("#### 📊 Real-time Log Stream")
                    st.dataframe(df_display, use_container_width=True)
                
                with col2:
                    st.markdown("#### ℹ️ Metrics Analytics Summary")
                    st.metric(label="Total Data Rows Fetched", value=len(df_display))
                    
                    # Automated Chart Evaluation Rendering Engine
                    if len(columns) >= 2 and len(df_display) > 1:
                        numeric_col = next((c for c in columns if df_display[c].dtype in ['float64', 'int64']), None)
                        text_col = next((c for c in columns if df_display[c].dtype == 'object'), columns[0])
                        
                        if numeric_col:
                            st.markdown(f"**Visual Distribution Matrix ({numeric_col}):**")
                            st.bar_chart(data=df_display, x=text_col, y=numeric_col)
            else:
                st.info("Query compiled and delivered successfully, but Snowflake returned an empty dataset state.")
                
        except Exception as err:
            st.error(f"Database Query Execution Failure: {err}")
