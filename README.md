# Agentic Deep Research

**Agentic Deep Research** (internally branded *Wissen E-Learn*) is a Python-based, multi-agent research assistant that autonomously plans, searches, evaluates, and synthesizes information into a structured, citation-aware report — combining live web search with a local library of reference books (PDFs).

Given a single topic, the system:
1. Breaks the topic into targeted search queries
2. Researches each query across the web *and* a local PDF knowledge base
3. Decides whether the findings are sufficient or whether follow-up research is needed
4. Synthesizes everything into a polished, multi-page Markdown report with a table of contents and source citations

Built on the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), with a rich terminal UI powered by [`rich`](https://github.com/Textualize/rich).

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Local Book / PDF Knowledge Base](#local-book--pdf-knowledge-base)
- [Agents Overview](#agents-overview)
- [Sample Reports](#sample-reports)
- [Known Issues](#known-issues)
- [Roadmap Ideas](#roadmap-ideas)
- [License](#license)

---

## How It Works

The `ResearchCoordinator` (in `coordinator.py`) drives a five-step pipeline for every research request:

1. **Query Analysis** — A `query_agent` breaks the topic down, reasons about the key aspects to cover, and generates 3 focused search queries.
2. **Web + Book Research** — For each query, the coordinator:
   - Runs a DuckDuckGo search and passes each result to a `search_agent`, which scrapes the page and produces a concise summary.
   - Searches the local SQLite-backed book index for relevant PDFs and extracts/summarizes matching passages.
3. **Follow-up Evaluation** — A `follow_up_decision_agent` reviews all findings so far and decides whether the research is complete, or whether 2–3 additional follow-up queries are needed to close specific gaps.
4. **Follow-up Research Round** *(optional)* — If more research is needed, step 2 runs again for the new queries.
5. **Report Synthesis** — A `synthesis_agent` combines every summary into a single, well-structured Markdown report (with a table of contents, headings, and in-text citations).

The final report is displayed in the terminal and can optionally be saved to a `.md` file.

## Architecture

```
                        ┌─────────────────────┐
                        │   User CLI (main.py) │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │  ResearchCoordinator  │
                        │   (coordinator.py)    │
                        └──────────┬───────────┘
                                   │
        ┌───────────────┬─────────┼─────────┬────────────────┐
        ▼               ▼         ▼         ▼                ▼
  query_agent     search_agent  DuckDuckGo  db_search_agent  follow_up_decision_agent
  (query plan)    (web summary)  (DDGS)     (local PDF/book   (stop or continue?)
                                             search + summary)
        │               │                       │                    │
        └───────────────┴───────────────────────┴────────────────────┘
                                   │
                        ┌──────────▼───────────┐
                        │   synthesis_agent      │
                        │  (final Markdown report)│
                        └────────────────────────┘
```

## Project Structure

```
agentic-deepResearch/
├── main.py                     # CLI entry point — runs the full research workflow
├── coordinator.py              # ResearchCoordinator: orchestrates all agents & steps
├── create_db.py                # Creates the SQLite book index and seeds sample entries
├── add_book.py                 # Interactive CLI to register a new PDF book/topic
├── requirements.txt            # Python dependencies
├── research_agents/
│   ├── query_agent.py          # Generates search queries + reasoning for a topic
│   ├── search_agent.py         # Scrapes a URL and summarizes its content
│   ├── db_search_agent.py      # Searches local PDFs for a topic and summarizes matches
│   ├── follow_up_agent.py      # Decides whether more research rounds are needed
│   └── synthasis_agent.py      # Synthesizes all findings into the final report
├── books/                      # Local PDF reference library (sample textbooks)
└── research_report_*.md        # Example generated research reports
```

## Prerequisites

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys) (used by the OpenAI Agents SDK)
- Internet access (for DuckDuckGo web search and page scraping)

## Installation

```bash
# Clone the repository
git clone https://github.com/Karthik-yadav-22/agentic-deepResearch.git
cd agentic-deepResearch

# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root with your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

`main.py` loads this automatically via `python-dotenv` and will raise a clear error at startup if the key is missing.

## Usage

### 1. Set up the local book database (one-time)

The system can supplement web research with locally stored PDF books. Initialize the SQLite index and seed it with the sample books included in `books/`:

```bash
python create_db.py
```

To register additional PDFs interactively:

```bash
python add_book.py
```

You'll be prompted for a topic, a display name, and the path to the PDF (e.g. `books/my_textbook.pdf`).

### 2. Run a research session

```bash
python main.py
```

You'll be prompted to enter a research topic. The tool will then:
- Print its query-generation reasoning and the search queries it chose
- Stream progress as it searches the web and local books
- Show its follow-up decision (and reasoning) before generating the final report
- Render the final report in the terminal
- Optionally save the report to a Markdown file (`research_report_<topic>.md`)

## Local Book / PDF Knowledge Base

Books are tracked in a lightweight SQLite database (`research.db`) with the schema:

| Column      | Description                          |
|-------------|---------------------------------------|
| `id`        | Auto-incrementing primary key         |
| `topic`     | Lowercased topic keyword(s)           |
| `book_name` | Human-readable title                  |
| `file_path` | Path to the PDF on disk               |
| `added_on`  | Timestamp of insertion                |

At research time, `db_search_agent.py` matches the query against stored topics, extracts topic-relevant pages from the matching PDFs using [PyMuPDF](https://pymupdf.readthedocs.io/), and summarizes the extracted text alongside the web results.

The repo ships with five sample textbooks in `books/` (e.g. Tanenbaum's *Computer Networks*, *Modern Operating Systems*, and *Distributed Systems*) to demonstrate the workflow out of the box.

## Agents Overview

| Agent | File | Responsibility |
|---|---|---|
| **Query Agent** | `research_agents/query_agent.py` | Analyzes the topic, reasons about key aspects and challenges, and produces 3 targeted search queries. |
| **Search Agent** | `research_agents/search_agent.py` | Scrapes a given URL (via `requests` + `BeautifulSoup`) and writes a concise 2–3 paragraph summary. |
| **DB Search Agent** | `research_agents/db_search_agent.py` | Finds relevant local PDFs for a topic, extracts matching pages, and summarizes them via a Book Summary Agent. |
| **Follow-up Decision Agent** | `research_agents/follow_up_agent.py` | Reviews accumulated findings and decides whether additional research rounds and queries are needed. |
| **Synthesis Agent** | `research_agents/synthasis_agent.py` | Combines all summaries (web + book) into a single structured Markdown report with a table of contents and citations. |

All agents are built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (`Agent`, `Runner`, `function_tool`) and use Pydantic models for structured outputs where applicable.

## Sample Reports

The repository includes example end-to-end outputs generated by the pipeline:

- `research_report_graphs_used_in_socialmedia_platforms.md`
- `research_report_piggy_backing_in_computer_networks.md`

These illustrate the report structure and formatting the `synthesis_agent` produces.

## Known Issues

- `research_agents/db_search_agent.py` imports `DB_PATH` from a module named `book_db`, which is not present in the repository — the database path is actually defined in `create_db.py`. To use the local-book search feature as-is, either rename `create_db.py`'s import target or add a small `book_db.py` module that exports `DB_PATH = "research.db"`.
- No automated tests or CI configuration are currently included.
- No license file is currently published in the repository — confirm usage terms with the repository owner before reuse.

## License

No license has been published for this repository yet. All rights are reserved by the author unless a license is added. Contact [Karthik-yadav-22](https://github.com/Karthik-yadav-22 or [hrudyagali] for usage permissions.
