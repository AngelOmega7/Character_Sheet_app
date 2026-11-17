"""Apply the owner's smoke/invisibility targeting rule to catalogs and guides."""
import json
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
TARGETING_RULE = "the Zoid cannot be targeted by attacks, but can still be hit by AoE attacks"
OLD_RULE = re.compile(
    r"(?:the )?attacks against (?:the Zoid|you|it) have disadvantage"
    r"|attack rolls against it have disadvantage"
    r"|(?:attack rolls|attacks) have disadvantage against (?:your Zoid|this zoid|you)"
    r"|(?:gain )?disadva(?:n)?tage on (?:attack rolls|attacks) against you", re.I)


def revise_concealment(text):
    if not isinstance(text, str) or not re.search(r"smoke|invisib", text, re.I):
        return text
    return OLD_RULE.sub(lambda match: TARGETING_RULE[0].upper() + TARGETING_RULE[1:]
                        if match[0][0].isupper() else TARGETING_RULE, text)


def update_guide(path):
    lines = path.read_text().splitlines()
    output, index = [], 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^( +)Effect: (.*)", line)
        if not match:
            output.append(line)
            index += 1
            continue
        indent = match[1]
        end = index + 1
        while end < len(lines) and lines[end].startswith(indent) and lines[end].strip():
            if re.match(r"\s*(?:\d+\.|[A-Za-z][A-Za-z /-]*:)", lines[end]):
                break
            end += 1
        original = " ".join([match[2], *(s.strip() for s in lines[index + 1:end])])
        revised = revise_concealment(original)
        output.extend(textwrap.wrap("Effect: " + revised, width=76, initial_indent=indent,
                                   subsequent_indent=indent) if revised != original else lines[index:end])
        index = end
    path.write_text("\n".join(output) + "\n")


def main():
    count = 0
    for name in ("zoids", "transports", "armaments"):
        path = ROOT / f"zoids_app/data/{name}.json"
        table = json.loads(path.read_text())
        for record in table["records"]:
            for key, value in record["fields"].items():
                revised = revise_concealment(value)
                if revised != value:
                    record["fields"][key] = revised
                    count += 1
        path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n")
    for name in ("ZOIDS_Companion.txt", "Equipment_Guide.txt"):
        update_guide(ROOT / name)
    print(f"Updated {count} smoke/invisibility descriptions and both guides.")


if __name__ == "__main__":
    main()
