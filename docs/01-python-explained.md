# Python: every Python file explained

The foundation uses `app.py` and `test_app.py` in `launchpad-lab`. The optional
[AI demo](06-foundry-demo.md) adds `ai_demo.py` (SDK calls), `manage_agent.py`
(Terraform's agent lifecycle bridge), and `test_ai.py` (offline mocked SDK,
access-guard and lifecycle tests). Presentation-generation scripts are private
presenter tooling, not participant application code.

## Before the web app: beginner building blocks

In an activated Python environment, type `python` for the REPL:

```python
count = 5
text = "5"
print(type(count).__name__)  # int
print(text * 2)             # 55 as text
print(int(text) * 2)        # 10 as a number
values = [5, 10, 15]
result = {"total": sum(values), "average": sum(values) / len(values)}
print(result)
```

Names reference values. `int`, `float`, `str`, `bool` are common scalar types.
Lists preserve order and duplicates; tuples are fixed sequences; dictionaries
associate keys and values; sets represent uniqueness. `/` divides, `//` floors,
`%` returns a remainder, `**` exponentiates. `==` compares, while `=` assigns.
`and`, `or`, `not` combine or invert conditions.

```python
for value in values:
    print(value)
attempts = 0
while attempts < 3:
    print(attempts)
    attempts += 1
print(list(range(3)))  # [0, 1, 2]; stop is excluded
```

`for` traverses a sequence. `while` repeats based on a condition; update that
condition. Indentation defines blocks. A nested loop runs its inner work for
each outer item. `break` exits only the **innermost** loop; `continue` skips the
rest of that iteration. Use readable names rather than clever compression.

```python
from app import summarize
raw = input("Enter three space-separated integers: ")
values = [int(item) for item in raw.split()]
print(summarize(values))
with open("app.py", encoding="utf-8") as source:
    print(source.readline().strip())
```

`input` returns text. `split()` separates whitespace, and the comprehension
converts each item. `with` closes a file even when its block fails. Explicit
encoding avoids platform assumptions. An invalid conversion raises `ValueError`;
do not convert failure into a fake successful zero result.

## app.py, in source order

### Imports and application object

- `import os`: reads process environment variables, not shell commands.
- `Flask`: constructs the web application.
- `jsonify`: serializes data as JSON and sets its response content type.
- `render_template`: loads HTML from the `templates` directory.
- `request`: accesses the current HTTP request through Flask's request context.
- `app = Flask(__name__)`: creates the WSGI application, using the module identity
  to find template/static resources. This `app` is exported for Gunicorn.
- `load_dotenv`: loads the adjacent ignored `.env-local` without overriding
  process settings. AI clients are instantiated only when a protected AI route
  is invoked; ordinary local requests require no Azure credentials.
- `secrets.compare_digest`: compares the private demo bearer token. AI requests
  require valid JSON, bounded prompts and a configured token. See the AI guide
  for the complete request and error contract.

### summarize(values)

`def` defines a reusable function; the body runs when it is called.
`values: list[int]` and `-> dict[str, int | float]` are type hints, not automatic
runtime input validation. `len(values) != 3` rejects the wrong count by raising
`ValueError`. `sum(values)` computes the total. Division by the validated count
gives the average. `return` hands a dictionary to the caller without printing
or sending an HTTP response. That separation makes direct unit tests possible.

### greeting(), home(), and health()

- `@app.get("/")`: a decorator registering `greeting` for GET `/`. The function
  reads `APP_MESSAGE`; an absent variable uses `"Hello, MMAUG!"`. This is an
  intentional public greeting default, not a silent exception fallback.
  `jsonify(message=...)` returns a JSON object with the `message` key.
- `@app.get("/ui")`: registers `home`. `render_template("index.html")` renders
  the browser page. Jinja generates static-resource URLs in that template.
- `@app.get("/health")`: registers `health`. Returning `jsonify(status="ok")`
  checks this process can respond; it does not test every external dependency.

### summary(): HTTP text becomes validated application data

1. The `/sum` decorator registers this handler.
2. `request.args.getlist("values")` retrieves all occurrences of the parameter.
   We use a list so duplicate `values` parameters are not silently accepted.
3. `try` encloses the expected conversion and validation work.
4. `len(raw) != 1` rejects missing or repeated parameters.
5. `len(raw[0]) > 120` bounds this beginner endpoint's input size before parsing.
6. `raw[0].split(",")` separates the three textual fields.
7. `[int(item) for item in ...]` converts each field; non-integer text fails.
8. `summarize(values)` rejects a count other than three and computes the result.
9. `except ValueError as error` catches this known input failure specifically.
10. `app.logger.warning(...)` records failure visibly. This demo does not collect
    credentials or confidential user input.
