
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.chunking import split_text
from app.extractor import extract_page_chunks


# ==================================================
# CONFIGURATION
# ==================================================

INPUT_FILE = Path("data/raw/scraped_websites.json")
OUTPUT_DIR = Path("data/processed")
OUTPUT_FILE = OUTPUT_DIR / "company_analysis.json"


# ==================================================
# GENERAL HELPERS
# ==================================================

def unique_strings(values):
    """Return unique, non-empty strings while preserving order."""
    result = []
    seen = set()

    for value in values:
        if not isinstance(value, str):
            continue

        value = value.strip()

        if value and value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)

    return result


def normalize_list(value):
    """Normalize a field to a list of strings."""
    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    return unique_strings([
        str(item)
        for item in value
        if isinstance(item, (str, int, float))
    ])


def load_existing_results():
    """Load previously saved company records without discarding them."""
    if not OUTPUT_FILE.exists():
        return []

    try:
        with OUTPUT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return [
                item for item in data
                if isinstance(item, dict) and item.get("domain")
            ]

    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: Could not load existing company results: {exc}")
        print("The existing output file has not been overwritten.")

        raise

    return []


def save_results(results):
    """Save company records to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    temporary_file.replace(OUTPUT_FILE)


def compact_summary(extractions):
    """Build a small context summary from previously extracted facts."""
    companies = []
    contacts = []
    needs = []
    signals = []

    for item in extractions:
        if not isinstance(item, dict):
            continue

        companies.append(item.get("company_name", ""))
        contacts.extend(normalize_list(item.get("phone_numbers")))
        contacts.extend(normalize_list(item.get("email_addresses")))
        needs.extend(normalize_list(item.get("potential_bag_needs")))
        signals.extend(normalize_list(item.get("buying_signals")))

    summary = {
        "company_names": unique_strings(companies)[:3],
        "known_contacts": unique_strings(contacts)[:10],
        "potential_bag_needs": unique_strings(needs)[:10],
        "buying_signals": unique_strings(signals)[:10],
    }

    return json.dumps(summary, ensure_ascii=False)


# ==================================================
# COMPANY MERGING
# ==================================================

def merge_extractions(domain, page_records, extractions):
    """Merge chunk-level extractions into one company record."""

    def get_values(field):
        values = []

        for item in extractions:
            if isinstance(item, dict):
                values.extend(normalize_list(item.get(field)))

        return unique_strings(values)

    def first_value(field):
        for item in extractions:
            if not isinstance(item, dict):
                continue

            value = item.get(field)

            if isinstance(value, str) and value.strip():
                if value.strip().lower() not in {
                    "unknown",
                    "not available",
                    "none",
                    "null",
                }:
                    return value.strip()

        return ""

    # Merge roles without allowing "unclear" to override known roles.
    allowed_roles = {
        "potential_buyer",
        "gifting_reseller",
        "bag_supplier",
        "mixed",
        "unclear",
    }

    roles = {
        item.get("business_role")
        for item in extractions
        if isinstance(item, dict)
        and item.get("business_role") in allowed_roles
    }

    substantive_roles = roles - {"unclear", "mixed"}

    if "mixed" in roles or len(substantive_roles) > 1:
        business_role = "mixed"
    elif len(substantive_roles) == 1:
        business_role = next(iter(substantive_roles))
    else:
        business_role = "unclear"

    # Deduplicate evidence using all three identifying fields.
    evidence = []
    seen_evidence = set()

    for item in extractions:
        if not isinstance(item, dict):
            continue

        entries = item.get("evidence", [])

        if isinstance(entries, dict):
            entries = [entries]

        if not isinstance(entries, list):
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            claim = entry.get("claim", "")
            snippet = entry.get("snippet", "")
            evidence_url = entry.get("source_url", "")

            if not isinstance(claim, str) or not isinstance(snippet, str):
                continue

            claim = claim.strip()
            snippet = snippet.strip()

            if not claim or not snippet:
                continue

            if not isinstance(evidence_url, str):
                evidence_url = ""

            evidence_url = evidence_url.strip()

            key = (claim, evidence_url, snippet)

            if key not in seen_evidence:
                seen_evidence.add(key)
                evidence.append({
                    "claim": claim,
                    "source_url": evidence_url,
                    "snippet": snippet,
                })

    company_name = first_value("company_name")
    phones = get_values("phone_numbers")
    emails = get_values("email_addresses")

    missing_information = get_values("missing_information")

    if not company_name:
        missing_information.append("Company name not identified")

    if not phones:
        missing_information.append("Public phone number not found")

    if not emails:
        missing_information.append("Public email address not found")

    source_urls = unique_strings([
        record.get("source_url")
        or record.get("page_url")
        or record.get("url", "")
        for record in page_records
        if isinstance(record, dict)
    ])

    pages_with_content = sum(
        bool(
            isinstance(record.get("markdown"), str)
            and record["markdown"].strip()
        )
        for record in page_records
    )

    # This is contact-data qualification, not buyer qualification.
    qualified = bool(company_name and (phones or emails))

    return {
        "domain": domain,
        "company_name": company_name or domain,
        "website": first_value("website") or f"https://{domain}",
        "phone_numbers": phones,
        "email_addresses": emails,
        "contact_person": first_value("contact_person") or None,
        "location": get_values("location"),
        "business_role": business_role,
        "business_category": get_values("business_category"),
        "potential_bag_needs": get_values("potential_bag_needs"),
        "buying_signals": get_values("buying_signals"),
        "evidence": evidence,
        "source_urls": source_urls,
        "pages_found": len(page_records),
        "pages_with_content": pages_with_content,
        "extracted_chunks": len(extractions),
        "qualification_status": (
            "qualified" if qualified else "needs_review"
        ),
        "missing_information": unique_strings(missing_information),
    }


# ==================================================
# PRESERVE PREVIOUS COMPANY RESULTS
# ==================================================

def merge_company_records(old_record, new_record):
    """
    Merge a newly processed company with its previous saved record.

    Existing list values are retained if a later run has partial failures.
    """
    merged = dict(old_record)

    list_fields = [
        "phone_numbers",
        "email_addresses",
        "location",
        "business_category",
        "potential_bag_needs",
        "buying_signals",
        "source_urls",
        "missing_information",
    ]

    for field in list_fields:
        merged[field] = unique_strings(
            normalize_list(old_record.get(field))
            + normalize_list(new_record.get(field))
        )

    # Merge evidence without duplicates.
    evidence = []
    seen = set()

    for item in (
        old_record.get("evidence", [])
        + new_record.get("evidence", [])
    ):
        if not isinstance(item, dict):
            continue

        key = (
            item.get("claim", ""),
            item.get("source_url", ""),
            item.get("snippet", ""),
        )

        if key not in seen:
            seen.add(key)
            evidence.append(item)

    merged["evidence"] = evidence

    # Prefer newly extracted non-empty scalar values.
    for field in (
        "company_name",
        "website",
        "contact_person",
        "business_role",
        "qualification_status",
    ):
        new_value = new_record.get(field)

        if new_value not in (None, ""):
            merged[field] = new_value

    # Preserve the latest extraction metrics.
    for field in (
        "pages_found",
        "pages_with_content",
        "extracted_chunks",
        "successful_chunks",
        "failed_chunks",
        "extraction_status",
    ):
        if field in new_record:
            merged[field] = new_record[field]

    return merged


# ==================================================
# MAIN PROCESS
# ==================================================

def process_scraped_data():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Scraped data not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            f"{INPUT_FILE} must contain a JSON list of page records."
        )

    # Keep previous results so interrupted runs don't erase them.
    existing_results = load_existing_results()

    existing_by_domain = {
        record["domain"]: record
        for record in existing_results
        if record.get("domain")
    }

    # Group successful scraped pages by website.
    companies = defaultdict(list)

    for record in records:
        if not isinstance(record, dict):
            continue

        if record.get("status") != "success":
            continue

        markdown = record.get("markdown", "")

        if not isinstance(markdown, str) or not markdown.strip():
            continue

        domain = (
            record.get("domain", "")
            .lower()
            .removeprefix("www.")
            .strip()
        )

        if domain:
            companies[domain].append(record)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Keep previous results in the output unless updated successfully.
    company_results = list(existing_by_domain.values())

    total_chunks = 0
    successful_chunks = 0
    failed_chunks = 0

    for company_index, (domain, pages) in enumerate(
        companies.items(), start=1
    ):
        print(f"\n[{company_index}/{len(companies)}] {domain}")

        extractions = []
        company_total_chunks = 0
        company_successful_chunks = 0
        company_failed_chunks = 0

        for page_index, page in enumerate(pages, start=1):
            source_url = (
                page.get("source_url")
                or page.get("page_url")
                or page.get("url", "")
            )

            title = page.get("page_title") or page.get("title", "")
            chunks = split_text(page.get("markdown", ""))

            print(
                f"  Page {page_index}/{len(pages)}: "
                f"{len(chunks)} chunk(s)"
            )

            for chunk in chunks:
                company_total_chunks += 1
                total_chunks += 1

                prior_facts = compact_summary(extractions)

                results_for_chunk = extract_page_chunks(
                    chunks=[chunk],
                    domain=domain,
                    source_url=source_url,
                    company_title=title,
                    prior_facts=prior_facts,
                )

                if results_for_chunk:
                    extractions.extend(results_for_chunk)
                    company_successful_chunks += 1
                    successful_chunks += 1
                else:
                    company_failed_chunks += 1
                    failed_chunks += 1

        # If every chunk failed, preserve the old result for this domain.
        if not extractions:
            print(
                "  No successful extractions. "
                "Preserving any previously saved company record."
            )
            continue

        company_record = merge_extractions(
            domain=domain,
            page_records=pages,
            extractions=extractions,
        )

        company_record["successful_chunks"] = company_successful_chunks
        company_record["failed_chunks"] = company_failed_chunks

        if company_failed_chunks == 0:
            company_record["extraction_status"] = "complete"
        else:
            company_record["extraction_status"] = "partial"

        # A partial run must not erase previously discovered facts.
        old_record = existing_by_domain.get(domain)

        if old_record:
            company_record = merge_company_records(
                old_record,
                company_record,
            )

        # Update or add this company's record.
        existing_by_domain[domain] = company_record

        company_results = list(existing_by_domain.values())
        save_results(company_results)

        print(
            f"  Company: {company_record['company_name']}\n"
            f"  Role: {company_record['business_role']}\n"
            f"  Contacts: "
            f"{len(company_record['phone_numbers'])} phone(s), "
            f"{len(company_record['email_addresses'])} email(s)\n"
            f"  Extraction: {company_record['extraction_status']}\n"
            f"  Successful chunks: {company_successful_chunks}\n"
            f"  Failed chunks: {company_failed_chunks}\n"
            f"  Contact status: "
            f"{company_record['qualification_status']}"
        )

    print("\nProcessing complete.")
    print(f"Websites processed: {len(companies)}")
    print(f"Chunks attempted: {total_chunks}")
    print(f"Successful chunks: {successful_chunks}")
    print(f"Failed chunks: {failed_chunks}")
    print(f"Companies saved: {len(company_results)}")

    
    qualified_count = sum(
        1 for r in company_results
        if r.get("qualification_status") == "qualified"
    )

    review_count = sum(
        1 for r in company_results
        if r.get("qualification_status") == "needs_review"
    )

    print(f"Qualified by contact availability: {qualified_count}")
    print(f"Needs review: {review_count}")

    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    process_scraped_data()
