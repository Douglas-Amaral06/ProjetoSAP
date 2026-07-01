# Tech Stack & Build System

## Core Dependencies

### Web Framework & UI
- **Streamlit** (>=1.35) — Multi-page app framework
- **Pandas** (>=2.0) — Data manipulation and display
- **Werkzeug** (>=2.3) — Password hashing utilities

### AI & NLP
- **LangChain Core** (>=0.2) — LLM orchestration
- **LangChain Google GenAI** (>=1.0) — Gemini integration
- **Sentence Transformers** (>=2.2) — Semantic embeddings (all-MiniLM-L6-v2 model)
- **NumPy** (>=1.24) — Numerical operations for embeddings

### Database
- **SQLite3** (built-in) — Development database
- **psycopg2-binary** (>=2.9) — PostgreSQL driver (production)
- **python-dotenv** (>=1.0) — Environment configuration

### Optional/Future
- **torch** (>=2.0) — ML framework (for custom models)
- **transformers** (>=4.30) — Model library
- **scikit-learn** (>=1.3) — ML utilities
- **mlflow** (>=2.0) — Experiment tracking
- **boto3** — AWS S3 integration (file attachments)
- **streamlit-autorefresh** (>=1.0) — Auto-refresh UI (optional)
- **pytest** (>=7.0) — Testing framework
- **black**, **flake8** — Code formatting and linting

See `requirements.txt` (essential) and `requirements_full.txt` (all dependencies).

## Build & Run Commands

### Development Setup
```bash
# Clone and install dependencies
git clone <repo>
cd helpdesk_sap_ia
pip install -r requirements.txt

# Create .env file (copy from .env.example or set variables)
cp .env.example .env
export GOOGLE_API_KEY=<your-key>
export DB_TYPE=sqlite  # or postgres

# Initialize database
python -c "import backend; backend.init_db()"
```

### Running the Application
```bash
# Terminal 1: Customer interface (port 8501)
streamlit run cliente_app.py

# Terminal 2: Support team interface (port 8502)
streamlit run equipe_app.py --server.port=8502

# Both interfaces share the same SQLite database (sap_chamados.db)
```

### Testing & Code Quality
```bash
# Run tests (if available)
pytest tests/ -v

# Format code
black *.py

# Lint code
flake8 *.py --max-line-length=120
```

### Database Migration (PostgreSQL)
```bash
# See postgres_setup.md for detailed instructions
# Quick setup:
export DB_TYPE=postgres
export PG_HOST=localhost
export PG_USER=postgres
export PG_DB=sap_helpdesk

python -c "import backend; backend.init_db()"
```

### Export & Analysis (ML - POC)
```bash
# Run ML viability analysis
python databricks_training.py

# Generates datasets in data/training/ folder
```

## Environment Variables

| Variable | Purpose | Example | Default |
|---|---|---|---|
| `GOOGLE_API_KEY` | Gemini API key | `AQ.Ab8R...` | Required |
| `DB_TYPE` | Database type | `sqlite` or `postgres` | `sqlite` |
| `SAP_HELPDESK_DB` | SQLite path | `./sap_chamados.db` | `./sap_chamados.db` |
| `PG_HOST` | PostgreSQL host | `localhost` | `localhost` |
| `PG_PORT` | PostgreSQL port | `5432` | `5432` |
| `PG_DB` | PostgreSQL database name | `sap_helpdesk` | `sap_helpdesk` |
| `PG_USER` | PostgreSQL user | `postgres` | `postgres` |
| `PG_PASSWORD` | PostgreSQL password | (sensitive) | `` (empty) |
| `AWS_ACCESS_KEY_ID` | AWS credentials (S3) | (sensitive) | `` |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials (S3) | (sensitive) | `` |
| `AWS_S3_BUCKET` | S3 bucket name | `meu-sap-helpdesk` | `` |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` | `us-east-1` |

## Key File Locations

```
helpdesk_sap_ia/
├── sap_chamados.db       # SQLite database (auto-created)
├── sap_chamados.db-shm   # SQLite WAL shared memory
├── sap_chamados.db-wal   # SQLite write-ahead log
├── anexos/               # Directory for uploaded file attachments
├── data/training/        # ML dataset exports
├── .env                  # Environment configuration (not in git)
├── requirements.txt      # Essential dependencies
└── requirements_full.txt # All dependencies (including optional)
```

## Performance Considerations

1. **SQLite vs PostgreSQL**
   - SQLite: Good for single-threaded, file-based workloads
   - PostgreSQL: Required for multi-user concurrent access in production
   - WAL mode enabled for SQLite (better concurrency)

2. **Semantic Search**
   - Embeddings cached in knowledge_base.embedding (BLOB)
   - Model (all-MiniLM-L6-v2) lazy-loaded on first use
   - Threshold: 0.7 similarity (configurable in backend.py)

3. **Streamlit Caching**
   - Leverage Streamlit's @st.cache_data for expensive operations
   - Currently not extensively used; can be optimized

## Common Issues & Solutions

| Issue | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'streamlit'` | Dependencies not installed | `pip install -r requirements.txt` |
| `ImportError: psycopg2 not found` | PostgreSQL driver missing | `pip install psycopg2-binary` |
| `GOOGLE_API_KEY not set` | Missing API key | Set `GOOGLE_API_KEY` in .env |
| `Database is locked` | Concurrent write attempts | Enable WAL mode (auto-enabled for SQLite) |
| `Port already in use` | Streamlit port conflict | Use `streamlit run ... --server.port=XXXX` |

## Future Optimization Opportunities

- Add @st.cache_data decorators for DB queries
- Implement connection pooling for PostgreSQL
- Add query indexes on frequently searched columns (problem_chave, status)
- Consider async DB operations for high concurrency
- Implement rate limiting on Gemini API calls
