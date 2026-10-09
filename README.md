# Aarogya: a RAG support bot and the eval harness that tests it

Aarogya answers health-insurance questions from public policy wordings. The project's real subject is **evaluation**: every bot version runs against a fixed 41-case suite, gets scored by rule checks and an LLM judge, and disputed cases go to a human whose labels measure how far the judge can be trusted.

**Live demo:** `<your Vercel URL>`  **API docs:** `<your HF Space URL>/docs`

<!-- Add screenshots: home (results strip), run dashboard, chat inspector, review page -->

## Why this exists
LLM support bots fail silently: they sound confident while inventing waiting periods or coverage limits. Most teams catch this through anecdotes. This project shows a repeatable alternative: a versioned test suite, measurable quality criteria, and a judge that is itself audited.

## Architecture
```
                  ┌──────────────── Next.js (Vercel) ────────────────┐
                  │ Chat + answer inspector │ Runs │ Compare │ Review │
                  └──────────────────────────┬───────────────────────┘
                                             │ REST
┌──────────────────────────── FastAPI (Hugging Face Spaces, Docker) ────────────────────────────┐
│ Bot turn:  hybrid retrieval (pgvector + full-text, RRF) → confidence gate → Groq LLM (JSON)    │
│            → citation validation → full trace persisted                                        │
│ Eval run:  suite × bot version → rule checks → LLM judge (Gemini, different model family)      │
│            → review routing → metrics, run diff, Cohen's kappa vs human labels                 │
└────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                             │
                               Neon Postgres + pgvector
   documents · chunks (HNSW + GIN) · bot_versions · conversations · messages
   test_suites · test_cases · eval_runs · eval_results · human_labels
```

## Evaluation design
| Layer | What it catches |
|---|---|
| **Test suite** (41 cases) | Policy questions, answers absent from the documents, ambiguous queries, off-topic requests, prompt injection and false premises, Hindi and Hinglish |
| **Rule checks** | Wrong behaviour (answered when it should decline), uncited answers, citations to excerpts that don't exist, required and forbidden phrases, latency budget |
| **LLM judge** | Groundedness (1–5), made-up facts, helpfulness, safety. Written rubric, rationale before scores, temperature 0, a different model family from the bots to avoid self-preference |
| **Judge self-consistency** | The verdict is re-derived from the judge's own scores. Contradictions are flagged |
| **Human review** | Low-confidence, self-contradicting, or rule-vs-judge disagreements, plus a seeded 10% random audit |
| **Judge audit** | Cohen's kappa and a confusion matrix between judge and human labels |
| **Regression tracking** | Case-by-case diff between any two runs |

## Bot design choices
- **Hybrid retrieval.** Policy wording relies on exact terms ("PED", "co-payment", clause numbers) that vector search alone misses.
- **Gate before generation.** Below a similarity threshold the model receives no context, so it can't paraphrase weak matches into confident answers.
- **Typed outcomes** (`answered`, `not_found`, `out_of_scope`, `clarify`). Behaviour becomes testable.
- **Versioned bot configs.** Model, prompt, top-k, and threshold are rows in the database, so runs are comparable.

## Free-tier stack
| Piece | Service |
|---|---|
| Frontend | Next.js 14 + Tailwind on Vercel |
| API | FastAPI on Hugging Face Spaces (Docker) |
| Database | Neon Postgres + pgvector |
| Bot LLMs | Groq: gpt-oss-20b, gpt-oss-120b |
| Judge | Gemini (Google AI Studio free tier) |
| Embeddings | fastembed `bge-small-en-v1.5`, baked into the image |

## Run locally
**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # fill in Neon, Groq, Gemini, admin token
# put 2-3 text-based policy wording PDFs in data/policies/
python -m scripts.ingest_folder data/policies
uvicorn app.main:app --port 7860 --reload
```
**Frontend**
```bash
cd frontend
npm install
cp .env.example .env.local                            # NEXT_PUBLIC_API_URL=http://localhost:7860
npm run dev                                           # http://localhost:3000
```
Sign in with your admin token via "Owner sign-in" to start runs and label results.

## Deploy
1. **Neon:** create a project (Singapore region). Use the connection string in the format shown in `.env.example`.
2. **Hugging Face Space:** create a new Space with the Docker SDK. Push the `backend/` folder as the Space's root:
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/aarogya-api
   git subtree push --prefix backend space main
   ```
   Add secrets: `DATABASE_URL`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `ADMIN_TOKEN`, `CORS_ORIGINS` (your Vercel URL).
3. **Ingest** against the deployed API:
   `curl -X POST https://<space>.hf.space/admin/ingest -H "X-Admin-Token: …" -F "file=@policy.pdf"`
4. **Vercel:** import the GitHub repo, set **Root Directory** to `frontend`, and add `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_GITHUB_URL`.
5. Sign in on the live site and start a run for each bot version, so visitors see real results.

## Known limits
- Free hosting sleeps when idle. The first request can take up to a minute, and the UI says so.
- Free-tier rate limits make a full run take several minutes. Only one run can execute at a time.
- A run in progress is marked failed if the host restarts mid-run.
- Cost figures use list prices hard-coded in `backend/app/evals.py`. Verify them before quoting.

## Data
Public policy-wording PDFs only. No customer, client, or employer data.
