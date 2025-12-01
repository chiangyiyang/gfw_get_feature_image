import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import requests
from dotenv import load_dotenv


def load_urls(path: Path) -> List[str]:
    """Load an array of URLs from a JSON file."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc

    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        return data
    raise ValueError(f"Expected a JSON array of strings in {path}")


def feature_id_from_url(url: str) -> str:
    """Extract the feature_id portion between /thumbnail/ and the query string."""
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path
    marker = "/thumbnail/"
    if marker in path:
        _, _, tail = path.partition(marker)
        # tail may contain additional slashes but feature ids in this dataset do not.
        feature_id = tail
    else:
        feature_id = path.rsplit("/", 1)[-1]
    return urllib.parse.unquote(feature_id)


def safe_filename(name: str) -> str:
    """Make a filesystem-safe filename for Windows."""
    forbidden = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in forbidden else ch for ch in name)
    cleaned = cleaned.strip().rstrip(".")  # avoid trailing dots/spaces on Windows
    return cleaned or "image"


def extension_from_content_type(content_type: Optional[str]) -> str:
    if not content_type:
        return ".bin"
    if "png" in content_type:
        return ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "webp" in content_type:
        return ".webp"
    return ".bin"


def download_image(
    session: requests.Session,
    url: str,
    output_dir: Path,
    token: Optional[str],
    timeout: int,
) -> Tuple[Path, int]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = session.get(url, headers=headers, timeout=timeout, stream=True)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        body_preview = resp.text[:500]
        raise RuntimeError(
            f"HTTP {resp.status_code} for {url}: {body_preview}")

    feature_id = feature_id_from_url(url)
    ext = extension_from_content_type(resp.headers.get("Content-Type"))
    filename = safe_filename(feature_id) + ext
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    with out_path.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return out_path, resp.status_code


def iterate_urls(urls: Iterable[str]) -> Iterable[str]:
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        yield url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download thumbnail images listed in img_urls.json using optional Bearer token."
    )
    parser.add_argument(
        "--input",
        default="img_urls.json",
        help="Path to JSON array of thumbnail URLs (default: img_urls.json).",
    )
    parser.add_argument(
        "--output-dir",
        default="images",
        help="Directory to save downloaded images (default: images).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GFW_TOKEN"),
        help="Bearer token for authenticated requests (default: env GFW_TOKEN, including .env).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Download only the first N URLs (optional).",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    try:
        urls = load_urls(input_path)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    if args.limit is not None:
        urls = urls[: args.limit]

    session = requests.Session()
    successes = 0
    failures: List[str] = []

    for idx, url in enumerate(iterate_urls(urls), start=1):
        try:
            out_path, status = download_image(
                session,
                url,
                output_dir=output_dir,
                token=args.token,
                timeout=args.timeout,
            )
            print(f"[{idx}] HTTP {status} -> {out_path}")
            successes += 1
        except Exception as exc:
            print(f"[{idx}] Failed: {url}\n  Reason: {exc}", file=sys.stderr)
            failures.append(url)

    print(
        f"\nDone. Success: {successes} | Failed: {len(failures)} | Output dir: {output_dir}"
    )
    if failures:
        print("Failed URLs (not downloaded):", file=sys.stderr)
        for url in failures:
            print(f"  {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
