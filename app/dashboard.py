
import io
import json
import re

import pandas as pd
import requests
import streamlit as st


# ============================================================
# 1. CONFIGURATION
# ============================================================

API_BASE_URL = "http://127.0.0.1:8000"
COMPANIES_API_URL = f"{API_BASE_URL}/api/companies"

st.set_page_config(
    page_title="Bags & Luggage AI",
    page_icon="🎒",
    layout="wide",
)


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def get_company_name(company):
    """Return the company name using common field names."""

    return str(
        company.get("company_name")
        or company.get("name")
        or company.get("company")
        or company.get("domain")
        or "Unknown company"
    )



def get_score(company):
    """Get the numeric lead score from the company record."""

    for key in (
        "buying_intent_score",
        "score",
        "lead_score",
        "total_score",
        "final_score",
    ):
        value = company.get(key)

        try:
            if value is not None:
                return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            continue

    return 0




def get_score_band(company):
    """Read the existing score band or calculate it."""

    band = company.get("score_band")

    if band:
        return str(band).title()

    score = get_score(company)

    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"

    return "Low"



def get_value(company, *keys, default="Not available"):
    """Return the first non-empty field."""

    for key in keys:
        value = company.get(key)

        if value is not None and value != "":
            return value

    return default


def display_value(value):
    """Format nested data for Streamlit."""

    if value is None or value == "":
        return "Not available"

    if isinstance(value, (dict, list, tuple)):
        if not value:
            return "Not available"

        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    return str(value)


def as_list(value):
    """Convert a value into a list for consistent display."""

    if value is None or value == "":
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):
        return [value] if value.strip() else []

    if isinstance(value, dict):
        return [value]

    return [value]


def get_emails(company):
    """Extract public email fields."""

    value = get_value(
        company,
        "emails",
        "email_addresses",
        "email",
        default=[],
    )

    return as_list(value)


def get_phones(company):
    """Extract public phone fields."""

    value = get_value(
        company,
        "phone_numbers",
        "phones",
        "phone",
        "mobile_numbers",
        default=[],
    )

    return as_list(value)


def get_evidence(company):
    """Retrieve evidence records from common field names."""

    value = get_value(
        company,
        "evidence",
        "evidence_records",
        "supporting_evidence",
        default=[],
    )

    return as_list(value)


def get_source_urls(company):
    """Retrieve source URLs from a company record."""

    urls = []

    for key in ("source_urls", "sources", "source_pages"):
        value = company.get(key)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    url = (
                        item.get("url")
                        or item.get("source_url")
                        or item.get("page_url")
                    )
                    if url:
                        urls.append(str(url))

        elif isinstance(value, str):
            urls.append(value)

    # Include common website fields.
    for key in ("website", "domain", "source_url"):
        value = company.get(key)

        if isinstance(value, str) and value.strip():
            urls.append(value.strip())

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(urls))


def normalize_for_export(companies):
    """Convert nested values into CSV/Excel-friendly cells."""

    rows = []

    for company in companies:
        row = {}

        for key, value in company.items():
            if isinstance(value, (dict, list, tuple)):
                row[key] = json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                )
            else:
                row[key] = value

        rows.append(row)

    return pd.DataFrame(rows)


def build_evidence_dataframe(companies):
    """Create one export row per evidence item."""

    rows = []

    for company in companies:
        company_name = get_company_name(company)

        for item in get_evidence(company):
            if isinstance(item, dict):
                rows.append({
                    "company_name": company_name,
                    **item,
                })
            else:
                rows.append({
                    "company_name": company_name,
                    "evidence": str(item),
                })

    return pd.DataFrame(rows)


def get_score_reasons(company):
    """Read the score explanation from available fields."""

    reasons = get_value(
        company,
        "score_reasons",
        "scoring_reasons",
        "score_breakdown",
        "reasons",
        default=[],
    )

    if isinstance(reasons, dict):
        return [
            {"reason": key, "points": value}
            for key, value in reasons.items()
        ]

    return as_list(reasons)


