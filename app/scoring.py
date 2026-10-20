
import json
from pathlib import Path


# ==================================================
# CONFIGURATION
# ==================================================

INPUT_FILE = Path("data/processed/company_analysis.json")
OUTPUT_FILE = Path("data/processed/scored_companies.json")


# ==================================================
# KEYWORDS
# ==================================================

BAG_KEYWORDS = [
    "bag",
    "bags",
    "backpack",
    "backpacks",
    "laptop bag",
    "travel bag",
    "travel bags",
    "tote bag",
    "tote bags",
    "duffel",
    "duffle",
    "luggage",
    "sling bag",
    "sling bags",
    "school bag",
    "school bags",
]

CATEGORY_KEYWORDS = [
    "corporate gifting",
    "corporate gift",
    "promotional merchandise",
    "promotional product",
    "branded merchandise",
    "employee gifts",
    "business gifts",
    "corporate merchandise",
]

INTENT_GROUPS = {
    "Bulk or wholesale purchasing": [
        "bulk order",
        "bulk orders",
        "bulk purchase",
        "wholesale",
        "large quantities",
    ],
    "Custom or branded products": [
        "custom bag",
        "custom bags",
        "branded bag",
        "branded bags",
        "logo printing",
        "custom branding",
        "personalized products",
    ],
    "Corporate gifting": [
        "corporate gifting",
        "corporate gifts",
        "business gifts",
        "client gifts",
        "customer gifts",
    ],
    "Employee gifting": [
        "employee gifts",
        "employee welcome kit",
        "welcome kits",
        "onboarding kits",
        "employee merchandise",
    ],
    "Events and promotions": [
        "event merchandise",
        "event giveaways",
        "promotional merchandise",
        "conference giveaways",
        "trade show giveaways",
    ],
}


# ==================================================
# HELPERS
# ==================================================

def as_list(value):
    """Convert a string or list into a list of strings."""
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [
            item for item in value
            if isinstance(item, str)
        ]

    return []


def contains_keyword(text, keywords):
    """Return matching keywords, ignoring capitalization."""
    text = text.lower()

    return [
        keyword
        for keyword in keywords
        if keyword in text
    ]


def get_company_text(company):
    """Combine relevant extracted fields for keyword matching."""
    fields = [
        "business_category",
        "potential_bag_needs",
        "buying_signals",
    ]

    parts = []

    for field in fields:
        parts.extend(as_list(company.get(field)))

    for item in as_list(company.get("company_name")):
        parts.append(item)

    evidence = company.get("evidence", [])

    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                parts.extend([
                    str(item.get("claim", "")),
                    str(item.get("snippet", "")),
                ])

    return " ".join(parts).lower()


# ==================================================
# SCORING
# ==================================================

def score_company(company):
    """Calculate a transparent buying-intent score from 0 to 100."""

    score = 0
    reasons = []

    role = company.get("business_role", "unclear")

    # 1. Business role: maximum positive contribution is 25.
    role_points = {
        "potential_buyer": 25,
        "gifting_reseller": 18,
        "mixed": 12,
        "unclear": 5,
        "bag_supplier": -20,
    }

    points = role_points.get(role, 0)
    score += points

    if points > 0:
        reasons.append(
            f"Business role '{role}': +{points} points"
        )
    elif points < 0:
        reasons.append(
            f"Supplier role may indicate a competitor: {points} points"
        )

    # 2. Explicit bag-related needs: +25.
    bag_needs = as_list(company.get("potential_bag_needs"))
    bag_need_text = " ".join(bag_needs).lower()

    bag_matches = contains_keyword(
        bag_need_text,
        BAG_KEYWORDS,
    )

    if bag_matches:
        score += 25
        reasons.append(
            "Bag-related needs identified: +25 points"
        )

    # 3. Relevant corporate gifting category: +15.
    category_text = " ".join(
        as_list(company.get("business_category"))
    ).lower()

    category_matches = contains_keyword(
        category_text,
        CATEGORY_KEYWORDS,
    )

    if category_matches:
        score += 15
        reasons.append(
            "Relevant corporate gifting/merchandise category: +15 points"
        )

    # 4. Buying-intent signals: +5 per matching group, up to +25.
    full_text = get_company_text(company)
    matched_groups = []

    for group_name, keywords in INTENT_GROUPS.items():
        matches = contains_keyword(full_text, keywords)

        if matches:
            matched_groups.append(group_name)

    intent_points = min(len(matched_groups) * 5, 25)

    if intent_points:
        score += intent_points
        reasons.append(
            f"{len(matched_groups)} buying-signal group(s): "
            f"+{intent_points} points"
        )

    # 5. Supporting evidence: +10 when evidence supports a
    # bag-related or relevant purchasing signal.
    evidence = company.get("evidence", [])
    evidence_supported = False

    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue

            evidence_text = (
                str(item.get("claim", ""))
                + " "
                + str(item.get("snippet", ""))
            ).lower()

            has_bag = bool(
                contains_keyword(evidence_text, BAG_KEYWORDS)
            )

            has_intent = any(
                contains_keyword(evidence_text, keywords)
                for keywords in INTENT_GROUPS.values()
            )

            if has_bag or has_intent:
                evidence_supported = True
                break

    if evidence_supported:
        score += 10
        reasons.append(
            "Supporting source evidence found: +10 points"
        )

    # 6. Public contact information: +5.
    has_phone = bool(as_list(company.get("phone_numbers")))
    has_email = bool(as_list(company.get("email_addresses")))

    if has_phone or has_email:
        score += 5
        reasons.append(
            "Public contact information available: +5 points"
        )

    # Keep score in the 0-100 range.
    score = max(0, min(100, score))

    if score >= 70:
        band = "High"
    elif score >= 40:
        band = "Medium"
    else:
        band = "Low"

    result = dict(company)
    result["buying_intent_score"] = score
    result["score_band"] = band
    result["score_reasons"] = reasons
    result["matched_intent_groups"] = matched_groups

    return result


# ==================================================
# MAIN
# ==================================================

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        companies = json.load(file)

    if not isinstance(companies, list):
        raise ValueError(
            "company_analysis.json must contain a JSON list."
        )

    scored_companies = [
        score_company(company)
        for company in companies
        if isinstance(company, dict)
    ]

    # Highest score first.
    scored_companies.sort(
        key=lambda item: item["buying_intent_score"],
        reverse=True,
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            scored_companies,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\nBuying-intent scoring completed.")
    print(f"Companies scored: {len(scored_companies)}")
    print(f"Output saved to: {OUTPUT_FILE}")

    print("\nRanked prospects:")

    for index, company in enumerate(scored_companies, start=1):
        print(
            f"{index}. {company.get('company_name', 'Unknown')} | "
            f"Score: {company['buying_intent_score']}/100 | "
            f"Band: {company['score_band']} | "
            f"Role: {company.get('business_role', 'unclear')}"
        )


if __name__ == "__main__":
    main()
