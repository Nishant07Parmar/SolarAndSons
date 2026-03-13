import streamlit as st
from PIL import Image
import base64
from pathlib import Path
from HomePage import homepage
from ROICalc import roi_calc
from PowerBIDashboard import dashboard
from llm_chatbot import chatbot
from streamlit_float import float_init, float_css_helper
import streamlit.components.v1 as components

def _image_data_uri(image_path):
    try:
        img_bytes = Path(image_path).read_bytes()
        encoded = base64.b64encode(img_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return None

sunny_button_image = _image_data_uri(Path(__file__).resolve().parent / "assets" / "sunny_image.png")
if float_init:
    try:
        float_init()
    except Exception:
        pass

logo_path = Path(__file__).parent / "assets" / "logo.jpeg"
st.set_page_config(
    page_title="Solar & Sons",
    page_icon="assets/logo.jpeg",
    layout="wide"
)st.logo(str(logo_path), size="large")
st.title("Solar & Sons")

st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at 15% 35%,
            rgba(244, 230, 216, 0.6) 0%,
            rgba(244, 230, 216, 0.2) 20%,
            rgba(244, 230, 216, 0) 40%
        ),
        linear-gradient(180deg, #E9EEF5 0%, #DDE5F1 50%, #D4DCEF 100%);
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <style>
    .stApp .block-container,
    [data-testid="stMainBlockContainer"] {
        max-width: 100% !important;
        width: 100% !important;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(236, 242, 250, 0.9) !important;
        border: 1px solid #c6d3e5 !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06) !important;
    }
    .top-hero-banner {
        background-color: rgba(236, 242, 250, 0.9);
        border: 1px solid #c6d3e5;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
        border-radius: 12px;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin-bottom: 0.6rem;
        padding: 1.2rem;
    }
    .top-hero-title {
        margin: 0;
        color: #0f172a;
        text-align: center;
        font-size: 2.2rem;
    }
    .top-hero-subtitle {
        margin: 0.35rem 0 0 0;
        color: #1f2937;
        text-align: center;
        font-size: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown("""<div class="top-hero-banner">
            <h1 class="top-hero-title">Solar & Sons</h1>
            <p class="top-hero-subtitle">Gujarat Solar Radiation Analysis & Budget Forecast</p>
            </div>""",unsafe_allow_html=True)

open_button_bg_rule = (
    f"background-image: url('{sunny_button_image}') !important;"
    if sunny_button_image
    else "background: linear-gradient(135deg, #f59e0b, #f97316) !important;"
)
st.markdown(
    """
    <style>
    .st-key-chat_toggle_button button {
        width: 56px !important;
        height: 56px !important;
        border-radius: 999px !important;
        border: none !important;
        background-color: #ffffff !important;
    """
    + open_button_bg_rule
    + """
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        color: transparent !important;
        font-size: 0 !important;
        box-shadow: 0 8px 20px rgba(249, 115, 22, 0.3) !important;
        transition: transform 0.18s ease, filter 0.18s ease !important;
    }
    .st-key-chat_toggle_button button:hover {
        transform: translateY(-2px) scale(1.02) !important;
        filter: brightness(1.05) !important;
    }
    .st-key-chat_toggle_button button:focus {
        box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.45), 0 8px 20px rgba(249, 115, 22, 0.3) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def chat_toggle_button():
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False
    btn_container = st.container()
    with btn_container:
        if st.button(
            " ",
            key="chat_toggle_button",
            use_container_width=False,
            help="Ask Sunny anything about solar energy!" if st.session_state.chat_open else "Ask Sunny anything about solar energy!",
        ):
            st.session_state.chat_open = not st.session_state.chat_open

    if float_css_helper:
        try:
            btn_container.float(
                css=float_css_helper(
                    bottom="1rem",
                    right="1rem",
                    width="72px",
                    z_index="999",
                    background="rgba(236, 242, 250, 0.95)",
                    border="1px solid #c6d3e5",
                    shadow=2,
                )
            )
        except Exception:
            pass
    return st.session_state.chat_open

def render_main_view():
    valid_tabs = ["Home", "ROI Calc", "Dashboard"]
    st.session_state.setdefault("active_main_tab", "Home")
    if "tab_initialized" not in st.session_state:
        # Always open Home on a fresh page load/session.
        st.session_state["tab_initialized"] = True
        st.session_state["active_main_tab"] = "Home"
        st.query_params.update({"tab": "Home"})
    else:
        qp_tab = st.query_params.get("tab")
        if isinstance(qp_tab, list):
            qp_tab = qp_tab[0] if qp_tab else None
        if qp_tab in valid_tabs:
            st.session_state["active_main_tab"] = qp_tab
        elif st.session_state["active_main_tab"] not in valid_tabs:
            st.session_state["active_main_tab"] = "Home"

    # Persist selected Streamlit tab in query params so reruns keep the same tab.
    components.html(
        """
        <script>
        (function () {
          const install = () => {
            const tabButtons = parent.document.querySelectorAll('button[data-baseweb="tab"]');
            tabButtons.forEach((btn) => {
              if (btn.dataset.tabBound === "1") return;
              btn.dataset.tabBound = "1";
              btn.addEventListener("click", () => {
                const label = (btn.innerText || "").trim();
                const url = new URL(parent.window.location.href);
                url.searchParams.set("tab", label);
                parent.window.history.replaceState({}, "", url.toString());
              });
            });
          };
          install();
          setTimeout(install, 300);
          setTimeout(install, 1000);
        })();
        </script>
        """,
        height=0,
        width=0,
    )

    st.markdown(
        """
        <style>
        .stTabs [data-baseweb="tab-list"] {
            justify-content: flex-end;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    home_tab, roi_tab, dashboard_tab = st.tabs(
        valid_tabs,
        width="stretch",
        default=st.session_state["active_main_tab"],
    )
    with home_tab:
        homepage.load_home()
    with roi_tab:
        roi_calc.load_roi()
    with dashboard_tab:
        dashboard.load_dashboard()

chat_open = chat_toggle_button()
render_main_view()
if chat_open:
    chat_window_container = st.container()
    with chat_window_container:
        chat_panel = st.container(height=620, border=True)
        with chat_panel:
            chatbot.load_chatbot()

    if float_css_helper:
        try:
            chat_window_container.float(
                css=float_css_helper(
                    bottom="1rem",
                    right="1rem",
                    width="min(420px, calc(100vw - 2rem))",
                    z_index="998",
                    background="rgba(236, 242, 250, 0.97)",
                    border="1px solid #c6d3e5",
                    shadow=3,
                )
            )
        except Exception:
            pass

