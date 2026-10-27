"""Bilder til matretter: fillagring (ImageStore) og generering fra instruks
(ImageGenerator). Bilder lagres først som «ventende» slik at admin kan
forhåndsvise før de knyttes til en rett."""
from __future__ import annotations

import html
import logging
import os
import re
import shutil
import uuid
from typing import Optional

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class ImageError(ValueError):
    pass


class ImageStore:
    """Eier filene. pending_dir ligger utenfor static/; ferdige bilder i
    static/uploads/dishes så de kan serveres direkte."""

    def __init__(self, pending_dir: str, static_dir: str, public_subdir="uploads/dishes"):
        self.pending_dir = pending_dir
        self.static_dir = static_dir
        self.public_subdir = public_subdir
        os.makedirs(pending_dir, exist_ok=True)
        os.makedirs(os.path.join(static_dir, public_subdir), exist_ok=True)

    @staticmethod
    def extension_for(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ImageError("Filtypen støttes ikke. Bruk PNG, JPG, WEBP, GIF eller SVG.")
        return ext

    def save_pending(self, data: bytes, ext: str) -> str:
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageError("Bildet er større enn 5 MB.")
        if not data:
            raise ImageError("Filen er tom.")
        if ext == "svg":
            data = sanitize_svg(data.decode("utf-8", errors="ignore")).encode("utf-8")
        token = f"{uuid.uuid4().hex}.{ext}"
        with open(os.path.join(self.pending_dir, token), "wb") as f:
            f.write(data)
        return token

    def _pending_file(self, token: str) -> str:
        # Token kommer fra brukeren via skjema – tillat kun vårt eget format
        if not re.fullmatch(r"[0-9a-f]{32}\.[a-z]{3,4}", token or ""):
            raise ImageError("Ugyldig bilde-referanse.")
        path = os.path.join(self.pending_dir, token)
        if not os.path.exists(path):
            raise ImageError("Forhåndsvisningen har utløpt. Last opp eller generer på nytt.")
        return path

    def pending_path(self, token: str) -> str:
        return self._pending_file(token)

    def commit(self, token: str) -> str:
        """Flytter et ventende bilde til static/. Returnerer sti relativ til static/."""
        src = self._pending_file(token)
        rel = f"{self.public_subdir}/{token}"
        shutil.move(src, os.path.join(self.static_dir, rel))
        return rel

    def clear_all(self) -> None:
        """Sletter alle lagrede og ventende bilder (brukes av seed-scriptet)."""
        public = os.path.join(self.static_dir, self.public_subdir)
        for folder in (self.pending_dir, public):
            for name in os.listdir(folder):
                if name != ".gitkeep":
                    os.remove(os.path.join(folder, name))

    def delete(self, rel_path: Optional[str]) -> None:
        if not rel_path or not rel_path.startswith(self.public_subdir + "/"):
            return
        path = os.path.join(self.static_dir, rel_path)
        if os.path.exists(path):
            os.remove(path)


SVG_SYSTEM_PROMPT = (
    "You are an illustrator for a Norwegian catering company. Given a description of "
    "a dish, reply with a single self-contained SVG illustration (viewBox 0 0 400 300) "
    "of the dish, appetising and flat-styled, with no text in the image. "
    "Reply with the SVG markup only."
)


class ImageGenerator:
    """Lager et bilde fra en tekstinstruks.

    Med ANTHROPIC_API_KEY satt bruker den Claude til å tegne en SVG-illustrasjon.
    Uten nøkkel (eller ved feil) lages en enkel plassholder, så appen alltid virker.
    """

    def __init__(self, api_key: Optional[str], model: str = "claude-opus-5-5"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> tuple[bytes, str, str]:
        """Returnerer (bytes, filendelse, kilde) der kilde er 'claude' eller 'plassholder'."""
        prompt = prompt.strip()
        if not prompt:
            raise ImageError("Skriv en instruks for bildet.")
        if self.api_key:
            try:
                return self._generate_with_claude(prompt), "svg", "claude"
            except Exception as exc:  # noqa: BLE001 – faller tilbake til plassholder
                log.warning("Bildegenerering med Claude feilet: %s", exc)
        return self._placeholder(prompt), "svg", "plassholder"

    def _generate_with_claude(self, prompt: str) -> bytes:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SVG_SYSTEM_PROMPT,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise ImageError("Claude avslo å lage bildet.")
        text = "".join(b.text for b in response.content if b.type == "text")
        match = re.search(r"<svg\b.*?</svg>", text, re.DOTALL | re.IGNORECASE)
        if not match:
            raise ImageError("Svaret inneholdt ikke SVG.")
        return sanitize_svg(match.group(0)).encode("utf-8")

    @staticmethod
    def _placeholder(prompt: str) -> bytes:
        hue = sum(ord(c) for c in prompt) % 360
        label = html.escape(prompt[:60] + ("…" if len(prompt) > 60 else ""))
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
  <rect width="400" height="300" fill="hsl({hue},45%,88%)"/>
  <ellipse cx="200" cy="165" rx="130" ry="80" fill="#fff" stroke="hsl({hue},30%,70%)" stroke-width="4"/>
  <ellipse cx="200" cy="160" rx="90" ry="50" fill="hsl({hue},55%,60%)"/>
  <circle cx="170" cy="150" r="14" fill="hsl({(hue + 90) % 360},50%,45%)"/>
  <circle cx="225" cy="165" r="10" fill="hsl({(hue + 180) % 360},50%,50%)"/>
  <text x="200" y="280" font-family="sans-serif" font-size="14" text-anchor="middle"
        fill="hsl({hue},30%,30%)">{label}</text>
</svg>"""
        return svg.encode("utf-8")


def sanitize_svg(svg: str) -> str:
    """Fjerner script og hendelsesattributter fra SVG fra en ekstern tjeneste."""
    svg = re.sub(r"<script\b.*?</script>", "", svg, flags=re.DOTALL | re.IGNORECASE)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.IGNORECASE)
    svg = re.sub(r"(href\s*=\s*[\"'])\s*javascript:[^\"']*", r"\1#", svg, flags=re.IGNORECASE)
    return svg
