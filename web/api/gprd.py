from http.server import BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import json
import xlrd

GPRD_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"


def _iso_day(value):
    digits = str(int(value))
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def load_gprd(start="1985-01-01", end=None, frequency="daily"):
    end = end or datetime.utcnow().strftime("%Y-%m-%d")
    request = Request(GPRD_URL, headers={"User-Agent": "Oil-Price-Intelligence/1.0"})
    with urlopen(request, timeout=35) as response:
        workbook = xlrd.open_workbook(file_contents=response.read())
    sheet = workbook.sheet_by_index(0)
    headers = [str(sheet.cell_value(0, column)).strip() for column in range(sheet.ncols)]
    day_column = headers.index("DAY")
    value_column = headers.index("GPRD")
    rows = []
    for index in range(1, sheet.nrows):
        try:
            stamp = _iso_day(sheet.cell_value(index, day_column))
            value = float(sheet.cell_value(index, value_column))
        except (TypeError, ValueError):
            continue
        if start <= stamp <= end:
            rows.append({"date": stamp, "value": value})
    if frequency == "monthly":
        grouped = {}
        for point in rows:
            grouped[point["date"][:7]] = point
        rows = list(grouped.values())
    return rows


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            start = query.get("start", ["1985-01-01"])[0]
            end = query.get("end", [None])[0]
            frequency = "monthly" if query.get("frequency", ["daily"])[0] == "monthly" else "daily"
            points = load_gprd(start, end, frequency)
            if not points:
                raise ValueError("Official GPRD workbook returned no observations for the requested range")
            payload = {
                "id": "GPRD",
                "name": "地缘政治风险指数（传统日度 GPR）",
                "nameEn": "Geopolitical Risk Index (traditional daily GPR)",
                "source": "Caldara-Iacoviello GPR",
                "unit": "指数",
                "frequency": "月度" if frequency == "monthly" else "日度",
                "updated": points[-1]["date"],
                "color": "#c47d59",
                "points": points,
                "officialPage": "https://www.matteoiacoviello.com/gpr.htm",
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, s-maxage=21600, stale-while-revalidate=86400")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": "Official GPRD source unavailable", "detail": str(exc)[:300]}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
