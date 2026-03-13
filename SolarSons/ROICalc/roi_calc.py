import streamlit as st
import pandas as pd
import streamlit_antd_components as sac
import plotly.graph_objects as go
from pathlib import Path
from streamlit_float import float_init, float_css_helper

TARGET_STATE = "GUJARAT"
VALID_PROVIDERS = {"MGVCL", "DGVCL", "UGVCL", "PGVCL"}
GOVT_REFERENCE_AREA_PER_KW_M2 = 12.0
SUBSIDY_RULES_FILE = "subsidy_schemes.csv"
DISTRICT_PROVIDER_FALLBACK = {
    "AHMADABAD": "UGVCL",
}

@st.cache_data(show_spinner=False)
def load_pincode_data():
    csv_path = Path(__file__).resolve().parents[1] / "pincode_dataset.csv"
    df = pd.read_csv(csv_path, usecols=["pincode", "district", "statename", "provider"])
    df["pincode"] = df["pincode"].astype(str).str.strip()
    df["district"] = df["district"].astype(str).str.strip()
    df["statename"] = df["statename"].astype(str).str.strip()
    df["provider"] = df["provider"].astype(str).str.strip()
    df = df[df["statename"].str.upper() == TARGET_STATE].copy()
    return df.drop_duplicates(subset=["pincode"], keep="first")

