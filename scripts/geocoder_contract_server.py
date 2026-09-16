"""Localhost-only Nominatim contract server over synthetic, PII-free fixtures."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def create_server(port: int, fixture: Path) -> ThreadingHTTPServer:
    rows = load_rows(fixture)
    by_query = {row["query"].casefold(): row for row in rows}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/search":
                self.send_error(404)
                return
            query = parse_qs(parsed.query).get("q", [""])[0].casefold()
            row = by_query.get(query)
            payload = []
            if row:
                payload.append(
                    {
                        "place_id": row["provider_id"],
                        "display_name": row["display_name"],
                        "lat": str(row["lat"]),
                        "lon": str(row["lon"]),
                        "addresstype": {
                            "building": "house",
                            "street": "road",
                            "area": "suburb",
                        }[row["precision"]],
                    }
                )
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fixture", type=Path, default=Path("data/geocoder-gold.synthetic.jsonl"))
    args = parser.parse_args()
    server = create_server(args.port, args.fixture)
    print(f"Synthetic geocoder contract server: http://127.0.0.1:{server.server_port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
