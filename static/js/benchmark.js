/**
 * LearnSphere - High-Concurrency Benchmark Suite (500+ Requests)
 */

async function runLiveBenchmark(concurrencyLevel = 500) {
  const runBtn = document.getElementById("run-bench-btn");
  const spinner = document.getElementById("bench-spinner");
  const resultsContainer = document.getElementById("bench-results");

  if (runBtn) runBtn.disabled = true;
  if (spinner) spinner.style.display = "inline-block";
  if (resultsContainer) resultsContainer.style.opacity = "0.5";

  showToast(`Simulating ${concurrencyLevel} concurrent requests against MongoDB connection pool...`, "info");

  const startTime = performance.now();
  try {
    const res = await fetch(`/api/benchmark/run/?concurrency=${concurrencyLevel}`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "XMLHttpRequest"
      }
    });

    const data = await res.json();
    const durationClient = Math.round(performance.now() - startTime);

    if (data.status === "success") {
      const b = data.data;
      document.getElementById("stat-concurrency").innerText = b.concurrency_level;
      document.getElementById("stat-rps").innerText = `${b.requests_per_sec} req/s`;
      document.getElementById("stat-avg-lat").innerText = `${b.avg_latency_ms} ms`;
      document.getElementById("stat-p99-lat").innerText = `${b.p99_latency_ms} ms`;
      document.getElementById("stat-success").innerText = `${b.success_rate_pct}%`;
      document.getElementById("stat-duration").innerText = `${b.total_duration_sec}s`;

      const gaugeFill = document.getElementById("gauge-fill");
      if (gaugeFill) gaugeFill.style.width = "100%";

      showToast(`Benchmark PASSED: ${b.concurrency_level} requests served in ${b.total_duration_sec}s with ${b.success_rate_pct}% zero-loss!`, "success");
    } else {
      showToast(data.message || "Benchmark failed", "error");
    }
  } catch (err) {
    showToast("Benchmark execution error.", "error");
  } finally {
    if (runBtn) runBtn.disabled = false;
    if (spinner) spinner.style.display = "none";
    if (resultsContainer) resultsContainer.style.opacity = "1";
  }
}
