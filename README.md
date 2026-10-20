# Aarogya: a RAG support bot and the eval harness that tests it

Aarogya answers health-insurance questions from public policy wordings. The project's real subject is **evaluation**: every bot version runs against a fixed 41-case suite, gets scored by rule checks and an LLM judge, and disputed cases go to a human whose labels measure how far the judge can be trusted.

**Live demo:** https://aarogya-blue.vercel.app  ·  **API docs:** https://aarogya-api-62r4.onrender.com/docs

> The API runs on Render's free tier and sleeps when idle. The first request can take about a minute; the site shows a "waking up" message meanwhile.

| Home: latest run at a glance | Chat with the answer inspector |
|---|---|
| ![Home page](docs/screenshots/home.png) | ![Chat and answer inspector](docs/screenshots/chat.png) |

| Human review queue |
|---|
| ![Human review](docs/screenshots/review.png) |

## Why this exists
LLM support bots fail silently: they sound confident while inventing waiting periods or coverage limits. Most teams catch this through anecdotes. This project shows a repeatable alternative: a versioned test suite, measurable quality criteria, and a judge that is itself audited.

## Architecture
```
                  ┌──────────────── Next.js (Vercel) ────────────────┐
                  │ Chat + answer inspector │ Runs │ Compare │ Review │
                  └──────────────────────────┬───────────────────────┘
                                             │ REST
┌───────────────────────────────── FastAPI (Render, Docker) ─────────────────────────────────────┐
│ Bot turn:  hybrid retrieval (pgvector + full-text, RRF) → confidence gate → Groq LLM (JSON)    │
│            → citation validation → full trace persisted                                        │
│ Eval run:  suite × bot version → rule checks → LLM judge (Qwen, different model family)        │
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

## Results (v1, 41 cases, judged by Qwen3.8-27B)
Same suite, same prompt, same retrieval; only the model changes.

| Metric | gpt-oss-120b | gpt-oss-20b |
|---|---|---|
| **Cases passed** (rule checks **and** judge) | **85.4%** | **85.4%** |
| Behaved as expected (right outcome type) | 92.7% | 92.7% |
| Made-up facts (of answered cases) | 10.5% | 13.3% |
| Groundedness (judge, 1–5) | 4.68 | 4.60 |
| Valid citations | 100% | 100% |
| Latency p50 / p95 | 2.1 s / 13.8 s | 1.5 s / 9.1 s |
| Est. cost per 1,000 conversations | $0.28 | $0.13 |
| Routed to human review | 6 | 7 |

| Category | Cases | 120b | 20b |
|---|---|---|---|
| Policy questions | 16 | 81% | 75% |
| Answer not in the documents | 6 | 100% | 83% |
| Ambiguous | 4 | 75% | 100% |
| Off-topic | 5 | 100% | 100% |
| Prompt injection / false premise | 6 | 83% | 100% |
| Hindi and Hinglish | 4 | 75% | 75% |

**What this says**
- The 20b model matches the 120b pass rate at **about half the cost** and a third lower p95 latency, but invents facts more often (13.3% vs 10.5%) and is weaker on real policy questions. For a support bot, the made-up-fact rate is the number that matters most, so neither is shippable as is.
- Off-topic and "not in the documents" cases are near-perfect: the confidence gate and typed outcomes work.
- Most failures are on in-scope questions. Example: asked whether cataract surgery is covered, the bot retrieved the clause listing cataract under a waiting period but answered "not found", because it never infers "covered after the wait". That is the target for a v2 prompt.
- The judge is not yet audited: judge-vs-human agreement (Cohen's kappa) appears on the Review page once enough cases are labelled.

| Run dashboard | Compare two runs |
|---|---|
| ![Run dashboard](docs/screenshots/dashboard.png) | ![Compare runs](docs/screenshots/compare.png) |

## Bot design choices
- **Hybrid retrieval.** Policy wording relies on exact terms ("PED", "co-payment", clause numbers) that vector search alone misses.
- **Gate before generation.** Below a similarity threshold the model receives no context, so it can't paraphrase weak matches into confident answers.
- **Typed outcomes** (`answered`, `not_found`, `out_of_scope`, `clarify`). Behaviour becomes testable.
- **Versioned bot configs.** Model, prompt, top-k, and threshold are rows in the database, so runs are comparable.

## Free-tier stack
| Piece | Service |
|---|---|
| Frontend | Next.js 14 + Tailwind on Vercel |
| API | FastAPI on Render (Docker, free web service) |
| Database | Neon Postgres + pgvector |
| Bot LLMs | Groq: gpt-oss-20b, gpt-oss-120b |
| Judge | Groq: Qwen3.8-27B (switchable to Gemini via `JUDGE_PROVIDER`) |
| Embeddings | fastembed `bge-small-en-v1.5`, baked into the image |

## Run locally
**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # fill in Neon, Groq, admin token (Gemini optional)
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
2. **Render:** New → Web Service → connect this GitHub repo. Set **Root Directory** to `backend`, **Language** to Docker, **Instance type** to Free, and **Health Check Path** to `/health`.
   Add environment variables: `DATABASE_URL`, `GROQ_API_KEY`, `ADMIN_TOKEN`, `CORS_ORIGINS` (your Vercel URL), `JUDGE_PROVIDER=groq`, `JUDGE_MODEL=qwen/qwen3.8-27b`.
3. **Ingest and evaluate locally.** The local backend and the deployed one share the Neon database, so documents, eval runs, and labels created locally appear on the live site. This keeps slow eval runs off the free instance.
4. **Vercel:** import the GitHub repo, set **Root Directory** to `frontend`, and add `NEXT_PUBLIC_API_URL` (your Render URL) and `NEXT_PUBLIC_GITHUB_URL`.

## Known limits
- The free Render instance sleeps after 15 idle minutes. The first request then takes about a minute, and the UI says so.
- Free-tier rate limits make a full run take several minutes. Only one run can execute at a time.
- A run in progress is marked failed if the host restarts mid-run.
- Cost figures use list prices hard-coded in `backend/app/evals.py`. Verify them before quoting.
- The judge started on Gemini's free tier, which allows only 20 requests a day per model, fewer than one 41-case run. The judge now runs on Groq (Qwen), still a different model family from the gpt-oss bots. Judge calls are paced, and any case where the judge errors can be re-judged without re-running the bot (`python -m scripts.rejudge <run> [--all]`).

## Data
Public policy-wording PDFs only. No customer, client, or employer data.
