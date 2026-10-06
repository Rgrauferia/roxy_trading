import threading

import anyio
import httpx

from tools.roxy_home_service import app


def test_liveness_does_not_wait_for_saturated_provider_thread_pool():
    async def scenario():
        limiter = anyio.to_thread.current_default_thread_limiter()
        original_tokens = limiter.total_tokens
        limiter.total_tokens = 1
        release = threading.Event()
        started = anyio.Event()

        def provider_work():
            anyio.from_thread.run_sync(started.set)
            release.wait(3)

        try:
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(anyio.to_thread.run_sync, provider_work)
                await started.wait()
                try:
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        with anyio.fail_after(1):
                            response = await client.get("/health")
                    assert response.status_code == 200
                    assert response.json()["service"] == "roxy-home"
                finally:
                    release.set()
        finally:
            release.set()
            limiter.total_tokens = original_tokens

    anyio.run(scenario)
