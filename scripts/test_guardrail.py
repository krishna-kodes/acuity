#!/usr/bin/env python3
"""Manual guardrail smoke-test CLI.

Usage:
    python scripts/test_guardrail.py "Your question here"
    python scripts/test_guardrail.py "What are the main features?" --project-id 3
    python scripts/test_guardrail.py "Explain microservices" --project-id 3 --base-url http://localhost:8000
"""
import argparse
import json

import httpx

THRESHOLD = 0.70  # mirrors GROUNDEDNESS_THRESHOLD default


def parse_sse_stream(response: httpx.Response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def run(question: str, project_id: int, base_url: str) -> None:
    sep = "━" * 44
    print(f"\n{sep}")
    print(f"Query  : {question!r}")
    print(f"Project: {project_id}  |  URL: {base_url}")
    print(f"{sep}\n")

    url = f"{base_url}/api/v1/projects/{project_id}/chat"
    payload = {"message": question, "proceed": False}

    # Layer 1 — domain classifier (detected via HTTP status)
    print("[LAYER 1] Domain Classifier")
    try:
        with httpx.Client(timeout=60) as client:
            with client.stream("POST", url, json=payload) as resp:
                if resp.status_code == 400:
                    body = json.loads(resp.read())
                    print(f"  ✗ BLOCKED (HTTP 400)")
                    print(f"  Detail: {body.get('detail', '')}")
                    print("\n[LAYER 2] Retrieval Gate      ← skipped (blocked at Layer 1)")
                    print("[LAYER 3] Groundedness        ← skipped (blocked at Layer 1)")
                    return
                elif resp.status_code != 200:
                    print(f"  ✗ Unexpected HTTP {resp.status_code}")
                    return

                print("  ✓ PASS")
                events = parse_sse_stream(resp)

    except httpx.ConnectError:
        print(f"  ✗ Cannot connect to {base_url}. Is the server running?")
        return
    except httpx.ReadTimeout:
        print("  ✗ Request timed out (LLM may be slow — try again)")
        return

    # Layer 2 — retrieval gate (detected via gate_blocked SSE event)
    print("\n[LAYER 2] Retrieval Gate")
    gate_event = next((e for e in events if e.get("type") == "gate_blocked"), None)
    if gate_event:
        print(f"  ✗ GATE BLOCKED  (status: {gate_event.get('status')})")
        print(f"  Message: {gate_event.get('message', '')!r}")
        print("\n[LAYER 3] Groundedness        ← skipped (blocked at Layer 2)")
        return
    print("  ✓ PASS")

    # Layer 3 — groundedness judge (detected via groundedness SSE event)
    print("\n[LAYER 3] Groundedness")
    gnd = next((e for e in events if e.get("type") == "groundedness"), None)
    warn = next((e for e in events if e.get("type") == "groundedness_warning"), None)
    if gnd:
        score = gnd.get("score", 0)
        status = "✗ FLAGGED" if gnd.get("flagged") else "✓ above threshold"
        print(f"  Score  : {score:.2f}  {status} (threshold: {THRESHOLD:.2f})")
        if warn:
            claims = warn.get("unsupported_claims", [])
            print(f"  Warning: {len(claims)} unsupported claim(s)")
            for c in claims:
                print(f"    • {c}")
        else:
            print("  Warning: none")
    else:
        print("  (disabled or score not returned — set GROUNDEDNESS_CHECK_ENABLED=true)")

    # Response text
    tokens = [e.get("content", "") for e in events if e.get("type") == "token"]
    response_text = "".join(tokens).strip()
    if response_text:
        lines = response_text.splitlines()
        print(f"\nResponse:")
        for line in lines[:12]:
            print(f"  {line}")
        if len(lines) > 12:
            print(f"  ... ({len(lines)} lines total)")
    else:
        error_event = next((e for e in events if e.get("type") == "error"), None)
        if error_event:
            print(f"\n✗ Stream error: {error_event.get('content', '')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smoke-test the guardrail pipeline with a single query.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python scripts/test_guardrail.py "How do I make pasta?"
  python scripts/test_guardrail.py "What are the main features?" --project-id 3
  python scripts/test_guardrail.py "Explain microservices in general" --project-id 3
        """,
    )
    parser.add_argument("question", help="Question to send to the chat endpoint")
    parser.add_argument(
        "--project-id", type=int, default=1, metavar="N",
        help="Project ID — must have an uploaded document for Layer 2/3 (default: 1)",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    run(args.question, args.project_id, args.base_url)
