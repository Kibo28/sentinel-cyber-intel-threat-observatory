from pathlib import Path


def test_cyber_intel_branding_in_frontend():
    static=Path(__file__).resolve().parents[1]/"app"/"static"
    html=(static/"index.html").read_text(encoding="utf-8")
    js=(static/"app.js").read_text(encoding="utf-8")
    css=(static/"app.css").read_text(encoding="utf-8")
    assert "Cyber Intel — Threat Observatory" in html
    assert "SENTINEL" not in html
    assert "cyber-intel-icon.png" in html
    assert "Cyber Intel · Threat Observatory" in js
    assert "[data-theme=light]" in css
    assert (static/"assets"/"cyber-intel-icon.png").is_file()
    assert (static/"assets"/"cyber-intel-wordmark.png").is_file()
