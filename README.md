# SMAI Backend

A scalable FastAPI starter focused on:

- strict typing
- versioned API routing
- centralized settings
- explicit error handling
- testable app factory pattern

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Run With Docker

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.
Source changes under `app/` will reload automatically inside the running container.

To stop it:

```bash
docker compose down
```

## Endpoints

- `GET /health`
- `GET /docs`
