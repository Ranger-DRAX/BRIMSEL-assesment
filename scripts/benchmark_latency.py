#!/usr/bin/env python3
"""Configurable latency benchmark for Little English Buddy.

Measures full submit-to-checked-response latency through the HTTP API.
Baseline: 5 concurrent sessions, 100 total turns, warm backend, compact context.

Reports:
- p50, p95, p99 complete-response latency
- Error rate
- Fallback rate
- Provider success rate

Usage:
    python scripts/benchmark_latency.py [--concurrency 5] [--turns 100] [--url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx


async def run_session(
    base_url: str,
    session_idx: int,
    turns_per_session: int,
    results: list[dict],
):
    """Execute turns for a single independent session."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # 1. Initialize session
        create_resp = await client.post(
            "/api/session",
            json={"nickname": f"Kid_{session_idx}", "starting_level": "L1"},
        )
        if create_resp.status_code != 200:
            print(f"[Session {session_idx}] Failed to create session: {create_resp.status_code}")
            return

        revision = 0
        sample_messages = [
            "Hello!",
            "I like cats",
            "What color is the sky?",
            "Can we play a game?",
            "Tell me a story",
            "I want to learn colors",
            "Thank you Pip",
            "What is your name?",
            "I have two red shoes",
            "Goodbye for now!",
        ]

        for turn_idx in range(turns_per_session):
            req_id = str(uuid.uuid4())
            msg = sample_messages[turn_idx % len(sample_messages)]

            start = time.monotonic()
            try:
                resp = await client.post(
                    "/api/chat",
                    json={
                        "request_id": req_id,
                        "expected_revision": revision,
                        "message": msg,
                    },
                )
                duration_ms = (time.monotonic() - start) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    revision = data.get("revision", revision + 1)
                    results.append({
                        "duration_ms": duration_ms,
                        "status": 200,
                        "source": data.get("source", "unknown"),
                        "is_fallback": data.get("source") == "fallback",
                    })
                else:
                    results.append({
                        "duration_ms": duration_ms,
                        "status": resp.status_code,
                        "source": "error",
                        "is_fallback": False,
                    })

            except Exception as e:
                duration_ms = (time.monotonic() - start) * 1000
                results.append({
                    "duration_ms": duration_ms,
                    "status": 0,
                    "error": str(e),
                    "source": "exception",
                    "is_fallback": False,
                })

            # Polite pacing between turns in the same session
            await asyncio.sleep(0.05)


async def main():
    parser = argparse.ArgumentParser(description="Little English Buddy Latency Benchmark")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent sessions")
    parser.add_argument("--turns", type=int, default=100, help="Total turns across all sessions")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    print("=" * 65)
    print("🚀 LITTLE ENGLISH BUDDY LATENCY BENCHMARK")
    print(f"Target URL:    {args.url}")
    print(f"Concurrency:   {args.concurrency} concurrent sessions")
    print(f"Total Turns:   {args.turns}")
    print("=" * 65)

    # Health check
    async with httpx.AsyncClient(base_url=args.url) as client:
        try:
            h = await client.get("/health")
            if h.status_code != 200:
                print(f"❌ Backend not healthy at {args.url}: HTTP {h.status_code}")
                return 1
        except Exception as e:
            print(f"❌ Cannot connect to {args.url}: {e}")
            print("Make sure the backend is running with: uvicorn app.main:app --port 8000")
            return 1

    turns_per_session = max(1, args.turns // args.concurrency)
    results: list[dict] = []

    start_bench = time.monotonic()
    tasks = [
        run_session(args.url, i + 1, turns_per_session, results)
        for i in range(args.concurrency)
    ]
    await asyncio.gather(*tasks)
    total_time = time.monotonic() - start_bench

    # Analysis
    if not results:
        print("No results recorded.")
        return 1

    durations = [r["duration_ms"] for r in results if r["status"] == 200]
    durations.sort()

    errors = [r for r in results if r["status"] != 200]
    fallbacks = [r for r in results if r.get("is_fallback")]

    p50 = durations[len(durations) // 2] if durations else 0
    p95_idx = int(len(durations) * 0.95)
    p95 = durations[p95_idx] if durations else 0
    p99_idx = int(len(durations) * 0.99)
    p99 = durations[p99_idx] if durations else 0

    error_rate = len(errors) / len(results) * 100
    fallback_rate = len(fallbacks) / len(results) * 100

    print("\n" + "=" * 65)
    print("BENCHMARK RESULTS")
    print("=" * 65)
    print(f"Total Requests:     {len(results)}")
    print(f"Total Wall Time:    {total_time:.2f} s")
    print(f"Throughput:         {len(results) / total_time:.1f} turns/sec")
    print("-" * 65)
    print(f"Latency p50:        {p50:.1f} ms")
    print(f"Latency p95:        {p95:.1f} ms")
    print(f"Latency p99:        {p99:.1f} ms")
    print(f"Error Rate:         {error_rate:.1f}% ({len(errors)}/{len(results)})")
    print(f"Fallback Rate:      {fallback_rate:.1f}% ({len(fallbacks)}/{len(results)})")
    print("-" * 65)

    # Evaluation against specification target: p95 <= 2000ms & fallback <= 5%
    if p95 <= 2000 and fallback_rate <= 5.0 and error_rate == 0:
        print("✔ TARGET MET: p95 <= 2000ms and fallback rate <= 5%")
    else:
        print(f"ℹ TARGET STATUS: p95={p95:.1f}ms (target <=2000ms), fallback={fallback_rate:.1f}% (target <=5%)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
