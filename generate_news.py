import os, json, datetime as dt
import anthropic

MODEL = "claude-sonnet-5-5"
MAX_SEARCHES = 30
CATEGORIES = [
    "Languages & Compilers", "Frameworks & Libraries", "AI Coding Tools",
    "GitHub & Open Source", "Platforms & APIs", "DevOps & Infrastructure",
    "Security & Supply Chain", "Bugs & Breaking Changes", "IDEs & Editors",
    "Databases & Web Tech", "Emerging Tech",
]

now = dt.datetime.now(dt.timezone.utc)
start = now - dt.timedelta(hours=24)
F = "%Y-%m-%d %H:%M UTC"

SYSTEM = f"""You are a world-class developer-news researcher and editor (Coding & Developers only).
Task: find ALL important coding news worldwide published between {start.strftime(F)} and {now.strftime(F)}.

Categories (spread coverage; AI news must not dominate): {", ".join(CATEGORIES)}.

Research rules:
- Use web search extensively (many different queries per category, vendors, regions).
- Prefer primary sources: release notes, changelogs, GitHub releases, security advisories.
- Cross-check important stories with a second independent source when possible.
- Verify product name, exact version, status (stable/beta/RC/preview/proposal) and publication date.
- Never invent versions, benchmarks, CVEs, URLs or capabilities. Unverified => priority "RUMOR". If unsure, exclude.
- Security: include CVE, CVSS (only if official), affected/fixed versions, CONFIRMED vs theoretical exploitation.
- Priority: CRITICAL (actively exploited, supply-chain compromise, severe outage), HIGH (major stable
  releases, significant AI coding capability, breaking changes, big platform changes), MEDIUM (useful updates).
  Exclude LOW. Do not inflate importance. Merge duplicates. No sponsored content.
- Each summary: ONE precise sentence: what changed, version, why it matters to developers.
- Only real, direct URLs seen in search results.

Output ONLY valid JSON, no markdown fences, exactly this schema:
{{"coverage":"short note on coverage/limitations",
 "stories":[{{"priority":"CRITICAL|HIGH|MEDIUM|RUMOR","category":"one of the categories",
   "headline":"...","summary":"one sentence","source":"Publisher","date":"YYYY-MM-DD",
   "official_url":"https://...","confirm_url":"https://... or empty"}}],
 "gaps":["categories/regions not adequately researched"]}}
Order stories by priority, then impact."""

client = anthropic.Anthropic()
tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_SEARCHES}]
messages = [{"role": "user", "content": "Begin researching now and return the JSON digest."}]

resp = None
for _ in range(8):
    with client.messages.stream(
        model=MODEL, max_tokens=32000, system=SYSTEM, tools=tools, messages=messages
    ) as s:
        resp = s.get_final_message()
    if resp.stop_reason != "pause_turn":
        break
    messages.append({"role": "assistant", "content": resp.content})

text = "".join(b.text for b in resp.content if b.type == "text")
data = json.loads(text[text.index("{"): text.rindex("}") + 1])

order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "RUMOR": 3}
seen, stories = set(), []
for st in data.get("stories", []):
    url = st.get("official_url", "")
    key = st.get("headline", "").strip().lower()
    if not url.startswith("https://") or not key or key in seen or st.get("priority") not in order:
        continue
    seen.add(key)
    if not str(st.get("confirm_url", "")).startswith("https://"):
        st["confirm_url"] = ""
    stories.append(st)
stories.sort(key=lambda x: order[x["priority"]])

out = {
    "generated": now.strftime(F),
    "window": f"{start.strftime(F)} – {now.strftime(F)}",
    "timezone": "UTC",
    "coverage": data.get("coverage", ""),
    "gaps": data.get("gaps", []),
    "stories": stories,
}
with open("news.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"OK: {len(stories)} stories")
