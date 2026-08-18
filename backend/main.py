from fastapi import FastAPI, HTTPException, Query, Response
import asyncio

app = FastAPI(
    title="Job Ingestion Pipeline",
    description=(
        "Acdyon Technologies — Part 1: End-to-end job data ingestion "
        "from public sources with resilience, retry, and circuit breaking."
    ),
    version="1.0.0",
)


@app.get("/", tags=["status"])
async def root():
    """Basic liveness check — confirms the application process is running."""
    return {"status": "ok", "message": "Job Ingestion Pipeline is running"}


# --- Sandbox Feed XML Templates ---

HAPPY_PATH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sandbox Feed - Happy Path</title>
    <link>http://127.0.0.1:8000/sandbox/jobs</link>
    <description>Simulated happy path jobs</description>
    <item>
      <title>Sandbox Software Engineer</title>
      <link>http://example.com/sandbox/job/1</link>
      <author>Sandbox Industries</author>
      <category>Software Development</category>
      <pubDate>Tue, 18 Aug 2026 12:00:00 +0000</pubDate>
      <description>Build elegant software in our simulated sandbox.</description>
    </item>
    <item>
      <title>Sandbox DevOps Wizard</title>
      <link>http://example.com/sandbox/job/2</link>
      <author>Cloud Labs</author>
      <category>DevOps</category>
      <pubDate>Tue, 18 Aug 2026 12:05:00 +0000</pubDate>
      <description>Keep the simulated containers running smoothly.</description>
    </item>
  </channel>
</rss>
"""

EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sandbox Feed - Empty</title>
    <link>http://127.0.0.1:8000/sandbox/jobs</link>
    <description>Simulated empty channel</description>
  </channel>
</rss>
"""

MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sandbox Feed - Malformed</title>
    <link>http://127.0.0.1:8000/sandbox/jobs</link>
    <description>Simulated malformed content</description>
    <!-- Record 1: Valid -->
    <item>
      <title>Sandbox Analyst</title>
      <link>http://example.com/sandbox/job/valid</link>
      <author>Data Corp</author>
      <category>Analytics</category>
      <pubDate>Tue, 18 Aug 2026 12:00:00 +0000</pubDate>
      <description>Valid analyst position</description>
    </item>
    <!-- Record 2: Invalid (missing both title and link) -->
    <item>
      <author>Broken Corp</author>
      <category>Broken</category>
      <pubDate>Tue, 18 Aug 2026 12:01:00 +0000</pubDate>
      <description>Missing title and link fields completely</description>
    </item>
    <!-- Record 3: Valid -->
    <item>
      <title>Sandbox Designer</title>
      <link>http://example.com/sandbox/job/designer</link>
      <author>Pixel Art</author>
      <category>Design</category>
      <pubDate>Tue, 18 Aug 2026 12:02:00 +0000</pubDate>
      <description>Valid designer position</description>
    </item>
  </channel>
</rss>
"""

DUPLICATES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sandbox Feed - Duplicates</title>
    <link>http://127.0.0.1:8000/sandbox/jobs</link>
    <description>Simulated duplicates</description>
    <!-- Job A (First occurrence) -->
    <item>
      <title>Unique Sandbox Lead</title>
      <link>http://example.com/sandbox/job/lead</link>
      <author>Tech Inc</author>
      <category>Management</category>
      <pubDate>Tue, 18 Aug 2026 12:00:00 +0000</pubDate>
      <description>Lead dev role</description>
    </item>
    <!-- Job A (Duplicate occurrence inside the same batch) -->
    <item>
      <title>Unique Sandbox Lead</title>
      <link>http://example.com/sandbox/job/lead</link>
      <author>Tech Inc</author>
      <category>Management</category>
      <pubDate>Tue, 18 Aug 2026 12:00:00 +0000</pubDate>
      <description>Duplicate description</description>
    </item>
  </channel>
</rss>
"""


@app.get("/sandbox/jobs")
async def sandbox_jobs(scenario: str = Query(..., description="The simulation scenario to run")):
    allowed_scenarios = {
        "happy_path",
        "rate_limit",
        "server_error",
        "timeout",
        "empty",
        "malformed",
        "schema_changed",
        "duplicates",
    }
    if scenario not in allowed_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario '{scenario}'. Allowed: {sorted(allowed_scenarios)}",
        )

    if scenario == "happy_path" or scenario == "schema_changed":
        # schema_changed returns valid XML; the parser throws the exception
        return Response(content=HAPPY_PATH_XML, media_type="application/xml")

    elif scenario == "empty":
        return Response(content=EMPTY_XML, media_type="application/xml")

    elif scenario == "malformed":
        return Response(content=MALFORMED_XML, media_type="application/xml")

    elif scenario == "duplicates":
        return Response(content=DUPLICATES_XML, media_type="application/xml")

    elif scenario == "rate_limit":
        # Returns 429 Too Many Requests with Retry-After header
        return Response(
            content="Rate Limit Exceeded (Simulated)",
            status_code=429,
            headers={"Retry-After": "1"},
        )

    elif scenario == "server_error":
        # Returns 500 Internal Server Error
        return Response(content="Internal Server Error (Simulated)", status_code=500)

    elif scenario == "timeout":
        # Delays the response to trigger the client-side read timeout (default 10s)
        await asyncio.sleep(12)
        return Response(content="Timeout simulation completed", status_code=200)

    raise HTTPException(status_code=500, detail="Unhandled sandbox scenario")

