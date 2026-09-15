# InternMate FastAPI backend

The FastAPI runtime preserves the existing InternMate SQLite data and exposes the
REST paths consumed by the React client. Start it from the project root:

```powershell
.\.venv-win\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

The interactive API documentation is available at `/docs`.