11. `return jsonify(error=str(error)), 400` returns a JSON error **and** HTTP 400.
12. On success, `jsonify(result)` returns HTTP 200 and labeled numeric values.

Invalid input, negative values and zero are different concepts: negative
integers and zero are accepted. Strings such as `"nope"` and missing values are
invalid. JSON field order is not significant.

### not_found(_error)

`@app.errorhandler(404)` registers the not-found response. Flask passes an error
object; `_error` signals we do not need its details. The result is explicit JSON
and HTTP 404, preserving a consistent API format.

### main() and the entry-point guard

`os.getenv("PORT", "8000")` reads optional configuration. `int` converts it;
invalid text raises visibly. The range check rejects invalid network ports.
`app.run(host="127.0.0.1", port=port, debug=False)` starts a **local development**
server bound to localhost, with debug mode disabled.
`if __name__ == "__main__": main()` runs that function only when the file is
executed directly. Importing `app` from tests or Gunicorn does not start a second
development server.

The Docker command `gunicorn ... app:app` imports module `app`, finds its Flask
object `app`, and serves it with two worker processes on `0.0.0.0:8000`.
Gunicorn, rather than `main()`, owns container listening and shutdown.

## test_app.py, in source order

### Imports

`json` decodes responses; `os` provides environment mappings; `threading` lets a
server run concurrently with the tests; `unittest` supplies the runner,
assertions and lifecycle hooks; `patch` temporarily changes environment values
and restores them; `HTTPError` represents HTTP error responses; `urlopen`
performs real requests; Werkzeug's `make_server` creates a local WSGI server;
`from app import app, main, summarize` imports the same production application
and logic instead of duplicating them.

### SummaryTests(unittest.TestCase)

Inheritance gives the class assertions and unittest discovery.

- `test_total_and_average`: proves `[5, 10, 15]` yields total 30 and average 10.0.
- `test_negative_and_zero`: proves `[-3, 0, 3]` is valid and yields zero.
- `test_wrong_count`: a `for` loop tests empty, one, two and four values.
  `subTest` reports which input failed; `assertRaises` requires `ValueError`.
- `test_invalid_port`: temporarily sets PORT to `"abc"`, `"0"` and `"65536"`;
  `main()` must raise before starting a server. `patch.dict` restores values
  automatically, so tests do not pollute the environment.

### HttpTests(unittest.TestCase)

- `@classmethod setUpClass`: receives `cls`, not a per-test `self`. It starts one
  real threaded Werkzeug server on `127.0.0.1`, port **0** so the OS selects an
  available port. A thread runs `serve_forever`. The assigned `server_port`
  constructs `base_url`, avoiding dependence on the classroom port 8000.
- `@classmethod tearDownClass`: stops serving, closes the socket and joins the
  thread. Tests should not leak processes or ports.
- `request(self, path)`: performs `urlopen` with a three-second timeout.
  `HTTPError` also contains a response; keeping it lets us inspect expected 400
  and 404 responses. This is not suppressing a failure: tests explicitly assert
  the status. `with response` closes it; the helper checks JSON content type and
  returns `(status, decoded_dictionary)`.
- `test_health`: checks both status 200 and `{"status": "ok"}`.
- `test_configured_message`: patches APP_MESSAGE and checks the `/` payload.
- `test_valid_sum`: verifies numeric total and average over actual HTTP.
- `test_bad_input`: uses subtests for missing, empty, non-numeric, short, long
  and duplicate parameters, requiring status 400 and an `error` field.
- `test_missing_route`: checks explicit 404 JSON.
- `test_home_page`: checks `/ui` gives HTML and contains the page title.
- `test_oversized_input`: proves the 120-character bound produces HTTP 400.
- The final `__main__` guard runs `unittest.main()` when this test file is
  executed directly. `python -m unittest -v` discovers the same methods.

## Browser files are not Python

`templates/index.html` defines the accessible form and result area.
`static/style.css` supplies responsive styling.
`static/app.js` intercepts submission, safely URL-encodes values, calls `/sum`,
checks HTTP status and writes `textContent` instead of injecting HTML.
It separately loads the greeting and explicitly displays network failures.
Flask serves those files; the JavaScript runs in the participant's browser.

## What this example does not claim

No user authentication, durable data, abuse protection or complete production
observability is implemented. Gunicorn provides an appropriate WSGI process
boundary, but a production server alone does not make the system production-ready.

References: [Python tutorial](https://docs.python.org/3/tutorial/),
[Flask quickstart](https://flask.palletsprojects.com/en/stable/quickstart/),
[Gunicorn documentation](https://docs.gunicorn.org/en/stable/).
