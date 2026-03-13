import streamlit as st
import streamlit.components.v1 as components
def load_dashboard():
    st.title("Dashboard")
    powerbi_embed_url = "https://app.powerbi.com/reportEmbed?reportId=YOUR_REPORT_ID&autoAuth=true&ctid=YOUR_TENANT_ID"
    components.iframe(
        powerbi_embed_url,
        height=720,
        scrolling=True
    )

