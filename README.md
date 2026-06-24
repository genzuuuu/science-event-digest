# Science Event Digest

Automated bilingual (EN/ZH) digests for:

1. **PKS Weekly** — talks, colloquia, workshops at [MPI PKS Dresden](https://www.pks.mpg.de) for the coming week (every Sunday).
2. **Conference Deadlines** — global physics / materials / AI conferences with approaching submission deadlines (last Sunday of each month).

## Data sources

| Source | Coverage |
|--------|----------|
| [ai-deadlines](https://mlciv.com/ai-deadlines/) | Top-tier AI / ML / CV / NLP / robotics |
| `data/curated_conferences.json` | Verified international physics / materials / AI venues |
| [WikiCFP](https://wikicfp.com) | APS, MRS, IEEE, condensed matter (international filter) |
| [E-MRS](https://www.european-mrs.com/meetings/deadlines) | European materials research meetings |

WikiCFP results are filtered to drop low-signal regional aggregator conferences (especially China/SEA spam) while keeping IEEE and society events in US/Europe/Japan/Korea/Australia.

## Required GitHub Secrets

Copy from your `arXiv_cond-mat` repo (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `API_KEY` | DeepSeek API key |
| `BASE_URL` | `https://api.deepseek.com` |
| `MODEL` | `deepseek-v4-flash` |
| `EMAIL_TO` | Recipient email |
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | SMTP login |
| `SMTP_PASSWORD` | Gmail app password |
| `SMTP_FROM` | optional |

No extra tokens are required for PKS or WikiCFP scraping.

## Manual runs

- **PKS:** Actions → *PKS Weekly Digest* → Run workflow
- **Conferences:** Actions → *Conference Deadlines Monthly* → Run workflow (enable **force** to test any day)

## Schedules

| Workflow | Cron (UTC) | Meaning |
|----------|------------|---------|
| PKS Weekly | `0 7 * * 0` | Every Sunday 07:00 |
| Conferences | `30 7 22-31 * 0` | Last Sunday of month (~07:30) |
