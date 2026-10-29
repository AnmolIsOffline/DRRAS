# GitHub and Render deployment

## Before pushing to GitHub

The repository ignore rules intentionally exclude local SQLite databases, virtual environments, generated credential references, account inventory exports, and ZIP archives. Review `git status` before the first push and make sure no `.env`, real personal data, or credentials are staged.

Create a private GitHub repository if the project or its demo account details should not be public. From the project directory:

```powershell
git init
git add .
git status --short
git commit -m "Prepare DRRAS for Render deployment"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repository>.git
git push -u origin main
```

Replace the repository URL with the one GitHub gives you. If this project already has Git history in another location, connect/push that repository instead of initializing a second history.

## Render setup

The included `render.yaml` configures a Python **Web Service**, installs dependencies, seeds the demonstration database during the build, serves Flask through Gunicorn, generates a Render-managed `SECRET_KEY`, and checks `/healthz`.

1. Push the project to GitHub.
2. In Render, choose **New → Blueprint**, connect the repository, and apply `render.yaml`.
3. Wait for the build and deploy to finish, then open the service's `onrender.com` URL. `/healthz` should return `{"status":"ok"}`.

Render's free web service uses an ephemeral filesystem. The seed database is packaged into each build so the demo starts populated, but activity written to SQLite while the service is running can be lost when the free service spins down, restarts, or redeploys. Free web services cannot attach persistent disks. For data that must survive restarts, use a paid web service with a persistent disk mounted at `/var/data` and set `DRRAS_DB_PATH=/var/data/drras.db`; seed that disk after it is mounted. Alternatively, migrate the database layer to PostgreSQL before connecting a managed PostgreSQL service—this code currently uses Python's SQLite driver and does not consume `DATABASE_URL`.

The default Blueprint is intended for a classroom/demo preview, not sensitive or production emergency operations. Do not enter real citizen personal data or use the seeded demonstration passwords for real accounts. For a public-facing production system, use durable managed storage, review the demo seed policy, configure backups, and perform an authorization/security review.

## Local commands

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed_demo.py
python -m pytest -q
python app.py
```

On Render, the equivalent build command is `pip install -r requirements.txt && python seed_demo.py`; the start command is `gunicorn --bind 0.0.0.0:$PORT --worker-class gthread --workers 1 --threads 8 --timeout 120 app:app`.
