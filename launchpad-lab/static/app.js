const result = document.querySelector("#result");
document.querySelector("#summary-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = document.querySelector("#values").value;
  try {
    const response = await fetch(`/sum?${new URLSearchParams({ values })}`);
    const payload = await response.json();
    result.textContent = response.ok
      ? JSON.stringify(payload, null, 2)
      : `HTTP ${response.status}: ${payload.error}`;
  } catch (error) {
    result.textContent = `Request failed: ${error.message}`;
  }
});

async function loadGreeting() {
  const element = document.querySelector("#greeting");
  try {
    const response = await fetch("/");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    element.textContent = payload.message;
  } catch (error) {
    element.textContent = `Greeting unavailable: ${error.message}`;
  }
}
loadGreeting();
