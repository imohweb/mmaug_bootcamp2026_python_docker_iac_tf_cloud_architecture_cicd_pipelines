import os
import secrets
from pathlib import Path

from azure.core.exceptions import AzureError
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAIError

from ai_demo import ask_agent, ask_model


load_dotenv(Path(__file__).with_name(".env-local"), override=False)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def summarize(values: list[int]) -> dict[str, int | float]:
    if len(values) != 3:
        raise ValueError("Provide exactly three integers.")
    total = sum(values)
    return {"total": total, "average": total / len(values)}


@app.get("/")
def greeting():
    return jsonify(message=os.getenv("APP_MESSAGE", "Hello, MMAUG!"))


@app.get("/ui")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/sum")
def summary():
    raw = request.args.getlist("values")
    try:
        if len(raw) != 1:
            raise ValueError("Use one values parameter with three integers.")
        if len(raw[0]) > 120:
            raise ValueError("Keep values within 120 characters.")
        values = [int(item) for item in raw[0].split(",")]
        result = summarize(values)
    except ValueError as error:
        app.logger.warning("Invalid /sum request: %s", error)
        return jsonify(error=str(error)), 400
    return jsonify(result)


@app.errorhandler(404)
def not_found(_error):
    return jsonify(error="Route not found."), 404


@app.post("/ai/<mode>")
def ai_reply(mode: str):
    if mode not in ("model", "agent"):
        app.logger.warning("Unknown AI demo mode.")
        return jsonify(error="Choose model or agent."), 404
    token = os.getenv("AI_DEMO_API_TOKEN", "")
    if len(token) < 32 or token.startswith("REPLACE-"):
        app.logger.warning("AI demo is disabled: configure a random AI_DEMO_API_TOKEN.")
        return jsonify(error="AI demo is not configured."), 503
    if not secrets.compare_digest(
        request.headers.get("Authorization", "").encode(), f"Bearer {token}".encode()
    ):
        app.logger.warning("Unauthorized AI demo request.")
        return jsonify(error="A valid demo bearer token is required."), 401
    payload = request.get_json(silent=True)
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
        app.logger.warning("Invalid AI prompt.")
        return jsonify(error="Provide a JSON prompt of 1-2000 characters."), 400
    try:
        text = ask_model(prompt.strip()) if mode == "model" else ask_agent(prompt.strip())
    except ValueError as error:
        app.logger.warning("AI configuration error: %s", error)
        return jsonify(error="AI configuration is incomplete; check server logs."), 503
    except (AzureError, OpenAIError, RuntimeError):
        app.logger.exception("AI service request failed.")
        return jsonify(error="AI request failed; check server logs and Azure permissions."), 502
    return jsonify(mode=mode, answer=text)


@app.errorhandler(413)
def too_large(_error):
    app.logger.warning("Request exceeded the 16 KiB limit.")
    return jsonify(error="Request body must not exceed 16 KiB."), 413


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
