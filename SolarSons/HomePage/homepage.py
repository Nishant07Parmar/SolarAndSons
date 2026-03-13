import streamlit as st
import pandas as pd
import streamlit_antd_components as sac
from pathlib import Path

try:
    from streamlit_card import card
except ImportError:
    card = None

CARD_STYLES = {
    "card": {
        "width": "100%",
        "backgroundColor": "rgba(236, 242, 250, 0.9)",
        "border": "1px solid #c6d3e5",
        "boxShadow": "0 8px 20px rgba(15, 23, 42, 0.07)",
        "borderRadius": "12px",
        "margin": 12,
    },
    "filter": {
        "backgroundColor": "transparent",
    },
    "title": {
        "color": "#0f172a",
        "fontSize": "1.25rem",
    },
    "text": {
        "color": "#334155",
        "fontWeight": "500",
    },
    "div": {
        "padding": "14px",
    },
}

SUBSIDY_URLS = {
    "PM Surya Ghar": "https://pmsuryaghar.gov.in/",
    "Surya Gujarat (GEDA)": "https://suryagujarat.guvnl.in/",
    "PM KUSUM (B & C)": "https://pmkusum.mnre.gov.in/",
    "PM KUSUM (A)": "https://pmkusum.mnre.gov.in/",
    "Green Credit Programme": "https://www.moefcc-gcp.in/",
}

@st.cache_data(show_spinner=False)
def _load_active_subsidies():
    csv_path = Path(__file__).resolve().parents[1] / "ROICalc" / "subsidy_schemes.csv"
    df = pd.read_csv(csv_path)
    df["is_active"] = pd.to_numeric(df.get("is_active", 0), errors="coerce").fillna(0).astype(int)
    df = df[df["is_active"] == 1].copy()
    if "scheme_name" in df.columns:
        df["scheme_name"] = df["scheme_name"].astype(str).str.strip()
    return df