@st.cache_data(show_spinner=False)
def load_subsidy_rules():
    csv_path = Path(__file__).resolve().parent / SUBSIDY_RULES_FILE
    df = pd.read_csv(csv_path)
    required_cols = [
        "scheme_name",
        "usage_type",
        "state_scope",
        "is_active",
        "subsidy_model",
        "eligible_kw_cap",
        "subsidy_percent",
        "slab1_upto_kw",
        "slab1_rate_general",
        "slab1_rate_special",
        "slab2_upto_kw",
        "slab2_rate_general",
        "slab2_rate_special",
        "max_subsidy_amount",
        "note",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing subsidy rule columns: {', '.join(missing)}")
    df["scheme_name"] = df["scheme_name"].astype(str).str.strip()
    df["usage_type"] = df["usage_type"].astype(str).str.strip()
    df["state_scope"] = df["state_scope"].astype(str).str.strip().str.upper()
    df["subsidy_model"] = df["subsidy_model"].astype(str).str.strip().str.lower()
    df["is_active"] = df["is_active"].fillna(0).astype(int)
    numeric_cols = [
        "eligible_kw_cap",
        "subsidy_percent",
        "slab1_upto_kw",
        "slab1_rate_general",
        "slab1_rate_special",
        "slab2_upto_kw",
        "slab2_rate_general",
        "slab2_rate_special",
        "max_subsidy_amount",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df[df["is_active"] == 1].copy()

def _to_kw(system_size_label):
    if isinstance(system_size_label, (int, float)):
        return max(0.0, float(system_size_label))
    size_map = {"1 kW": 1.0, "2 kW": 2.0, "3 kW": 3.0, "3kW+": 5.0}
    return size_map.get(system_size_label, 0.0)

def _currency(value):
    return f"INR {value:,.0f}"

def _normalize_provider(provider, district):
    provider_value = (provider or "").strip().upper()
    if provider_value in VALID_PROVIDERS:
        return provider_value
    district_value = (district or "").strip().upper()
    if district_value in DISTRICT_PROVIDER_FALLBACK:
        return DISTRICT_PROVIDER_FALLBACK[district_value]
    return "Unknown"

SPECIAL_CATEGORY_STATES = {
    "ARUNACHAL PRADESH",
    "ASSAM",
    "MANIPUR",
    "MEGHALAYA",
    "MIZORAM",
    "NAGALAND", 
    "SIKKIM",
    "TRIPURA",
    "JAMMU AND KASHMIR",
    "LADAKH",
    "HIMACHAL PRADESH",
    "UTTARAKHAND",
    "LAKSHADWEEP",
    "ANDAMAN AND NICOBAR ISLANDS",
}


def _usage_matches(rule_usage, usage_type):
    allowed = [u.strip() for u in str(rule_usage).split("|") if u.strip()]
    return usage_type in allowed


def _state_matches(rule_state_scope, state):
    scope = (rule_state_scope or "").strip().upper()
    if scope in {"", "ALL"}:
        return True
    return scope == (state or "").strip().upper()


def _subsidy_options_for_usage(usage_type, state, subsidy_rules):
    if not usage_type:
        return ["No Subsidy"]
    matched = subsidy_rules[
        subsidy_rules.apply(
            lambda r: _usage_matches(r["usage_type"], usage_type) and _state_matches(r["state_scope"], state),
            axis=1,
        )
    ]
    options = matched["scheme_name"].dropna().astype(str).str.strip().unique().tolist()
    return ["No Subsidy"] + sorted(options)


def _resolve_subsidy_rule(subsidy, usage_type, state, subsidy_rules):
    if subsidy == "No Subsidy" or not subsidy:
        return None
    matched = subsidy_rules[
        subsidy_rules.apply(
            lambda r: (r["scheme_name"] == subsidy)
            and _usage_matches(r["usage_type"], usage_type)
            and _state_matches(r["state_scope"], state),
            axis=1,
        )
    ]
    if matched.empty:
        return None
    return matched.iloc[0].to_dict()


def _calculate_subsidy_amount(*, subsidy, usage_type, state, effective_kw, gross_cost, subsidy_rules):
    if subsidy == "No Subsidy":
        return 0.0, "No subsidy applied."

    rule = _resolve_subsidy_rule(subsidy, usage_type, state, subsidy_rules)
    if not rule:
        return 0.0, f"Selected subsidy is not applicable for {usage_type} category."

    eligible_kw_cap = float(rule.get("eligible_kw_cap", 0.0) or 0.0)
    eligible_kw = min(effective_kw, eligible_kw_cap) if eligible_kw_cap > 0 else effective_kw
    if eligible_kw <= 0 or gross_cost <= 0:
        return 0.0, f"{subsidy} selected, but no eligible project capacity/cost available."

    eligible_cost = gross_cost * (eligible_kw / effective_kw) if effective_kw > 0 else 0.0
    subsidy_model = str(rule.get("subsidy_model", "")).strip().lower()
    is_special_state = (state or "").strip().upper() in SPECIAL_CATEGORY_STATES
    amount = 0.0

    if subsidy_model == "slab_per_kw":
        slab1_upto = max(0.0, float(rule.get("slab1_upto_kw", 0.0) or 0.0))
        slab2_upto = max(slab1_upto, float(rule.get("slab2_upto_kw", 0.0) or 0.0))
        slab1_rate = float(
            rule.get("slab1_rate_special" if is_special_state else "slab1_rate_general", 0.0) or 0.0
        )
        slab2_rate = float(
            rule.get("slab2_rate_special" if is_special_state else "slab2_rate_general", 0.0) or 0.0
        )
        first_kw = min(eligible_kw, slab1_upto)
        next_kw = max(0.0, min(eligible_kw, slab2_upto) - slab1_upto)
        amount = (first_kw * slab1_rate) + (next_kw * slab2_rate)
    elif subsidy_model == "percent_of_gross":
        pct = max(0.0, float(rule.get("subsidy_percent", 0.0) or 0.0))
        amount = eligible_cost * (pct / 100.0)

    max_subsidy = max(0.0, float(rule.get("max_subsidy_amount", 0.0) or 0.0))
    if max_subsidy > 0:
        amount = min(amount, max_subsidy)

    amount = max(0.0, amount)
    note = str(rule.get("note", "")).strip()
    if note:
        note = (
            f"{note} Estimated subsidy considered: {_currency(amount)} "
            f"(eligible capacity: {eligible_kw:.2f} kW)."
        )
    else:
        note = f"{subsidy} applied. Estimated subsidy considered: {_currency(amount)}."
    return amount, note


def _slabbed_cost(kw, slabs):
    remaining = max(0.0, kw)
    total = 0.0
    for slab_kw, rate in slabs:
        if remaining <= 0:
            break
        take = min(remaining, slab_kw)
        total += take * rate
        remaining -= take
    if remaining > 0 and slabs:
        total += remaining * slabs[-1][1]
    return total


def _mnre_benchmark_cost(kw, state):
    is_special = (state or "").strip().upper() in SPECIAL_CATEGORY_STATES
    if is_special:
        # MNRE PM Surya Ghar benchmark style: special category states/UTs.
        slabs = [(2.0, 55000.0), (1.0, 49500.0), (7.0, 47300.0)]
    else:
        # MNRE PM Surya Ghar benchmark style: general category states.
        slabs = [(2.0, 50000.0), (1.0, 45000.0), (7.0, 43000.0)]
    return _slabbed_cost(kw, slabs)


def _estimate_metrics(
    *,
    customer_category,
    usage_type,
    system_size,
    roof_length,
    roof_breadth,
    provider,
    subsidy,
    manufacturer,
    state,
    electricity_bill,
    subsidy_rules,
):
    area_per_kw = GOVT_REFERENCE_AREA_PER_KW_M2
    usable_roof_ratio = 0.75
    performance_ratio = 0.78
    state_irradiance = {TARGET_STATE: 5.7}
    tariff_by_provider = {
        "MGVCL": 7.0,
        "DGVCL": 6.8,
        "UGVCL": 6.7,
        "PGVCL": 6.9,
        "Unknown": 6.5,
    }
    manufacturer_profiles = {
        "Adani Solar": {
            "cost_multiplier": 1.03,
            "generation_multiplier": 1.00,
            "om_multiplier": 1.00,
            "facilities": "Standard O&M support and standard product warranty package.",
        },
        "Tata Power Solar": {
            "cost_multiplier": 1.06,
            "generation_multiplier": 1.015,
            "om_multiplier": 0.98,
            "facilities": "Enhanced service network with comparatively lower O&M intensity.",
        },
    }
    manufacturer_profile = manufacturer_profiles.get(manufacturer, manufacturer_profiles["Adani Solar"])

    roof_area = max(0.0, roof_length) * max(0.0, roof_breadth)
    usable_roof_area = roof_area * usable_roof_ratio
    selected_kw = _to_kw(system_size)
    if customer_category == "Civic & Government":
        selected_kw = max(selected_kw, 25.0)

    roof_limited_kw = usable_roof_area / area_per_kw if usable_roof_area > 0 else selected_kw
    effective_kw = max(0.0, min(selected_kw, roof_limited_kw) if roof_area > 0 else selected_kw)
    panel_area = effective_kw * area_per_kw
    inverter_area = max(1.0, effective_kw * 0.12) if effective_kw > 0 else 0.0
    electrical_area = max(0.6, effective_kw * 0.05) if effective_kw > 0 else 0.0
    ancillary_area = inverter_area + electrical_area
    occupied_area = panel_area + ancillary_area
    free_space = max(0.0, roof_area - occupied_area)

    irradiance = state_irradiance.get((state or "").upper(), 5.3)
    daily_generation = effective_kw * irradiance * performance_ratio * manufacturer_profile["generation_multiplier"]
    monthly_generation = daily_generation * 30
    annual_generation = daily_generation * 365

    tariff = tariff_by_provider.get(provider, 6.5)
    if usage_type == "Commercial / Industrial":
        tariff = max(tariff, 8.2)
    if customer_category == "Civic & Government":
        tariff = max(tariff, 7.5)

    annual_savings = annual_generation * tariff
    bill_based_annual = (electricity_bill or 0) * 12
    if bill_based_annual > 0:
        annual_savings = min(annual_savings, bill_based_annual * 1.05)

    benchmark_cost = _mnre_benchmark_cost(effective_kw, state)
    gross_cost = benchmark_cost * manufacturer_profile["cost_multiplier"]

    subsidy_amount, subsidy_note = _calculate_subsidy_amount(
        subsidy=subsidy,
        usage_type=usage_type,
        state=state,
        effective_kw=effective_kw,
        gross_cost=gross_cost,
        subsidy_rules=subsidy_rules,
    )

    final_cost = max(0.0, gross_cost - subsidy_amount)
    payback_years = (final_cost / annual_savings) if annual_savings > 0 else 0.0

    om_year1 = gross_cost * 0.01 * manufacturer_profile["om_multiplier"]
    degradation = 0.006
    tariff_escalation = 0.03
    om_escalation = 0.05
    cashflows = [-final_cost]
    cumulative = [-final_cost]
    for year in range(1, 26):
        energy_factor = (1 - degradation) ** (year - 1)
        tariff_factor = (1 + tariff_escalation) ** (year - 1)
        om_cost = om_year1 * ((1 + om_escalation) ** (year - 1))
        year_saving = (annual_generation * energy_factor * tariff * tariff_factor) - om_cost
        cashflows.append(year_saving)
        cumulative.append(cumulative[-1] + year_saving)

    total_25y_savings = cumulative[-1]

    return {
        "selected_kw": selected_kw,
        "effective_kw": effective_kw,
        "roof_area": roof_area,
        "panel_area": panel_area,
        "inverter_area": inverter_area,
        "electrical_area": electrical_area,
        "ancillary_area": ancillary_area,
        "occupied_area": occupied_area,
        "free_space": free_space,
        "daily_generation": daily_generation,
        "monthly_generation": monthly_generation,
        "annual_generation": annual_generation,
        "annual_savings": annual_savings,
        "payback_years": payback_years,
        "total_25y_savings": total_25y_savings,
        "gross_cost": gross_cost,
        "benchmark_cost": benchmark_cost,
        "subsidy_amount": subsidy_amount,
        "final_cost": final_cost,
        "tariff": tariff,
        "cashflows": cashflows,
        "cumulative": cumulative,
        "subsidy_note": subsidy_note,
        "manufacturer_facilities": manufacturer_profile["facilities"],
    }


def _build_final_verdict(*, metrics, district, state, provider, usage_type, customer_category, electricity_bill):
    payback = metrics.get("payback_years", 0.0) or 0.0
    annual_savings = metrics.get("annual_savings", 0.0) or 0.0
    selected_kw = metrics.get("selected_kw", 0.0) or 0.0
    effective_kw = metrics.get("effective_kw", 0.0) or 0.0
    gross_cost = metrics.get("gross_cost", 0.0) or 0.0
    final_cost = metrics.get("final_cost", 0.0) or 0.0

    if payback > 0 and payback <= 5:
        viability_tone = "highly favorable"
    elif payback <= 7:
        viability_tone = "strong and financially attractive"
    elif payback <= 10:
        viability_tone = "viable with a moderate payback horizon"
    else:
        viability_tone = "technically feasible but financially slower to recover"

    if provider == "Unknown":
        location_note = (
            f"Location insight for {district}, {state} is indicative because DISCOM/provider could not be mapped."
        )
    else:
        location_note = (
            f"Location insight for {district}, {state} under {provider} shows stable rooftop-solar suitability."
        )

    bill_coverage_note = ""
    yearly_bill = (electricity_bill or 0) * 12
    if yearly_bill > 0:
        coverage_pct = min(105.0, (annual_savings / yearly_bill) * 100.0) if yearly_bill else 0.0
        bill_coverage_note = (
            f" Estimated annual savings can offset about {coverage_pct:.0f}% of your present yearly electricity spend."
        )

    roof_note = ""
    if selected_kw > 0 and effective_kw + 1e-6 < selected_kw:
        roof_note = (
            f" Current roof constraints reduce usable system size from {selected_kw:.1f} kW to {effective_kw:.1f} kW, "
            "so redesign or additional usable area can improve returns."
        )

    recommendation = (
        "Recommended to proceed with installation."
        if payback <= 8 and annual_savings > 0
        else "Proceed only after revisiting system sizing and commercial terms."
    )

    return (
        f"{location_note} Based on your selected {customer_category.lower()} usage ({usage_type}), "
        f"this project appears {viability_tone}. Expected payback is about {payback:.1f} years, "
        f"with gross investment around {_currency(gross_cost)} and post-subsidy investment around {_currency(final_cost)}."
        f"{bill_coverage_note} {roof_note} {recommendation}"
    ).strip()


def load_roi():
    if float_init:
        try:
            float_init()
        except Exception:
            pass

    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            .st-key-roi_steps_tracker .ant-steps {
                display: flex !important;
                flex-wrap: nowrap !important;
                overflow-x: auto !important;
                overflow-y: hidden !important;
                -webkit-overflow-scrolling: touch;
                padding-bottom: 0.15rem;
            }
            .st-key-roi_steps_tracker .ant-steps-item {
                flex: 0 0 auto !important;
                min-width: 96px !important;
            }
            .st-key-roi_steps_tracker .ant-steps-item-description {
                display: none !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    tracker_placeholder = st.empty()
    st.title("ROI Calculation")
    st.caption("Location-based calculation")
    pincode_df = load_pincode_data()
    subsidy_rules = load_subsidy_rules()
    st.session_state.setdefault("roi_show_results", False)
    st.session_state.setdefault("roi_calc_completed", False)
    st.session_state.setdefault("roi_steps_index", 0)

    with st.container(border=True):
        st.subheader("Location Details")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            pincode = st.text_input(
                "Pincode",
                max_chars=6,
                placeholder="Enter 6-digit pincode",
                key="roi_pincode",
            )

        pincode_value = (pincode or "").strip()
        if pincode_value and not pincode_value.isdigit():
            st.error("Pincode must contain numbers only.")
            pincode_value = ""

        district_default = ""
        state_default = TARGET_STATE
        provider_default = "Unknown"
        st.session_state.setdefault("roi_last_lookup_pincode", "")
        st.session_state.setdefault("roi_lookup_district", "")
        st.session_state.setdefault("roi_lookup_state", TARGET_STATE)
        st.session_state.setdefault("roi_lookup_provider", "Unknown")
        st.session_state.setdefault("roi_lookup_not_found", False)
        if pincode_value != st.session_state["roi_last_lookup_pincode"]:
            st.session_state["roi_last_lookup_pincode"] = pincode_value
            st.session_state["roi_lookup_not_found"] = False
            if len(pincode_value) == 6 and pincode_value.isdigit():
                match = pincode_df.loc[pincode_df["pincode"] == pincode_value]
                if not match.empty:
                    resolved_district = str(match.iloc[0]["district"])
                    st.session_state["roi_lookup_state"] = str(match.iloc[0]["statename"])
                    st.session_state["roi_lookup_district"] = resolved_district
                    st.session_state["roi_lookup_provider"] = _normalize_provider(
                        str(match.iloc[0]["provider"]),
                        resolved_district,
                    )
                else:
                    st.session_state["roi_lookup_district"] = ""
                    st.session_state["roi_lookup_state"] = TARGET_STATE
                    st.session_state["roi_lookup_provider"] = "Unknown"
                    st.session_state["roi_lookup_not_found"] = True
            else:
                st.session_state["roi_lookup_district"] = ""
                st.session_state["roi_lookup_state"] = TARGET_STATE
                st.session_state["roi_lookup_provider"] = "Unknown"
        district_default = st.session_state["roi_lookup_district"]
        state_default = st.session_state["roi_lookup_state"]
        provider_default = st.session_state["roi_lookup_provider"]
        if st.session_state["roi_lookup_not_found"]:
            st.warning("Only Gujarat pincodes are supported in this application.")

        st.session_state["roi_district_text"] = district_default
        st.session_state["roi_state_text"] = state_default
        st.session_state["roi_provider"] = provider_default

        with col2:
            district = st.text_input(
                "District",
                disabled=True,
                key="roi_district_text",
            )
        with col3:
            state = st.text_input(
                "State",
                disabled=True,
                key="roi_state_text",
            )
        with col4:
            provider = st.selectbox(
                "Provider",
                ["Unknown", "MGVCL", "DGVCL", "UGVCL", "PGVCL"],
                key="roi_provider",
                disabled=True,
            )

    st.write("")
    with st.container(border=True):
        st.subheader("Customer Type")
        col1, _ = st.columns(2)
        with col1:
            customer_category = st.pills(
                "Customer Category",
                options=["Personal", "Civic & Government"],
                selection_mode="single",
                key="roi_customer_category",
            )

        usage_type = None
        if customer_category == "Personal":
            usage_type = st.pills(
                "",
                options=["Residential", "Commercial / Industrial", "Agriculture"],
                selection_mode="single",
                key="roi_usage_personal",
            )
        elif customer_category == "Civic & Government":
            usage_type = st.pills(
                "",
                options=["Solar Farm"],
                selection_mode="single",
                key="roi_usage_government",
            )

    st.write("")
    system_size = None
    electricity_bill = None
    with st.container(border=True):
        st.subheader("System Configuration")
        if customer_category == "Personal":
            with st.container(border=True):
                st.markdown("**System Size**")
                system_size = st.number_input(
                    "System Size (kW)",
                    min_value=0.0,
                    step=0.1,
                    key="roi_system_size_kw",
                )
                st.caption(
                    "Govt reference (MNRE National Portal Rooftop Calculator): Approx. 12 m2 rooftop area per 1 kW."
                )

            if usage_type != "Agriculture":
                with st.container(border=True):
                    st.markdown("**Roof Size**")
                    roof_col1, roof_col2 = st.columns(2)
                    with roof_col1:
                        length = st.number_input("Roof Length (m)", key="roi_roof_length")
                    with roof_col2:
                        breadth = st.number_input("Roof Width (m)", key="roi_roof_breadth")
            electricity_bill = st.number_input("Electricity Bill (INR)", key="roi_electricity_bill")
        elif customer_category == "Civic & Government":
            st.info("Contact us for custom system configuration.")

    st.write("")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Subsidy")
                subsidy_options = _subsidy_options_for_usage(usage_type, state_default, subsidy_rules)
                if st.session_state.get("roi_subsidy") not in subsidy_options:
                    st.session_state["roi_subsidy"] = subsidy_options[0]
                subsidy = st.selectbox(
                    "Subsidy",
                    subsidy_options,
                    key="roi_subsidy",
                )
        with col2:
            with st.container(border=True):
                st.subheader("Manufacturer")
                manufacturer_options = ["Adani Solar", "Tata Power Solar"]
                if st.session_state.get("roi_manufacturer") not in manufacturer_options:
                    st.session_state["roi_manufacturer"] = manufacturer_options[0]
                manufacturer = st.selectbox(
                    "Manufacturer",
                    manufacturer_options,
                    key="roi_manufacturer",
                )

    validation_errors = []
    if not (len(pincode_value) == 6 and pincode_value.isdigit()):
        validation_errors.append("Enter a valid 6-digit numeric pincode.")
    elif not district_default or not state_default:
        validation_errors.append("Use a Gujarat pincode available in the dataset.")
    elif (state_default or "").upper() != TARGET_STATE:
        validation_errors.append("This calculator is limited to Gujarat state only.")

    if not customer_category:
        validation_errors.append("Select a customer type.")

    if customer_category == "Personal":
        if system_size is None or system_size <= 0:
            validation_errors.append("Enter system size greater than 0 kW.")
        if electricity_bill is None or electricity_bill <= 0:
            validation_errors.append("Enter electricity bill greater than 0.")

    has_valid_location = (
        len(pincode_value) == 6
        and pincode_value.isdigit()
        and bool(district_default)
        and bool(state_default)
        and (state_default or "").upper() == TARGET_STATE
    )
    has_customer_details = bool(customer_category)
    has_system_config = customer_category == "Civic & Government" or (
        customer_category == "Personal" and system_size is not None and system_size > 0 and electricity_bill is not None and electricity_bill > 0
    )
    is_ready_to_calculate = not validation_errors

    if validation_errors:
        st.session_state["roi_calc_completed"] = False
        st.warning("Complete required fields before calculating ROI:")
        for err in validation_errors:
            st.write(f"- {err}")

    calculate_clicked = st.button(
        "Calculate ROI",
        help="Calculate your location based insights!",
        type="primary",
        key="roi_calculate_button",
        disabled=bool(validation_errors),
    )
    if calculate_clicked:
        st.session_state["roi_show_results"] = True
        st.session_state["roi_calc_completed"] = False
        
    if st.session_state.get("roi_show_results"):
        st.write("")
        with st.container(border=True):
            roof_length = float(st.session_state.get("roi_roof_length", 0) or 0)
            roof_breadth = float(st.session_state.get("roi_roof_breadth", 0) or 0)
            metrics = _estimate_metrics(
                customer_category=customer_category,
                usage_type=usage_type,
                system_size=system_size,
                roof_length=roof_length,
                roof_breadth=roof_breadth,
                provider=provider,
                subsidy=subsidy,
                manufacturer=manufacturer,
                state=state,
                electricity_bill=electricity_bill,
                subsidy_rules=subsidy_rules,
            )
            st.session_state["roi_calc_completed"] = True

            if usage_type != "Agriculture":
                st.subheader("Roof Analysis (Metrics)")
                roof_table = pd.DataFrame(
                    [
                        ["Roof Area", f"{metrics['roof_area']:.2f} m2"],
                        ["Solar Panel Area", f"{metrics['panel_area']:.2f} m2"],
                        ["Inverter + Electrical Area", f"{metrics['ancillary_area']:.2f} m2"],
                        ["Total Occupied Area", f"{metrics['occupied_area']:.2f} m2"],
                        ["Free Space", f"{metrics['free_space']:.2f} m2"],
                    ],
                    columns=["Metric", "Value"],
                )
                st.table(roof_table)
                if metrics["effective_kw"] < metrics["selected_kw"]:
                    st.warning(
                        f"Roof-constrained sizing detected. Selected: {metrics['selected_kw']:.1f} kW, "
                        f"feasible on roof: {metrics['effective_kw']:.1f} kW."
                    )

                st.subheader("Roof Outlook")
                outlook_col, note_col = st.columns([2.2, 1], gap="medium")
                with outlook_col:
                    max_dim_px = 420
                    min_dim_px = 90
                    if roof_length > 0 and roof_breadth > 0:
                        if roof_length >= roof_breadth:
                            roof_box_width = max_dim_px
                            roof_box_height = max(min_dim_px, int(max_dim_px * (roof_breadth / roof_length)))
                        else:
                            roof_box_height = max_dim_px
                            roof_box_width = max(min_dim_px, int(max_dim_px * (roof_length / roof_breadth)))
                    else:
                        roof_box_width = max_dim_px
                        roof_box_height = 150
                    coverage_ratio = (metrics["panel_area"] / metrics["roof_area"]) if metrics["roof_area"] > 0 else 0.0
                    ancillary_ratio = (metrics["ancillary_area"] / metrics["roof_area"]) if metrics["roof_area"] > 0 else 0.0
                    coverage_ratio = max(0.0, min(1.0, coverage_ratio))
                    ancillary_ratio = max(0.0, min(1.0, ancillary_ratio))
                    solar_fill_height = int(roof_box_height * coverage_ratio)
                    if coverage_ratio > 0:
                        solar_fill_height = max(2, solar_fill_height)
                    solar_fill_label = f"{coverage_ratio * 100:.1f}% roof used"
                    inverter_box_size = 54 if ancillary_ratio > 0 else 0
                    electrical_box_width = 58 if ancillary_ratio > 0 else 0

                    st.markdown(
                        f"""
                        <div style="position:relative; width:100%; min-height:280px; border:1px solid #94a3b8; border-radius:8px; background:#f8fafc; display:flex; align-items:center; justify-content:center; padding:10px;">
                            <div style="position:absolute; top:10px; left:12px; font-size:0.88rem; color:#475569;">
                                Roof area reference box ({roof_length:.2f}m x {roof_breadth:.2f}m)
                            </div>
                            <div style="width:{roof_box_width}px; height:{roof_box_height}px; border:2px solid #64748b; border-radius:6px; background:#e2e8f0; position:relative;">
                                <div style="position:absolute; left:0; bottom:0; width:100%; height:{solar_fill_height}px; background:rgba(14, 165, 233, 0.70); border-top:1px solid rgba(2, 132, 199, 0.95); border-radius:0 0 4px 4px;"></div>
                                <div style="position:absolute; right:6px; top:6px; width:{inverter_box_size}px; height:{inverter_box_size}px; background:rgba(245, 158, 11, 0.85); border:1px solid #b45309; border-radius:4px; display:flex; align-items:center; justify-content:center; font-size:0.65rem; color:#111827; text-align:center; line-height:1.1;">Inverter</div>
                                <div style="position:absolute; right:6px; top:{inverter_box_size + 14}px; width:{electrical_box_width}px; height:28px; background:rgba(16, 185, 129, 0.85); border:1px solid #047857; border-radius:4px; display:flex; align-items:center; justify-content:center; font-size:0.62rem; color:#111827; text-align:center; line-height:1.1;">ACDB/DCDB</div>
                                <div style="position:absolute; right:6px; bottom:6px; font-size:0.74rem; color:#0f172a; background:rgba(255,255,255,0.75); padding:2px 5px; border-radius:4px;">{solar_fill_label}</div>
                                <div style="position:absolute; top:-22px; left:50%; transform:translateX(-50%); font-size:0.8rem; color:#334155;">Length: {roof_length:.2f} m</div>
                                <div style="position:absolute; top:50%; right:-115px; transform:translateY(-50%); font-size:0.8rem; color:#334155;">Width: {roof_breadth:.2f} m</div>
                            </div>
                            <div style="position:absolute; bottom:10px; left:12px; font-size:0.85rem; color:#334155;">
                                Blue = solar panels ({metrics['panel_area']:.2f} m2), Amber/Green = inverter and electrical equipment ({metrics['ancillary_area']:.2f} m2)
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with note_col:
                    st.markdown(
                        f"""
                        <div style="border:1px solid #fca5a5; background:#fef2f2; border-radius:8px; padding:12px;">
                            <div style="font-weight:600; color:#991b1b; margin-bottom:8px;">Equipment Included in Roof Outlook</div>
                            <div style="font-size:0.9rem; color:#7f1d1d; line-height:1.5;">
                                <div>Solar Panels: {metrics['panel_area']:.2f} m2</div>
                                <div>Inverter Zone: {metrics['inverter_area']:.2f} m2</div>
                                <div>ACDB/DCDB + Electricals: {metrics['electrical_area']:.2f} m2</div>
                                <div style="margin-top:6px;">Layout is indicative; final placement can change after site engineering.</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.write("")
            st.subheader("Information Metrics")
            info_table = pd.DataFrame(
                [
                    ["Location", f"{district}, {state}"],
                    ["Solar Potential", f"{metrics['effective_kw']:.1f} kW system @ {metrics['tariff']:.2f} INR/kWh tariff"],
                    ["Daily Production", f"{metrics['daily_generation']:.1f} kWh/day"],
                    ["Monthly Production", f"{metrics['monthly_generation']:.1f} kWh/month"],
                    ["Annual Production", f"{metrics['annual_generation']:.1f} kWh/year"],
                ],
                columns=["Metric", "Value"],
            )
            st.table(info_table)

            st.write("")
            st.subheader("Additional Metrics")
            add_table = pd.DataFrame(
                [
                    ["Annual Savings", _currency(metrics["annual_savings"])],
                    ["Payback Period", f"{metrics['payback_years']:.1f} years"],
                    ["25-Year Net Savings", _currency(metrics["total_25y_savings"])],
                ],
                columns=["Metric", "Value"],
            )
            st.table(add_table)
            st.caption(subsidy)
            st.info(f"Manufacturer package ({manufacturer}): {metrics['manufacturer_facilities']}")

            st.subheader("Detailed Cost Breakdown")
            component_shares = [
                ("Solar Panels", 0.50),
                ("Inverter", 0.16),
                ("Mounting Structure", 0.11),
                ("Balance of System", 0.13),
                ("Installation & Labour", 0.10),
            ]
            cost_rows = []
            remaining_subsidy = metrics["subsidy_amount"]
            total_final = 0.0
            for component, share in component_shares:
                gross_component = metrics["gross_cost"] * share
                subsidy_component = min(remaining_subsidy, gross_component)
                final_component = gross_component - subsidy_component
                remaining_subsidy -= subsidy_component
                total_final += final_component
                cost_rows.append(
                    [
                        component,
                        _currency(gross_component),
                        _currency(subsidy_component),
                        _currency(final_component),
                    ]
                )
            cost_rows.append(
                [
                    "Total",
                    _currency(metrics["gross_cost"]),
                    _currency(metrics["subsidy_amount"]),
                    _currency(total_final),
                ]
            )
            cost_df = pd.DataFrame(
                cost_rows,
                columns=["Components", "Gross Cost", "Subsidy", "Final Cost"],
            )
            st.table(cost_df)

            st.subheader("Savings Analysis")
            left_chart_col, right_chart_col = st.columns(2, gap="medium")

            with left_chart_col:
                st.markdown("**Cumulative Savings**")
                years = list(range(0, 26))
                cumulative_fig = go.Figure()
                cumulative_fig.add_trace(
                    go.Scatter(
                        x=years,
                        y=metrics["cumulative"],
                        mode="lines",
                        line={"color": "#0ea5e9", "width": 3},
                        name="Net Cumulative (INR)",
                    )
                )
                cumulative_fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
                cumulative_fig.update_layout(
                    margin={"l": 10, "r": 10, "t": 20, "b": 10},
                    xaxis_title="Year",
                    yaxis_title="INR",
                    height=360,
                    showlegend=False,
                )
                st.plotly_chart(cumulative_fig, use_container_width=True)

            with right_chart_col:
                st.markdown("**Break-Even Point**")
                break_even_year = next((i for i, val in enumerate(metrics["cumulative"]) if val >= 0), None)
                break_even_label = f"Year {break_even_year}" if break_even_year is not None else "Beyond 25 Years"
                break_even_fig = go.Figure()
                break_even_fig.add_trace(
                    go.Bar(
                        x=["Investment", "Annual Savings"],
                        y=[metrics["final_cost"], metrics["annual_savings"]],
                        marker_color=["#f97316", "#16a34a"],
                    )
                )
                break_even_fig.update_layout(
                    margin={"l": 10, "r": 10, "t": 35, "b": 10},
                    yaxis_title="INR",
                    height=360,
                    showlegend=False,
                    annotations=[
                        {
                            "text": f"Break-even: {break_even_label}",
                            "xref": "paper",
                            "yref": "paper",
                            "x": 0.5,
                            "y": 1.12,
                            "showarrow": False,
                            "font": {"size": 13, "color": "#1f2937"},
                        }
                    ],
                )
                st.plotly_chart(break_even_fig, use_container_width=True)

            st.write("")
            st.subheader("Final Verdict")
            final_verdict = _build_final_verdict(
                metrics=metrics,
                district=district,
                state=state,
                provider=provider,
                usage_type=usage_type,
                customer_category=customer_category,
                electricity_bill=electricity_bill,
            )
            st.info(final_verdict)

    if st.session_state.get("roi_calc_completed"):
        current_step = 5
    elif is_ready_to_calculate:
        current_step = 4
    elif has_system_config:
        current_step = 3
    elif has_customer_details:
        current_step = 2
    elif has_valid_location:
        current_step = 1
    else:
        current_step = 0

    st.session_state["roi_steps_index"] = current_step
    with tracker_placeholder.container():
        tracker_container = st.container()
        with tracker_container:
            sac.steps(
                items=[
                    sac.StepsItem(title="Start", description="Enter location"),
                    sac.StepsItem(title="Location", description="Pincode verified"),
                    sac.StepsItem(title="Customer", description="Type selected"),
                    sac.StepsItem(title="Configuration", description="System details"),
                    sac.StepsItem(title="Ready", description="Validation complete"),
                    sac.StepsItem(title="Results", description="ROI generated"),
                ],
                index=st.session_state["roi_steps_index"],
                size="sm",
                direction="horizontal",
                kwargs={"responsive": False, "labelPlacement": "horizontal"},
                key="roi_steps_tracker",
            )
    if float_css_helper:
        try:
            tracker_container.float(
                css=float_css_helper(
                    top="5.75rem",
                    left="1rem",
                    right="1rem",
                    z_index="998",
                    background="rgba(255, 255, 255, 0.96)",
                    border="1px solid #e2e8f0",
                    radius="10px",
                    padding="0.45rem 0.7rem",
                    shadow=1,
                )
            )
            st.write("")
            st.write("")
            st.write("")
        except Exception:
            pass
