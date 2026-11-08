"""Local Piper neural Text-to-Speech provider."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from voxstream.errors import ProviderError
from voxstream.providers.base import Voice


class PiperTtsProvider:
    name = "piper"
    sample_rate = 22050

    def __init__(self, piper_bin: str = "piper", model_path: Path | None = None) -> None:
        self.piper_bin = piper_bin
        self.model_path = model_path

    def list_voices(self, lang: str) -> list[Voice]:
        return [Voice(id=f"piper-{lang}", name=f"Piper {lang.upper()}", lang=lang)]

    async def synthesize(
        self,
        text: str,
        *,
        lang: str,
        voice: str | None = None,
        rate: float = 1.0,
    ) -> Path:
        bin_path = shutil.which(self.piper_bin)
        if not bin_path:
            raise ProviderError("piper binary not found on PATH.", provider=self.name)

        tmp_out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        out_path = Path(tmp_out.name)
        tmp_out.close()

        cmd = [bin_path, "--output_file", str(out_path)]
        if self.model_path:
            cmd.extend(["--model", str(self.model_path)])

        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                raise ProviderError(
                    f"Piper error: {proc.stderr.decode('utf-8')}", provider=self.name
                )
            return out_path
        except Exception as exc:
            if out_path.exists():
                out_path.unlink(missing_ok=True)
            raise ProviderError(f"Piper execution failed: {exc}", provider=self.name) from exc