def parse_reason(reason):
    """Convert different reason formats into a displayable format."""

    if isinstance(reason, dict):
        description = (
            reason.get("reason")
            or reason.get("description")
            or reason.get("rule")
            or reason.get("name")
            or "Scoring factor"
        )

        points = reason.get(
            "points",
            reason.get("score", reason.get("value")),
        )

        return str(description), points

    text = str(reason)

    # Supports explanations such as:
    # "Bag needs identified: +25 points"
    match = re.search(
        r":\s*([+-]?\d+(?:\.\d+)?)\s*points?\s*$",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        points = float(match.group(1))
        description = text[:match.start()].strip()
        return description, points

    return text, None


def format_points(points):
    """Format scoring points without unnecessary decimals."""

    if points is None:
        return ""

    try:
        number = float(points)

        if number.is_integer():
            number = int(number)

        return f"{number:+} points"
    except (TypeError, ValueError):
        return str(points)


# ============================================================
# 3. LOAD DATA THROUGH FASTAPI
# ============================================================

@st.cache_data(ttl=30)
def load_companies():
    """Fetch company records from the FastAPI backend."""

    response = requests.get(
        COMPANIES_API_URL,
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()

    if isinstance(payload, list):
        companies = payload
    elif isinstance(payload, dict):
        companies = payload.get("companies", [])
    else:
        companies = []

    if not isinstance(companies, list):
        raise ValueError(
            "FastAPI returned an unexpected company data format."
        )

    return [
        company
        for company in companies
        if isinstance(company, dict)
    ]


# ============================================================
# 4. PAGE HEADER
# ============================================================

st.title("🎒 Bags & Luggage AI")
st.caption(
    "Company discovery, buying-signal analysis, "
    "lead scoring and evidence review."
)

with st.sidebar:
    st.header("Backend status")
    st.write("FastAPI:", API_BASE_URL)

    if st.button("Refresh company data", use_container_width=True):
        load_companies.clear()
        st.session_state.pop("analyzed_company_name", None)
        st.rerun()


# ============================================================
# 5. HANDLE API CONNECTION
# ============================================================

try:
    companies = load_companies()

except requests.RequestException as exc:
    st.error("Cannot connect to the FastAPI backend.")
    st.markdown(
        "Make sure your API server is running in another terminal:"
    )

    st.code(
        "python -m uvicorn app.api:app --reload",
        language="cmd",
    )

    st.caption(f"Connection details: {exc}")
    st.stop()

except (ValueError, json.JSONDecodeError) as exc:
    st.error(f"Could not process the API response: {exc}")
    st.stop()


# ============================================================
# 6. SUMMARY METRICS
# ============================================================

total_companies = len(companies)

high_priority = sum(
    get_score_band(company).lower() == "high"
    for company in companies
)

medium_priority = sum(
    get_score_band(company).lower() == "medium"
    for company in companies
)

low_priority = sum(
    get_score_band(company).lower() == "low"
    for company in companies
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Companies", total_companies)
col2.metric("High Priority", high_priority)
col3.metric("Medium Priority", medium_priority)
col4.metric("Low Priority", low_priority)

st.divider()


# ============================================================
# 7. COMPANY SELECTION
# ============================================================

st.subheader("Analyze a Company")

if not companies:
    st.warning("No company records were returned by the API.")
    st.stop()

companies = sorted(
    companies,
    key=get_score,
    reverse=True,
)

# Display only company names in the dropdown.
company_options = [
    (get_company_name(company), index)
    for index, company in enumerate(companies)
]

# Handle duplicate company names safely.
labels = []
for name, index in company_options:
    label = name
    if label in labels:
        label = f"{name} ({index + 1})"
    labels.append(label)

selected_label = st.selectbox(
    "Select a company",
    options=labels,
    key="company_selector",
)

selected_index = labels.index(selected_label)

if st.button(
    "Analyze Selected Company",
    type="primary",
    use_container_width=True,
):
    st.session_state["analyzed_company_index"] = selected_index
    st.session_state["analyzed_company_name"] = get_company_name(
        companies[selected_index]
    )



# ============================================================
# 8. DISPLAY SELECTED COMPANY ANALYSIS
# ============================================================

analyzed_index = st.session_state.get("analyzed_company_index")

if analyzed_index is not None and 0 <= analyzed_index < len(companies):

    company = companies[analyzed_index]

    st.divider()
    st.header(get_company_name(company))

    score = get_score(company)
    band = get_score_band(company)

    # Main company metrics.
    metric1, metric2, metric3 = st.columns(3)

    metric1.metric("Lead Score", f"{score}/100")
    metric2.metric("Priority", band)

    role = get_value(
        company,
        "role",
        "company_role",
        "business_role",
    )

    metric3.metric("Company Role", display_value(role))

    # Score progress.
    st.write("**Score overview**")
    st.progress(score / 100)

    st.caption(
        "The score is a rule-based estimate, not a verified "
        "probability of purchasing."
    )

    # Company details.
    st.subheader("Company Details")

    website = get_value(
        company,
        "website",
        "domain",
        "url",
    )

    category = get_value(
        company,
        "category",
        "business_category",
        "industry",
    )

    qualification = get_value(
        company,
        "qualification_status",
        "status",
        "qualification",
    )

    data_quality = get_value(
        company,
        "data_quality",
        "extraction_status",
    )

    details1, details2 = st.columns(2)

    with details1:
        st.write("**Website**")
        website_text = display_value(website)
        if isinstance(website, str) and website.startswith(
            ("http://", "https://")
        ):
            st.markdown(f"[{website_text}]({website})")
        else:
            st.write(website_text)

        st.write("**Category / Industry**")
        st.write(display_value(category))

        st.write("**Qualification Status**")
        st.write(display_value(qualification))

    with details2:
        st.write("**Data Quality**")
        st.write(display_value(data_quality))

        st.write("**Company Role**")
        st.write(display_value(role))

    # Contact information.
    st.subheader("Public Contact Information")

    emails = get_emails(company)
    phones = get_phones(company)

    contact1, contact2 = st.columns(2)

    with contact1:
        st.write("**Email addresses**")

        if emails:
            for email in emails:
                st.write(f"- {display_value(email)}")
        else:
            st.write("No public email found in the extracted data.")

    with contact2:
        st.write("**Phone numbers**")

        if phones:
            for phone in phones:
                st.write(f"- {display_value(phone)}")
        else:
            st.write("No public phone found in the extracted data.")

    # Product and business needs.
    st.subheader("Business and Bag Needs")

    needs = get_value(
        company,
        "bag_needs",
        "identified_needs",
        "needs",
        "product_needs",
        default=[],
    )

    if needs == [] or needs is None:
        st.info("No specific bag needs recorded.")
    elif isinstance(needs, list):
        for need in needs:
            st.write(f"- {display_value(need)}")
    else:
        st.write(display_value(needs))

    buying_signals = get_value(
        company,
        "buying_signals",
        "buying_intent",
        "intent_signals",
        default=[],
    )

    st.subheader("Buying Signals")

    if buying_signals == [] or buying_signals is None:
        st.info("No buying signals recorded.")
    elif isinstance(buying_signals, list):
        for signal in buying_signals:
            st.write(f"- {display_value(signal)}")
    else:
        st.write(display_value(buying_signals))

    # Score explanation.
    st.divider()
    st.subheader("Why This Score Was Assigned")

    reasons = get_score_reasons(company)

    if reasons:
        st.caption(
            "Each item below explains a recorded scoring factor. "
            "Points are displayed when available in the data."
        )

        for reason in reasons:
            description, points = parse_reason(reason)

            if points is not None:
                try:
                    is_positive = float(points) >= 0
                except (TypeError, ValueError):
                    is_positive = True

                symbol = "🟢" if is_positive else "🔴"

                with st.container(border=True):
                    reason_col, points_col = st.columns([4, 1])

                    with reason_col:
                        st.write(f"{symbol} **{description}**")

                    with points_col:
                        st.markdown(
                            f"**{format_points(points)}**"
                        )
            else:
                with st.container(border=True):
                    st.write(f"• {description}")

    else:
        st.info(
            "No individual scoring reasons were found in this "
            "company record. Check the fields returned by the API."
        )

    # Intent groups.
    intent_groups = get_value(
        company,
        "matched_intent_groups",
        "intent_groups",
        "buying_intent_groups",
        default=[],
    )

    st.subheader("Matched Intent Groups")

    if intent_groups == [] or intent_groups is None:
        st.write("No matched intent groups recorded.")
    elif isinstance(intent_groups, list):
        st.write(", ".join(map(str, intent_groups)))
    else:
        st.write(display_value(intent_groups))

    # Evidence is hidden until expanded.
    st.divider()

    evidence = get_evidence(company)

    with st.expander("View Supporting Evidence", expanded=False):
        if evidence:
            for index, item in enumerate(evidence, start=1):
                st.markdown(f"**Evidence {index}**")

                if isinstance(item, dict):
                    for key, value in item.items():
                        st.write(f"**{key.replace('_', ' ').title()}:**")
                        st.write(display_value(value))
                else:
                    st.write(str(item))

                st.divider()
        else:
            st.info("No evidence records were found.")

    # Source links are hidden until expanded.
    source_urls = get_source_urls(company)

    with st.expander("View Source Websites", expanded=False):
        if source_urls:
            for url in source_urls:
                if url.startswith(("http://", "https://")):
                    st.markdown(f"- [{url}]({url})")
                else:
                    st.write(f"- {url}")
        else:
            st.info("No source URLs were recorded.")


# ============================================================
# 9. EXPORT ALL COMPANIES
# ============================================================

st.divider()
st.header("Export All Company Data")

st.write(
    "These downloads include all companies returned by FastAPI, "
    "not just the company selected above."
)

export_df = normalize_for_export(companies)

csv_data = export_df.to_csv(index=False).encode("utf-8-sig")

excel_buffer = io.BytesIO()

with pd.ExcelWriter(
    excel_buffer,
    engine="openpyxl",
) as writer:

    export_df.to_excel(
        writer,
        sheet_name="All Companies",
        index=False,
    )

    evidence_df = build_evidence_dataframe(companies)

    if evidence_df.empty:
        evidence_df = pd.DataFrame(
            columns=["company_name", "evidence"]
        )

    evidence_df.to_excel(
        writer,
        sheet_name="Evidence",
        index=False,
    )

excel_data = excel_buffer.getvalue()

download1, download2 = st.columns(2)

with download1:
    st.download_button(
        label="Download All Companies (CSV)",
        data=csv_data,
        file_name="all_company_analyses.csv",
        mime="text/csv",
        use_container_width=True,
    )

with download2:
    st.download_button(
        label="Download All Companies (Excel)",
        data=excel_data,
        file_name="all_company_analyses.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True,
    )


# ============================================================
# 10. FOOTER
# ============================================================

st.divider()

st.caption(
    "Bags & Luggage AI."
    "Lead scores are heuristic estimates based on extracted "
    "public website information. They do not confirm purchase "
    "intent or guarantee that a company is a buyer."
)
