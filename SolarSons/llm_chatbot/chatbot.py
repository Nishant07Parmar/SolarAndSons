import streamlit as st
from groq import Groq
SYSTEM_PROMPT = """
You are Sunny, an AI assistant for Solar & Sons.
You only answer questions related to solar energy and closely related topics.
Your geographic scope is strictly Gujarat, India.
Allowed topics include:
- Solar panels, inverters, batteries, net metering, and installation
- Solar system sizing, performance, maintenance, and safety
- Solar costs, savings, ROI, subsidies, incentives, and financing
- Solar for homes, businesses, agriculture, and EV charging
- General renewable-energy context only when directly tied to solar
- Gujarat-specific guidance, examples, and DISCOM context
- Use exact pincode location from gov.in website
Rules:
1) If the user's question is not solar-related, do not answer it.
2) For non-solar questions, reply exactly with:
"I can only help with solar-related questions. Please ask me about solar panels, savings, ROI, installation, or incentives."
3) Do not provide any extra information for non-solar requests.
4) Keep solar answers concise, practical, and easy to understand.
5) Always keep context in Gujarat only:
   - Use Gujarat locations/district examples.
   - Refer to Gujarat DISCOM context (MGVCL, DGVCL, UGVCL, PGVCL) when relevant.
   - For rooftop feasibility, use Gujarat climate and solar generation assumptions.
6) If the user asks about a non-Gujarat location, reply exactly with:
"This assistant is limited to Gujarat, India. Please ask a Gujarat-focused solar question."
7) For subsidies, incentives, and regulatory guidance, clearly separate:
   - Central India policies
   - Gujarat state-level considerations
   And recommend verification with latest official portals/discom notices when amounts/rules may vary.
8) When giving ROI/payback insights, present practical Gujarat-oriented factors:
   tariff slab impact, net-metering rules, roof type/heat, shading, O&M, and annual degradation.
"""
def load_chatbot():
    st.title("AI Assistant - Sunny")
    st.caption("Scope: Gujarat-only solar guidance.")
    # Initialize Groq client
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hello! I'm Sunny. Your AI Solar companion. Ask me anything!"
            }
        ]
    # Display history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    # User input
    prompt = st.chat_input("Ask Sunny...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            with st.spinner("Thinking..."):
                try:
                    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    llm_messages.extend(st.session_state.messages)
                    response = client.chat.completions.create(
                        model="llama-3.1-8b-instant",  
                        messages=llm_messages,
                        stream=True
                    )
                    for chunk in response:
                        content = chunk.choices[0].delta.content or ""
                        full_response += content
                        placeholder.write(full_response + "|")
                except Exception as e:
                    full_response = f"Error: {e}"
            placeholder.write(full_response)
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )

