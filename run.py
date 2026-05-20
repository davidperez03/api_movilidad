import os
import sys
import uvicorn

if __name__ == "__main__":
    env = os.getenv("APP_ENV", "development")
    if env == "production":
        print("ERROR: No uses run.py en producción. Usa el Dockerfile con gunicorn.", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(
        "app.main:app",
        app_dir="src",
        reload=True,
        host="127.0.0.1",
        port=8000,
    )
