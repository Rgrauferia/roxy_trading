# Home223 — liveness independent of provider workers

Render Events records an HTTP health check timeout (5s) and recovery at12:54;
Logs records further server starts/restarts around13:00/13:01. Browser requests
failed while direct provider calls and the OpenAI client/context/ledger initialize.
This does not establish OOM, a bad API key, or the exact blocking request.

The constant /health liveness response now runs asynchronously, without taking
a shared blocking-worker token. A regression saturates that pool and still
receives the response within1s. This is liveness only, not provider readiness.
OpenAI's client now has an explicit30s transport timeout and zero SDK retries.
Timeout accounting remains pending for review; no refund/reset or hidden retry.
No compute upgrade, billing change, provider replacement or permission change.

Verification:225 Python tests (including the saturated-pool regression and
durable timeout accounting),345 Node tests, syntax/diff checks passed.
HTML/APP223, JS231, SW223; other asset versions unchanged. Production must be
verified after deployment; successful liveness is not proof of a working chat.