def _inject_home_styles():
    st.markdown(
        """
        <style>
            .hero-banner {
                background-image:
                    linear-gradient(rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0.5)),
                    url("/app/static/background_image.jpg"),
                    url("/static/background_image.jpg"),
                    url("static/background_image.jpg");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                border-radius: 12px;
                min-height: 340px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                padding: 2.5rem 1.5rem;
                margin-bottom: 0.5rem;
            }
            .hero-title {
                text-align: center;
                margin: 0;
                color: #0f172a;
            }
            .hero-subtitle {
                text-align: center;
                margin: 0.5rem 0 0 0;
                color: #334155;
                font-size: 0.95rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_subsidy_details_section():
    subsidies = _load_active_subsidies()

    def _matches_selected_category(usage_value, selected_category):
        usage_tokens = [u.strip() for u in str(usage_value).split("|") if u.strip()]
        category_aliases = {
            "Residential": {"Residential"},
            "Industrial": {"Commercial / Industrial", "Industrial"},
            "Commercial": {"Commercial / Industrial", "Commercial"},
            "Agriculture": {"Agriculture"},
            "Solar Farm": {"Solar Farm"},
        }
        allowed = category_aliases.get(selected_category, set())
        return any(token in allowed for token in usage_tokens)

    st.write("")
    with st.container(border=True):
        st.subheader("Government Subsidy Details")
        st.caption(
            "Basic overview for each active subsidy. Use the official portal buttons for latest rules, documents, and application workflow."
        )
        st.info(
            "Click any subsidy name below to view scheme details, eligibility, benefits, and application process on the official website."
        )
        selected_category = st.selectbox(
            "Select Subsidy Category",
            options=["Residential", "Industrial", "Commercial", "Agriculture", "Solar Farm"],
            key="home_subsidy_category_filter",
        )

        if subsidies.empty:
            st.info("No active subsidy records available right now.")
            return

        filtered_subsidies = subsidies[
            subsidies["usage_type"].apply(
                lambda usage: _matches_selected_category(usage, selected_category)
            )
        ]
        if filtered_subsidies.empty:
            st.info(f"No active subsidies mapped to {selected_category} category.")
            return

        subsidy_names = (
            filtered_subsidies["scheme_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .loc[lambda s: s != ""]
            .drop_duplicates()
            .tolist()
        )
        if not subsidy_names:
            st.info(f"No active subsidies mapped to {selected_category} category.")
            return

        button_items = [
            sac.ButtonsItem(
                label=name,
                href=SUBSIDY_URLS.get(name, "https://mnre.gov.in/en/"),
            )
            for name in subsidy_names
        ]
        button_key = (
            f"home_subsidy_name_buttons_{selected_category.lower().replace(' ', '_').replace('/', '_')}"
        )
        st.markdown("**Available Subsidies (Click a name to open official page)**")
        sac.buttons(
            items=button_items,
            index=None,
            size="md",
            radius="md",
            variant="link",
            color="blue",
            direction="vertical",
            use_container_width=True,
            key=button_key,
        )


def load_home():
    _inject_home_styles()
    st.markdown(
        """
        <div class="hero-banner">
            <h2 class="hero-title"><strong>PLAN YOUR SOLAR INVESTMENT</strong></h2>
            <p class="hero-subtitle">
                Analyze Solar Radiation, estimate ROI & Payback period, and explore pincode-to-district
                insights for Gujarat-powered by Government data and Solar&Sons
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    with st.container(border=True):
        st.subheader("What can you do here?")
        col1, col2, col3 = st.columns([1, 1, 1], gap="small")
        with col1:
            if card:
                card(
                    title="Solar Potential Analysis",
                    text=[
                        "- Location-based radiation estimation",
                        "- Roof & Usage aware sizing",
                    ],
                    key="home_card_solar_potential",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Solar Potential Analysis**")
        with col2:
            if card:
                card(
                    title="ROI & Payback Calculator",
                    text=[
                        "- Subsidy-adjusted cost",
                        "- Statistical chart representation",
                    ],
                    key="home_card_roi_payback",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**ROI & Payback Calculator**")
        with col3:
            if card:
                card(
                    title="Manufacturer comparison",
                    text=["- Cost vs efficiency", "- Warranty & Degradation"],
                    key="home_card_mfg_compare",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Manufacturer comparison**")

    st.write("")
    with st.container(border=True):
        st.subheader("Who is this platform for?")
        col1, col2, col3 = st.columns([1, 1, 1], gap="small")
        with col1:
            if card:
                card(
                    title="Residential",
                    text=["- Is solar worth it for my home?", "- How much can I save?"],
                    key="home_card_residential",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Residential**")
        with col2:
            if card:
                card(
                    title="Commercial/Industrial",
                    text=["- Load-based optimization", "- Cost forecasting"],
                    key="home_card_commercial_industrial",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Commercial/Industrial**")
        with col3:
            if card:
                card(
                    title="Civic&Government",
                    text=["- Ward-wise insights", "- Planning & adoption metrics"],
                    key="home_card_civic_government",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Civic&Government**")

    _render_subsidy_details_section()

    st.write("")
    with st.container(border=True):
        st.subheader("Talk to our Solar Experts")
        st.caption("Get implementation guidance, subsidy support, and system sizing recommendations.")

        col1, col2, col3 = st.columns([1, 1, 1], gap="small")
        with col1:
            if card:
                card(
                    title="Mobile no",
                    text="+91-XXXXXXXXXX",
                    key="home_card_contact_mobile",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Mobile no**")
                    st.write("+91-XXXXXXXXXX")
                    st.caption("Mon-Sat, 9 AM - 7 PM")
        with col2:
            if card:
                card(
                    title="Email",
                    text="support@solarsons.com\nResponse within 24 hours",
                    key="home_card_contact_email",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Email**")
                    st.write("support@solarsons.com")
                    st.caption("Response within 24 hours")
        with col3:
            if card:
                card(
                    title="Location",
                    text="Vadodara, Gujarat\nRemote + On-site assistance",
                    key="home_card_contact_location",
                    styles=CARD_STYLES,
                )
            else:
                with st.container(border=True):
                    st.markdown("**Location**")
                    st.write("Gujarat, India")
                    st.caption("Remote + On-site assistance")

    st.write("")
    st.markdown(
        "<p style='text-align: center; color: #dc2626; font-size: 0.9rem; margin-bottom: 0.25rem;'>"
        "Note: This platform is scoped to Gujarat only. Data and calculations are based on Government sources; authority rests with the Government of India and Gujarat DISCOM/state bodies."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #6b7280; font-size: 0.85rem;'>"
        "@2026 Solar & Sons. All rights reserved."
        "</p>",
        unsafe_allow_html=True,
    )
