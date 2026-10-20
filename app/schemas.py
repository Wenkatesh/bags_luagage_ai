
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str = ""
    source_url: str = ""
    snippet: str = ""


class CompanyExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_name: str = ""
    website: str = ""

    phone_numbers: list[str] = Field(default_factory=list)
    email_addresses: list[str] = Field(default_factory=list)

    contact_person: str | None = None
    location: list[str] = Field(default_factory=list)

    business_role: Literal[
        "potential_buyer",
        "gifting_reseller",
        "bag_supplier",
        "mixed",
        "unclear",
    ] = "unclear"

    business_category: list[str] = Field(default_factory=list)
    potential_bag_needs: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)

    evidence: list[Evidence] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
