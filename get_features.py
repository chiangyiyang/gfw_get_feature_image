import argparse
import json
import os
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

import mapbox_vector_tile
import requests
from dotenv import load_dotenv


DEFAULT_URL = (
    "https://gateway.api.globalfishingwatch.org/v3/4wings/tile/position/12/3294/1837"
    "?datasets%5B0%5D=public-global-sentinel2-presence%3Av3.0"
    "&filters%5B0%5D=matched%20IN%20%28%27false%27%29"
    "&format=MVT&max-points=5000"
    "&properties%5B0%5D=bearing%2Cshipname%2Cvessel_id"
    "&date-range=2025-08-01T00%3A00%3A00.000Z%2C2025-11-24T00%3A00%3A00.000Z"
)


def fetch_tile(
    url: str,
    token: Optional[str] = None,
    timeout: int = 30,
    origin: Optional[str] = None,
    debug_http: bool = False,
) -> bytes:
    """Request the MVT tile and return raw bytes."""
    headers = {"Accept": "application/x-protobuf"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin

    response = requests.get(url, timeout=timeout, headers=headers)
    if debug_http:
        print(
            f"HTTP {response.status_code} {response.reason}, "
            f"Headers: {dict(response.headers)}"
        )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        # Surface error body to help diagnose 401/403/4xx issues.
        print(f"Response body: {response.text}", file=sys.stderr)
        raise
    return response.content


def decode_tile(tile_bytes: bytes) -> Dict[str, Any]:
    """Decode Mapbox Vector Tile bytes into python structures."""
    return mapbox_vector_tile.decode(tile_bytes)


def summarize_layers(tile: Dict[str, Any], max_features: int = 3) -> None:
    """
    Print a compact summary of layers and a few sample features.
    Limits per-layer output to avoid flooding the console.
    """
    if not tile:
        print("No layers found in the tile.")
        return

    for layer_name, layer_data in tile.items():
        features = layer_data.get("features", [])
        print(f"\nLayer: {layer_name} | feature count: {len(features)}")

        for idx, feature in enumerate(features[:max_features], start=1):
            geom_type = feature.get("type")
            props = feature.get("properties", {})
            # Only show the first geometry coordinate for brevity.
            geometry = feature.get("geometry")
            first_geom = None
            if geometry and isinstance(geometry, list):
                first_geom = geometry[0]
            elif geometry:
                first_geom = geometry

            print(
                f"  Feature {idx}: type={geom_type} "
                f"sample_geom={first_geom} properties={json.dumps(props, ensure_ascii=False)}"
            )

        if len(features) > max_features:
            print(f"  ... {len(features) - max_features} more features omitted ...")


def truncate_geometry(geom: Any, max_coords: int) -> Any:
    """Recursively trim geometry lists to avoid huge console output."""
    if not isinstance(geom, list):
        return geom
    trimmed = geom[:max_coords]
    return [truncate_geometry(item, max_coords) for item in trimmed]


def print_geometries(
    tile: Dict[str, Any], max_features: int = 5, max_coords: int = 10
) -> None:
    """Print geometry for a limited number of features per layer."""
    if not tile:
        print("\nNo geometries to display.")
        return

    print(f"\nGeometries (max_features={max_features}, max_coords={max_coords}):")
    for layer_name, layer_data in tile.items():
        features: List[Dict[str, Any]] = layer_data.get("features", [])
        if not features:
            continue

        print(f"\nLayer: {layer_name}")
        for idx, feature in enumerate(features[:max_features], start=1):
            geom_type = feature.get("type")
            geometry = feature.get("geometry")
            trimmed_geom = truncate_geometry(geometry, max_coords)
            print(f"  Feature {idx}: type={geom_type} geometry={trimmed_geom}")

        if len(features) > max_features:
            print(f"  ... {len(features) - max_features} more features omitted ...")


def adjust_matched_filter(url: str, matched_choice: Optional[str]) -> str:
    """
    Override the matched filter in the URL.
    matched_choice: "true" | "false" | "any" | None.
      - None: leave URL unchanged.
      - "any": remove matched filter.
      - others: set filters[0]=matched IN ('<value>').
    """
    if matched_choice is None:
        return url

    parsed = urllib.parse.urlsplit(url)
    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

    # Drop existing filters[0] if present.
    query_items = [(k, v) for k, v in query_items if k != "filters[0]"]

    if matched_choice != "any":
        query_items.append(("filters[0]", f"matched IN ('{matched_choice}')"))

    new_query = urllib.parse.urlencode(query_items, doseq=True)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
    )


def print_selected_fields(tile: Dict[str, Any]) -> None:
    """
    Print requested fields (bearing, shipname, vessel_id) for all features.
    Each line: <layer> | bearing=<...> | shipname=<...> | vessel_id=<...>
    """
    if not tile:
        print("\nNo data to list requested fields.")
        return

    print("\nRequested fields (bearing, shipname, vessel_id):")
    for layer_name, layer_data in tile.items():
        features = layer_data.get("features", [])
        for feature in features:
            props = feature.get("properties", {})
            bearing = props.get("bearing")
            shipname = props.get("shipname")
            vessel_id = props.get("vessel_id")
            print(
                f"{layer_name} | bearing={bearing} | shipname={shipname} | vessel_id={vessel_id}"
            )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Fetch and decode a Global Fishing Watch MVT tile."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Tile URL to request. Defaults to the provided sample URL.",
    )
    parser.add_argument(
        "--max-features",
        type=int,
        default=3,
        help="Max number of sample features to print per layer.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GFW_TOKEN"),
        help="Bearer token if the endpoint requires authentication. "
        "Defaults to the GFW_TOKEN env var (including values loaded from a .env file).",
    )
    parser.add_argument(
        "--origin",
        default=None,
        help="Optional Origin header to mimic browser requests if required by the API.",
    )
    parser.add_argument(
        "--debug-http",
        action="store_true",
        help="Print HTTP status/headers and error body to help debug auth issues.",
    )
    parser.add_argument(
        "--matched",
        choices=["true", "false", "any"],
        default=os.getenv("GFW_MATCHED"),
        help="Override the matched filter. "
        "'true' or 'false' sets filters[0]=matched IN ('...'); 'any' removes the filter.",
    )
    parser.add_argument(
        "--print-geometry",
        action="store_true",
        help="When set, print geometries for a limited number of features per layer.",
    )
    parser.add_argument(
        "--geometry-max-features",
        type=int,
        default=5,
        help="Max number of features per layer to print geometry for (used with --print-geometry).",
    )
    parser.add_argument(
        "--geometry-max-coords",
        type=int,
        default=10,
        help="Max number of coordinate elements to include per geometry (used with --print-geometry).",
    )
    args = parser.parse_args()

    try:
        url = adjust_matched_filter(args.url, args.matched)
        print(f"Requesting tile...\n{url}\n")
        raw_tile = fetch_tile(
            url,
            token=args.token,
            origin=args.origin,
            debug_http=args.debug_http,
        )
        print(f"Received {len(raw_tile)} bytes. Decoding...\n")
        decoded = decode_tile(raw_tile)
        summarize_layers(decoded, max_features=args.max_features)
        # print_selected_fields(decoded)
        if args.print_geometry:
            print_geometries(
                decoded,
                max_features=args.geometry_max_features,
                max_coords=args.geometry_max_coords,
            )
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
