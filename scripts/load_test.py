#!/usr/bin/env python3
"""Simulate N concurrent participants hitting a running MetaLoop app.

Two modes:
  ping     -- each virtual user makes one cheap, no-LLM call through the
              Gradio queue (repeated --requests times each, if you want).
              Use this first to check the server/queue can even accept N
              concurrent connections, with zero OpenAI cost.
  oneshot  -- each virtual user runs the REAL one-shot path (save a throw-
              away profile, submit a blank pre-quiz, then generate) with a
              minimal one-concept prompt. This calls the OpenAI API for
              real and spends tokens on your key -- pass --real to confirm
              you mean it.

Run this against the app while it's already running (`python app.py` in
another terminal), pointing --url at wherever it's listening.

Usage:
    python scripts/load_test.py --users 30 --mode ping
    python scripts/load_test.py --users 30 --mode oneshot --real
"""
from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from gradio_client import Client

DEFAULT_URL = "http://localhost:7860"

# Deliberately tiny -- "one concept" per the ask -- to keep real-mode token
# usage (and cost) as small as possible.
ONE_CONCEPT_PROMPT = "A system with exactly one concept: a Widget, which has a name and a price."

# The BP pre-quiz has 6 questions; leaving every one unanswered is fine --
# run_oneshot only checks that pre_responses exists on the profile, not
# that it's fully or correctly answered.
BP_PRE_BLANK_ANSWERS = [[] for _ in range(6)]


def _run_ping(user_id: int, url: str) -> tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        client = Client(url, verbose=False)
        client.predict(api_name="/_show_profile_page")
        return True, time.perf_counter() - start, ""
    except Exception as exc:
        return False, time.perf_counter() - start, str(exc)


def _run_oneshot(user_id: int, url: str) -> tuple[bool, float, str]:
    start = time.perf_counter()
    name = f"loadtest_{user_id}_{int(start)}"
    try:
        # Each Client keeps its own session_hash for the life of the
        # object, so the gr.State values (user_name, domain) set by
        # _save_user_name below are exactly what run_oneshot reads after
        # -- same as one browser tab acting as one participant.
        client = Client(url, verbose=False)
        client.predict(name, "bp", True, api_name="/_save_user_name")
        client.predict(name, *BP_PRE_BLANK_ANSWERS, api_name="/handler")
        client.predict(ONE_CONCEPT_PROMPT, None, api_name="/run_oneshot")
        return True, time.perf_counter() - start, ""
    except Exception as exc:
        return False, time.perf_counter() - start, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--users", type=int, default=30, help="Concurrent virtual users (default: 30)")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"App URL (default: {DEFAULT_URL})")
    parser.add_argument(
        "--mode", choices=["ping", "oneshot"], default="ping",
        help="'ping' (default): cheap, no-LLM concurrency check. "
             "'oneshot': real one-concept generation -- costs tokens.",
    )
    parser.add_argument(
        "--real", action="store_true",
        help="Required with --mode oneshot, to confirm you want to spend real OpenAI tokens.",
    )
    args = parser.parse_args()

    if args.mode == "oneshot" and not args.real:
        parser.error("--mode oneshot calls the real OpenAI API and costs tokens -- pass --real to confirm.")

    worker = _run_ping if args.mode == "ping" else _run_oneshot
    print(f"Simulating {args.users} concurrent users against {args.url} in '{args.mode}' mode...\n")

    results: list[tuple[bool, float]] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.users) as pool:
        futures = {pool.submit(worker, i, args.url): i for i in range(args.users)}
        for future in as_completed(futures):
            i = futures[future]
            ok, elapsed, err = future.result()
            results.append((ok, elapsed))
            status = "OK" if ok else "FAIL"
            line = f"  user {i:>2} [{status}] {elapsed:6.2f}s"
            if err:
                line += f"  -- {err[:120]}"
            print(line)

    total_wall = time.perf_counter() - started
    successes = [e for ok, e in results if ok]
    failures = [e for ok, e in results if not ok]

    print("\n--- Summary ---")
    print(f"Total users:       {len(results)}")
    print(f"Succeeded:         {len(successes)}")
    print(f"Failed:            {len(failures)}")
    print(f"Total wall time:   {total_wall:.2f}s (all {args.users} users started together)")
    if successes:
        print(
            f"Latency (success): min={min(successes):.2f}s  "
            f"median={statistics.median(successes):.2f}s  "
            f"mean={statistics.mean(successes):.2f}s  max={max(successes):.2f}s"
        )
    if failures:
        print(f"Latency (failure): min={min(failures):.2f}s  max={max(failures):.2f}s")
    if not successes and failures:
        print("\nAll requests failed -- check the app is running at --url and, for "
              "--mode oneshot, that OPENAI_API_KEY is set in its environment.")


if __name__ == "__main__":
    main()
