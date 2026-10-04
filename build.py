# Builds a USD high-impact (red folder) ForexFactory calendar feed.
import hashlib, json, os, urllib.request
from datetime import datetime, timedelta, timezone

SRC = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CURRENCIES = {"USD"}          # e.g. {"USD", "EUR", "GBP"}
KEEP_DAYS = 120               # how much history to keep in the calendar
owner, name = os.environ["GITHUB_REPOSITORY"].split("/")
SITE = f"https://{owner.lower()}.github.io/{name}/"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ff-red-news"})
    return urllib.request.urlopen(req, timeout=30).read()

def esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

events = {}
try:  # keep earlier weeks: merge with what is already published
    for e in json.loads(get(SITE + "events.json")):
        events[e["uid"]] = e
except Exception as ex:
    print("No previous events:", ex)

week = json.loads(get(SRC))
fresh = 0
for e in week:
    if e.get("impact") != "High" or e.get("country") not in CURRENCIES:
        continue
    start = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
    key = f'{e["country"]}|{e["title"]}|{start:%Y%m%d}'
    uid = hashlib.md5(key.encode()).hexdigest() + "@ff-red-news"
    events[uid] = {"uid": uid, "title": e["title"], "country": e["country"],
                   "start": start.strftime("%Y%m%dT%H%M%SZ"),
                   "forecast": e.get("forecast", ""), "previous": e.get("previous", "")}
    fresh += 1
print(f"{fresh} red events this week, {len(events)} total before pruning")

cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
events = {u: e for u, e in events.items()
          if datetime.strptime(e["start"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc) > cutoff}

now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ff-red-news//EN", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", "X-WR-CALNAME:Red News (USD)", "X-PUBLISHED-TTL:PT6H",
         "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
for e in sorted(events.values(), key=lambda x: x["start"]):
    s = datetime.strptime(e["start"], "%Y%m%dT%H%M%SZ")
    end = (s + timedelta(minutes=30)).strftime("%Y%m%dT%H%M%SZ")
    desc = f'Forecast: {e["forecast"] or "-"}\nPrevious: {e["previous"] or "-"}\nSource: ForexFactory'
    lines += ["BEGIN:VEVENT", f'UID:{e["uid"]}', f"DTSTAMP:{now}", f'DTSTART:{e["start"]}',
              f"DTEND:{end}", f'SUMMARY:{esc("🔴 " + e["country"] + " " + e["title"])}',
              f"DESCRIPTION:{esc(desc)}", "TRANSP:TRANSPARENT",
              "BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-PT15M",
              f'DESCRIPTION:{esc(e["country"] + " " + e["title"] + " in 15 min")}', "END:VALARM",
              "END:VEVENT"]
lines.append("END:VCALENDAR")

os.makedirs("_site", exist_ok=True)
with open("_site/red-news.ics", "w", encoding="utf-8", newline="") as f:
    f.write("\r\n".join(lines) + "\r\n")
with open("_site/events.json", "w") as f:
    json.dump(list(events.values()), f)
with open("_site/index.html", "w") as f:
    f.write(f'<p>Subscribe: <a href="webcal://{owner.lower()}.github.io/{name}/red-news.ics">'
            f'webcal://{owner.lower()}.github.io/{name}/red-news.ics</a></p>')
