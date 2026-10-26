from fastapi import FastAPI

app = FastAPI(title="Marketing Brain")


@app.get("/health")
def health():
    return {"status": "ok"}