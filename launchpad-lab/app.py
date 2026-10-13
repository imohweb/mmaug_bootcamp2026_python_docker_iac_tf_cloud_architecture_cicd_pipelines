import os

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)


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


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
