import streamlit as st
import snowflake.connector
import pandas as pd
import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# 1. INITIALIZATION & SECURITY ENVIRONMENT
# ==========================================
# Always load variables out of the local .env file first
load_dotenv()

# Initialize the Gemini Enterprise Client
client = genai.Client()

# Set up clean browser tab metadata layout
st.set_page_config(
    page_title="TDA Configuration Chatbot",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# 2. CORE UTILITY FUNCTIONS
# ==========================================
def query_snowflake(sql_query):
    """Executes database lookups targeting your Snowflake warehouse instances securely."""
    try:
        conn = snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA")
        )
        
        # Read data directly into a clean Pandas DataFrame workspace
        df = pd.read_sql(sql_query, conn)
        conn.close()
        
        return {"success": True, "data": df}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def load_manifest():
    """Loads configuration metadata structures profile schemas cleanly."""
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to read manifest.json: {str(e)}")
        return None

# ==========================================
# 3. STREAMLIT FRONTEND DASHBOARD LAYOUT
# ==========================================
st.title("📦 TDA Configuration-Driven Chatbot Workspace")
st.markdown("Parsing live industrial database logs utilizing structural JSON manifest metadata profiles.")
st.markdown("---")

# Load manifest data structures for caching or engine context injection
manifest = load_manifest()

# Core User Text Interaction Box
user_prompt = st.text_input("Enter search prompt or dynamic question:", placeholder="e.g., Show total anomalies")

if user_prompt:
    target_sql = None
    is_cached = False
    
    # Check if the query is a pre-saved question inside the manifest cache layer
    if manifest and "saved_questions" in manifest:
        for q in manifest["saved_questions"]:
            if q["prompt_pattern"].lower() in user_prompt.lower():
                target_sql = q["cached_sql"]
                is_cached = True
                st.info("🎯 Manifest Match: Executing Pre-Saved Question Template")
                break
                
    # If it's a dynamic exploration request, leverage the Gemini Engine
    if not target_sql and manifest:
        st.markdown("🧠 *Parsing dynamic entry via Gemini Engine utilizing JSON definitions*")
        
        system_context = f"""
        You are an expert SQL generator for a Snowflake data warehouse platform.
        Your system schema is strictly governed by this structural JSON configuration profile catalog:
        {json.dumps(manifest.get('schema_definitions', {}))}
        
        Given the user's natural language request, generate a clean, accurate SQL query statement.
        Only output the raw SQL text code. Do not wrap it in markdown code blocks or backticks.
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_context,
                    temperature=0.0 # Force objective technical accuracy
                )
            )
            target_sql = response.text.strip()
        except Exception as e:
            st.error(f"GenAI Translation Engine Error: {str(e)}")

    # ==========================================
    # 4. EXECUTION & VISUAL PRESENTATION LAYER
    # ==========================================
    if target_sql:
        st.markdown("### 📋 Evaluated Code Statement")
        st.code(target_sql, language="sql")
        
        with st.spinner("Extracting logs directly from target data views..."):
            db_payload = query_snowflake(target_sql)
            
            if db_payload["success"]:
                df = db_payload["data"]
                st.success("Log records parsed successfully!")
                
                # Create a dynamic row layout for advanced dashboard insights
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("#### 🔍 Tabular Logs Workspace")
                    st.dataframe(df, use_container_width=True)
                    
                with col2:
                    st.markdown("#### 📊 Operations KPI Visual")
                    
                    # 1. Multi-row data logic (Charts)
                    if len(df) > 1 and len(df.columns) >= 2:
                        try:
                            chart_df = df.copy()
                            x_axis_col = chart_df.columns[0]
                            chart_df = chart_df.set_index(x_axis_col)
                            st.bar_chart(chart_df)
                        except Exception as chart_err:
                            st.caption("Numerical tracking trends are not applicable for this data structure.")
                    
                    # 2. Single value logic (KPI Cards)
                    # 2. Single value logic (KPI Cards)
                    elif len(df) == 1 and len(df.columns) == 1:
                        metric_val = df.iloc[0, 0]
                        metric_lbl = df.columns[0].replace("_", " ").title()
                        
                        # Fix: Only apply comma formatting if the value is an integer or float
                        if isinstance(metric_val, (int, float)):
                            formatted_val = f"{metric_val:,}"
                        else:
                            formatted_val = str(metric_val)
                            
                        st.metric(label=metric_lbl, value=formatted_val)
                    
                    # 3. Text/Empty Fallback logic
                    else:
                        st.info("Log index payload structure is best evaluated via tabular view layout.")
                
                # --- EXECUTIVE INTERPRETATION BANNER ---
                st.markdown("---")
                st.markdown("### 💡 Executive Log Interpretation")
                
                with st.spinner("Analyzing data payload context..."):
                    # Convert the current dataframe snapshot into a text format for the LLM
                    data_string = df.to_string(index=False)
                    
                    explanation_context = f"""
                    You are a Lead Operations Analyst at an industrial manufacturing plant.
                    Review the following dataset retrieved from the system logs regarding the user's query '{user_prompt}':
                    
                    {data_string}
                    
                    Write a concise 2-3 sentence executive breakdown summarizing this finding. 
                    Explain what this metric implies for factory health, wear-and-tear, or shift efficiency based on standard IoT parameters.
                    """
                    
                    try:
                        analysis_response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=explanation_context
                        )
                        # Display the explanation in a professional blockquote alert layer
                        st.info(analysis_response.text)
                    except Exception as explanation_err:
                        st.caption("Contextual log summary generation offline.")
            else:
                st.error(f"Execution Error Encountered: {db_payload['error']}")