"""User-defined terminology and glossary enforcement for translations."""

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Glossary:
    """Manages term mappings to guarantee terminology consistency."""

    terms: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, mapping: dict[str, str]) -> "Glossary":
        """Create glossary from an in-memory dictionary."""
        return cls(terms=dict(mapping))

    @classmethod
    def from_file(cls, path: Path) -> "Glossary":
        """Load glossary from JSON or CSV file."""
        path = Path(path)
        if not path.exists():
            return cls()

        terms: dict[str, str] = {}
        if path.suffix.lower() == ".json":
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    terms = {str(k): str(v) for k, v in data.items()}
        elif path.suffix.lower() in (".csv", ".tsv"):
            delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
            with open(path, encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if len(row) >= 2:
                        src, tgt = row[0].strip(), row[1].strip()
                        if src and tgt:
                            terms[src] = tgt
        return cls(terms=terms)

    def apply(self, text: str) -> str:
        """Replace glossary terms in translated text using word-boundary matching."""
        if not self.terms or not text:
            return text

        result = text
        for src, tgt in self.terms.items():
            pattern = re.compile(rf"\b{re.escape(src)}\b", re.IGNORECASE)

            def _replacer(match: re.Match[str], target: str = tgt) -> str:
                matched_str = match.group(0)
                # Preserve titlecase or uppercase if source was titlecase or uppercase
                if matched_str.isupper():
                    return target.upper()
                if matched_str.istitle():
                    return target.capitalize()
                return target

            result = pattern.sub(_replacer, result)
        return result

    def get_prompt_hints(self) -> str:
        """Format glossary terms as prompt constraints for LLM translators."""
        if not self.terms:
            return ""
        lines = [f'- "{src}" -> "{tgt}"' for src, tgt in self.terms.items()]
        return (
            "Glossary constraints (you MUST use these exact translations when terms occur):\n"
            + "\n".join(lines)
        )
