import json
from pathlib import Path


def load_features(path: Path):
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        if "main" in data and isinstance(data["main"], dict):
            main = data["main"]
            if isinstance(main.get("features"), list):
                return main["features"]
        if isinstance(data.get("features"), list):
            return data["features"]
        if isinstance(data.get("data"), list):
            return data["data"]
    return []


def feature_id(feature: dict):
    props = feature.get("properties") or {}
    return props.get("id") or feature.get("id")


def main(
    input_file: Path = Path("features.json"),
    output_file: Path = Path("img_urls.json"),
    dataset: str = "public-global-sentinel2-thumbnails:v3.0",
):
    base = "https://gateway.api.globalfishingwatch.org/v3/thumbnail/"
    urls = []
    for feat in load_features(input_file):
        fid = feature_id(feat)
        if fid:
            urls.append(f"{base}{fid}?dataset={dataset}")
    output_file.write_text(json.dumps(urls, ensure_ascii=True, indent=2))
    print(f"Wrote {len(urls)} URLs to {output_file}")


if __name__ == "__main__":
    main()
