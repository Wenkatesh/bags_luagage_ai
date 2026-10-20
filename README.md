# Bags & Luggage AI 
An end-to-end Python project that uses AI-assisted information extraction to identify and analyze potential business opportunities in the bags, luggage, corporate gifting, and promotional merchandise space.

I built this project to explore how website data, Large Language Models (LLMs), and backend technologies can work together to turn unstructured business information into structured, searchable, and actionable insights.

The application collects publicly available website content, extracts company information and potential buying signals, assigns a rule-based lead score, and presents the results through an interactive Streamlit dashboard.

##  Live Application

- **Live Dashboard:** https://bagsluagageai-x3cmju9nwtntovte5t6c7t.streamlit.app/
- **Backend API:** [FastAPI on Render](https://bags-luagage-ai.onrender.com)

##  Project Overview

Researching companies manually involves visiting multiple websites, finding relevant business information, identifying potential product requirements, and organizing the findings for further analysis.

To simplify this process, I developed a pipeline that collects website content and uses an LLM to extract relevant information into a predefined structure. The extracted information is then validated, processed, and scored using business rules.

The final results are made available through a FastAPI backend and displayed in a Streamlit dashboard. Users can select individual companies, review their details and supporting evidence, understand why a score was assigned, and export the collected data.

The project currently processes a selected set of company websites and demonstrates how AI-assisted research can support an initial lead qualification workflow.

## Project Objectives

- Automate the collection and organization of relevant information from selected public company websites.
- Use an LLM to extract structured company details from unstructured website content.
- Identify potential bag requirements and business signals related to corporate gifting, bulk orders, events, and promotional merchandise.
- Handle malformed LLM responses and incomplete extraction results through parsing, validation, and recovery mechanisms.
- Apply explainable, rule-based scoring to prioritize companies for further investigation.
- Build a user-friendly dashboard and expose the results through a REST API.
- Deploy the application so that it can be accessed through a public URL.

##  Key Features

### 1. Website Content Collection

Uses Firecrawl to collect publicly accessible content from selected company websites and relevant pages. The collected content acts as the source material for the extraction pipeline.

### 2. LLM-Based Structured Data Extraction

Uses the Groq API with the `openai/gpt-oss-20b` model to extract information from website text.

The extraction prompt defines the expected JSON structure, field descriptions, permitted business-role values, and evidence requirements. This helps the model return consistent company records instead of unrestricted text responses.

### 3. Company Classification and Buying Signals

Extracts business information such as:

- Company name and website
- Public business phone numbers and email addresses
- Location and business category
- Business role, such as potential buyer, gifting reseller, bag supplier, or mixed
- Potential bag and luggage requirements
- Buying signals related to corporate gifting, bulk purchasing, custom branding, and events
- Supporting evidence and source URLs
- Information that is missing and may require further research

These signals help identify possible opportunities, but they do not establish confirmed purchase intent.

### 4. JSON Parsing, Normalization, and Validation

LLM responses are not always perfectly formatted. To make the extraction workflow more reliable, I implemented multiple processing steps:

- Attempts to repair malformed JSON using `json_repair`.
- Attempts to recover a company-level JSON object if the complete response cannot be parsed directly.
- Normalizes extracted fields into consistent formats.
- Uses Pydantic to validate the result against the expected `CompanyExtraction` schema.
- Saves the raw model response and parsing or validation error to a debug file when extraction fails.

This approach reduces failures caused by inconsistent output formatting and makes extraction errors easier to investigate.

### 5. Checkpoint Based Recovery

The extraction pipeline stores successful chunk results in a JSONL checkpoint file.

Each chunk is assigned a stable key based on its website domain, source URL, chunk index, and content hash. When the pipeline runs again, previously successful matching chunks can be reused rather than sent to the LLM again.

Failed chunks are reported separately and can be attempted again in a subsequent run. This helps preserve completed work, reduces unnecessary repeated API calls, and makes the pipeline easier to resume after interruptions.

### 6. Explainable Lead Scoring

Implements a rule-based scoring system that assigns each company a score from 0 to 100.

The scoring logic considers factors such as business role, bag-related needs, relevant business categories, buying-signal groups, and supporting evidence. It also considers negative factors, such as a supplier role that may indicate a potential competitor.

The dashboard displays the score band and the reasons behind the assigned score, making it easier to review why a company received a particular score.

The score is a heuristic for prioritization, not a trained machine-learning prediction or a verified probability of purchase.

### 7. Interactive Streamlit Dashboard

Provides a web interface for reviewing the processed company records.

Users can:

- View the total number of companies and priority distribution.
- Select a company from a dropdown.
- Analyze company details and its assigned score.
- Review potential bag needs and buying signals.
- Inspect supporting evidence and source URLs.
- Download company data in CSV and Excel formats.

### 8. FastAPI Backend

Implements a REST API that serves the processed company data to the Streamlit frontend.

The API separates data access from the dashboard, making the application easier to organize and maintain.

### 9. Public Deployment

Deployed the backend on Render and the dashboard on Streamlit Community Cloud. The dashboard communicates with the hosted FastAPI service, allowing users to access the application without running the project locally.

## Application Architecture

```text
Selected Company Websites
          |
          v
       Firecrawl
          |
          v
Website Content Collection
          |
          v
     Text Chunking
          |
          v
Groq LLM — gpt-oss-20b
          |
          v
Structured JSON Extraction
          |
          v
JSON Repair and Fallback Parsing
          |
          v
Normalization and Pydantic Validation
          |
          v
Checkpointing and Error Handling
          |
          v
Company Data Processing
          |
          v
Rule-Based Lead Scoring
          |
          v
scored_companies.json
          |
          v
       FastAPI API
          |
          v
   Streamlit Dashboard
          |
          v
Company Analysis and Data Export
```

## ⚙️ Technical Implementation

### Website Content Processing

The pipeline starts by collecting website content through Firecrawl. The text is split into smaller chunks so that each section can be processed independently.

Each chunk is sent to the LLM with the source metadata and extraction instructions. The prompt requires a consistent JSON object and asks the model to use only information supported by the supplied website content.

### Structured Extraction and Data Quality

After receiving the model response, the application attempts to parse and normalize the output before validating it with Pydantic.

The extraction workflow also handles common output problems, including malformed JSON, missing fields, unexpected list formats, invalid business-role values, and incorrectly formatted evidence entries.

When parsing or validation fails, the raw response and error details are saved for debugging rather than silently treating the output as a valid company record.

### Recovery and Checkpoint Strategy

The pipeline uses a JSONL checkpoint file to save successful chunk extractions incrementally.

A stable chunk key allows completed work to be identified in subsequent runs. This means a rerun can reuse successful results and focus on chunks that have not been completed successfully.

This is particularly useful when processing multiple pages because a failure in one chunk does not automatically require repeating every previously successful extraction.

The current recovery mechanisms focus on response parsing, validation, and resuming incomplete work. They do not guarantee that every website or failed API request will be recovered automatically.

### Lead Scoring and Evidence Review

After extraction, the company information is processed into records containing business details, identified signals, evidence, and scoring information.

The rule-based scoring approach makes the initial prioritization logic understandable. Instead of showing only a number, the dashboard also presents reasons contributing to the score.

Evidence snippets and source URLs provide a way to check whether the extracted information is supported by the original website content.

##  Technology Stack

| Technology | How it is used |
|---|---|
| Python | Core application logic and data processing |
| Firecrawl | Website content collection |
| Groq API | LLM inference |
| `openai/gpt-oss-20b` | Company information extraction |
| `json_repair` | Repairing malformed JSON responses |
| Pydantic | Structured data validation |
| FastAPI | REST API development |
| Streamlit | Interactive dashboard |
| Pandas | Tabular data handling and exports |
| JSON | Storage of processed company records |
| JSONL | Incremental extraction checkpoints |
| Render | Backend hosting |
| Streamlit Community Cloud | Frontend hosting |

##  Project Structure

```text
BAGS_LUGGAGE_AI/
├── app/
│   ├── api.py
│   ├── dashboard.py
│   ├── chunking.py
│   ├── extractor.py
│   ├── process.py
│   ├── scoring.py
│   ├── schemas.py
│   └── config.py
├── data/
│   └── processed/
│       ├── scored_companies.json
│       ├── chunk_extractions.jsonl
│       └── last_failed_llm_response.txt
├── requirements.txt
└── README.md
```

The processed JSON file stores the company records used by the API. The JSONL checkpoint file and debug file are generated or updated during extraction. These files may not exist until the relevant workflow has been executed.

##  Running the Project Locally

### Prerequisites

- Python installed
- Git installed
- Firecrawl API key for website collection
- Groq API key for LLM-based extraction

### Step 1: Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd BAGS_LUGGAGE_AI
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with the actual GitHub repository URL.

### Step 2: Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```cmd
.venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure API keys

Configure the Firecrawl and Groq API keys according to the project's configuration in `app/config.py`.

If using a `.env` file, ensure the application loads it correctly. Never commit API keys or the `.env` file to GitHub.

### Step 5: Start the FastAPI backend

```bash
python -m uvicorn app.api:app --reload
```

The backend will be available at:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

### Step 6: Start the Streamlit dashboard

Open a second terminal, activate the virtual environment, and run:

```bash
python -m streamlit run app/dashboard.py
```

Make sure the dashboard API base URL points to `http://127.0.0.1:8000` when running locally.

The API expects the processed company records to be available in `data/processed/scored_companies.json`.

### Running the Extraction Pipeline

The website extraction workflow is implemented in the application processing modules. Check `app/process.py` for the current entry point and required configuration before running it.

## 🔌 API Endpoints

| Endpoint | Description |
|---|---|
| `/` | Returns the API status message |
| `/health` | Checks the API health |
| `/api/companies` | Returns all saved company records |
| `/api/company?name=Swagilo` | Retrieves a company by name |
| `/docs` | Opens the interactive FastAPI documentation |

##  Current Scope and Limitations

- The current version processes selected company websites rather than discovering every business online.
- Extraction quality depends on the website content available and the model's response.
- Some records may have missing contact information or incomplete evidence.
- The scoring system is rule-based and has not been established as a calibrated purchase-probability model.

##  What I Learned

Building this project gave me practical experience in connecting several components into an end-to-end AI-assisted application.

I learned how to collect website content, split text into manageable chunks, design prompts for structured LLM output, and validate model responses using Pydantic. I also worked on JSON repair, fallback parsing, checkpointing, and debugging to make the extraction workflow more resilient to failures.

On the application side, I gained experience building REST endpoints with FastAPI, connecting a frontend to a backend, creating an interactive dashboard with Streamlit, exporting data, managing API keys, and deploying the application online.

Most importantly, this project helped me understand that building an AI application involves more than calling an LLM. Data quality, validation, error handling, evidence, and clear presentation are also important parts of a reliable workflow.

##  Future Improvements

- Expand website coverage and improve content collection.
- Add stronger retry and rate-limit handling for external API failures.
- Evaluate scoring rules against manually reviewed company leads.
- Introduce automated refresh scheduling and more detailed pipeline monitoring.
