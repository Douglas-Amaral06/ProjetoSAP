# SAP Helpdesk with AI — Product Overview

## What is it?
An internal helpdesk system designed for SAP support tickets with AI-powered resolution. It's a pilot system that validates the flow of: customer opens ticket → AI or team resolves → solution is recorded for future reuse.

## Core Value Proposition
- **For customers**: Quick ticket resolution with AI suggestions, tracked history, and knowledge base lookups
- **For support team**: Reduced workload through AI-assisted resolution, centralized knowledge base, priority validation, attachment support
- **For the organization**: Improved SLA compliance, documented solutions, and automated knowledge retention

## Key Features
- **Dual Interface**: Separate apps for customers (clients) and support team (equipe)
- **AI-Powered Suggestions**: Uses Google Gemini to analyze tickets and propose solutions based on:
  - Knowledge Base (semantic search via embeddings)
  - Internal model norms (rules and best practices)
  - Historical solutions
- **Knowledge Management**: Solutions are automatically saved and reused for similar problems
- **Priority Validation**: AI suggests priority levels with justification; team notified if divergence detected
- **Workflow States**: Aberto (Open) → Em Atendimento (In Progress) → Aguardando Confirmação (Awaiting Confirmation) → Resolvido (Resolved)
- **Notifications**: Real-time notifications for SLA violations, priority divergences, and status changes
- **Interaction History**: Thread-based conversation between customer and support team within each ticket
- **File Attachments**: Support for uploading/downloading files (JPG, PNG, PDF, DOC, XLS, TXT)
- **Database Flexibility**: Dual support for SQLite (development) and PostgreSQL (production)

## Current Scope (Pilot)
✅ User authentication (basic)  
✅ Ticket creation and management  
✅ Semantic search in knowledge base  
✅ AI-powered resolution suggestions  
✅ Priority validation  
✅ SLA tracking  
✅ File attachments  
✅ Interaction history  
✅ PostgreSQL support  

## Architecture
- **Language**: Python 3.11+
- **Web Framework**: Streamlit
- **AI Provider**: Google Gemini API (via LangChain)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Styling**: Custom dark theme (GitHub-inspired)

## Key Modules
- `backend.py` — Core business logic, database operations, shared functions
- `aiengine.py` — Gemini integration, ticket analysis, solution generation
- `cliente_app.py` — Customer-facing interface (port 8501)
- `equipe_app.py` — Support team interface (port 8502)
- `theme.py` — Shared dark theme and CSS utilities
- `databricks_training.py` — ML viability analysis and dataset export (POC)

## No Auth Model (Yet)
Currently uses basic in-app authentication (username/password hashed). Future versions may integrate with corporate AD/LDAP. Always validate user.role for access control.
