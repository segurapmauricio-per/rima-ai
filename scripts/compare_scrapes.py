"""Compara scrape actual vs snapshot / baseline."""
import json
from pathlib import Path

BASELINE = {
    "https://www.instagram.com/p/DSXp9ifjHin/": (8412053, 1410555, 99911),
    "https://www.instagram.com/p/DVlUiHGDEEa/": (590356, 33071, 26887),
    "https://www.instagram.com/p/DR3TLLwE6N1/": (426803, 36115, 151),
}


def main():
    cid = [d for d in Path("data/clients").iterdir() if d.name.startswith("negocio_b")][0]
    root = cid / "market_research"
    new = json.loads((root / "latest.json").read_text(encoding="utf-8"))
    snap_path = root / "snapshots" / "W23_2026.json"
    old = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}

    print("=== META ===")
    print("scrape_at:", new.get("timestamp", "")[:19])
    for k in ("metrics_updated", "viral_spikes", "deep_analyzed", "deep_analysis_parsed", "transcripts_ok"):
        print(f"  {k}: {new.get(k)}")

    new_urls = {p["url"] for p in new["posts"] if p.get("url")}
    old_urls = {p["url"] for p in old.get("posts", []) if p.get("url")}
    print("\n=== URL DIFF vs snapshot ===")
    print("  added:", len(new_urls - old_urls), "| removed:", len(old_urls - new_urls))

    print("\n=== METRIC DELTAS (~12h) ===")
    for p in new["posts"]:
        u = p.get("url")
        if u not in BASELINE:
            continue
        bv, bl, bc = BASELINE[u]
        print(f"  @{p['owner']} views {bv} -> {p['views']} ({p['views']-bv:+d})")
        print(f"    likes {bl} -> {p['likes']} ({p['likes']-bl:+d})  comm {bc} -> {p['comments']} ({p['comments']-bc:+d})")

    for p in new["posts"]:
        if (p.get("timestamp") or "").startswith("2026-06-09"):
            aj = p.get("analisis_json") or {}
            print("\n=== POST MAS RECIENTE (jun 9) ===")
            print(f"  @{p['owner']} views={p['views']} transcripcion={len(p.get('transcripcion') or '')} chars")
            print(f"  que_modelar: {(aj.get('que_modelar') or '')[:140]}")
            break

    for p in new["posts"]:
        if (p.get("transcripcion") or "").strip():
            aj = p.get("analisis_json") or {}
            print("\n=== MUESTRA TRANSCRIPCION ===")
            print(f"  @{p['owner']} mod={p.get('modelabilidad')}")
            print(f"  hook_hablado: {(aj.get('hook_hablado') or '')[:100]}")
            print(f"  guion: {(p.get('transcripcion') or '')[:160]}...")
            print(f"  que_modelar: {(aj.get('que_modelar') or '')[:140]}")
            break

    pi = new.get("profile_insights") or {}
    if pi:
        print("\n=== profile_insights (considerar) ===")
        for user, ins in pi.items():
            print(f"  @{user}: {(ins.get('considerar') or '')[:180]}")


if __name__ == "__main__":
    main()
