"""Minimal YAML subset parser (stdlib only).

Supports the subset used by robot-forge project files:
  - block mappings and sequences (indentation based)
  - flow mappings {a: 1, b: [2, 3]}
  - flow sequences [a, b]
  - quoted ('...' / "...") and plain scalars
  - comments, blank lines, block scalars (| and >)
  - bool / null / int / float / hex-string passthrough

It intentionally does NOT support anchors, aliases, tags, multi-document,
merge keys, or complex keys. If PyYAML is installed, callers should prefer it.
"""

from __future__ import annotations

import re

__all__ = ["loads", "YamlError"]


class YamlError(ValueError):
    def __init__(self, message, line=None):
        self.line = line
        super().__init__("line %s: %s" % (line, message) if line else message)


def loads(text):
    parser = _Parser(text)
    return parser.parse()


def _strip_comment(line):
    out = []
    quote = None
    prev = ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote and prev != "\\":
                quote = None
        else:
            if ch in ("'", '"'):
                quote = ch
                out.append(ch)
            elif ch == "#" and (not out or out[-1].isspace()):
                break
            else:
                out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _split_key(text):
    """Split 'key: value' at the first top-level colon. Returns (key, rest) or None."""
    quote = None
    depth = 0
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            if i + 1 == len(text) or text[i + 1] in " \t":
                return text[:i].strip(), text[i + 1:].strip()
    return None


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        body = value[1:-1]
        if value[0] == "'":
            return body.replace("''", "'")
        return (
            body.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
    return value


_NUM_RE = re.compile(r"^[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?$")


def _scalar(text):
    text = text.strip()
    if text == "":
        return None
    if text[0] in "[{" and text[-1] in "]}":
        return _FlowParser(text).parse()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return _unquote(text)
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    if _NUM_RE.match(text):
        try:
            return int(text) if "." not in text else float(text)
        except ValueError:
            pass
    return text


class _FlowParser:
    def __init__(self, text):
        self.text = text
        self.i = 0

    def parse(self):
        value = self._value()
        self._ws()
        if self.i != len(self.text):
            raise YamlError("unexpected flow content: %r" % self.text[self.i:])
        return value

    def _ws(self):
        while self.i < len(self.text) and self.text[self.i] in " \t\r\n":
            self.i += 1

    def _value(self):
        self._ws()
        if self.i >= len(self.text):
            return None
        ch = self.text[self.i]
        if ch == "[":
            return self._list()
        if ch == "{":
            return self._map()
        if ch in ("'", '"'):
            return self._string()
        start = self.i
        depth = 0
        while self.i < len(self.text):
            c = self.text[self.i]
            if c in "[{":
                depth += 1
            elif c in "]}":
                if depth == 0:
                    break
                depth -= 1
            elif c == "," and depth == 0:
                break
            self.i += 1
        return _scalar(self.text[start:self.i].strip())

    def _string(self):
        quote = self.text[self.i]
        start = self.i
        self.i += 1
        while self.i < len(self.text):
            if self.text[self.i] == quote and self.text[self.i - 1] != "\\":
                self.i += 1
                break
            self.i += 1
        return _unquote(self.text[start:self.i])

    def _list(self):
        self.i += 1
        out = []
        while True:
            self._ws()
            if self.i >= len(self.text):
                raise YamlError("unterminated flow list")
            if self.text[self.i] == "]":
                self.i += 1
                return out
            out.append(self._value())
            self._ws()
            if self.i < len(self.text) and self.text[self.i] == ",":
                self.i += 1

    def _key(self):
        self._ws()
        if self.i < len(self.text) and self.text[self.i] in ("'", '"'):
            return str(self._string())
        start = self.i
        while self.i < len(self.text) and self.text[self.i] != ":":
            self.i += 1
        return self.text[start:self.i].strip()

    def _map(self):
        self.i += 1
        out = {}
        while True:
            self._ws()
            if self.i >= len(self.text):
                raise YamlError("unterminated flow map")
            if self.text[self.i] == "}":
                self.i += 1
                return out
            key = self._key()
            self._ws()
            if self.i >= len(self.text) or self.text[self.i] != ":":
                raise YamlError("expected ':' in flow map")
            self.i += 1
            out[str(key)] = self._value()
            self._ws()
            if self.i < len(self.text) and self.text[self.i] == ",":
                self.i += 1


class _Line:
    __slots__ = ("indent", "text", "no")

    def __init__(self, indent, text, no):
        self.indent = indent
        self.text = text
        self.no = no


class _Parser:
    def __init__(self, text):
        if "\t" in text:
            raise YamlError("tabs are not allowed for indentation")
        self.raw = text.splitlines()
        self.lines = []
        self.i = 0
        self._prepare()

    def _prepare(self):
        idx = 0
        while idx < len(self.raw):
            raw = self.raw[idx]
            no = idx + 1
            stripped = _strip_comment(raw)
            if not stripped.strip():
                idx += 1
                continue
            indent = len(stripped) - len(stripped.lstrip(" "))
            self.lines.append(_Line(indent, stripped.strip(), no))
            idx += 1

    def parse(self):
        if not self.lines:
            return None
        value = self._block(self.lines[0].indent)
        if self.i < len(self.lines):
            raise YamlError("trailing content", self.lines[self.i].no)
        return value

    def _peek(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def _block(self, indent):
        line = self._peek()
        if line is None:
            return None
        if line.text == "-" or line.text.startswith("- "):
            return self._seq(indent)
        return self._map(indent)

    def _seq(self, indent):
        out = []
        while True:
            line = self._peek()
            if line is None or line.indent != indent:
                break
            if not (line.text == "-" or line.text.startswith("- ")):
                break
            rest = line.text[1:].strip()
            self.i += 1
            if rest == "":
                nxt = self._peek()
                if nxt is not None and nxt.indent > indent:
                    out.append(self._block(nxt.indent))
                else:
                    out.append(None)
                continue
            kv = _split_key(rest)
            if kv and not rest.startswith(("{", "[")):
                key, val = kv
                item = {}
                item[_unquote(key)] = self._value_after(val, indent, line.no)
                # continuation of this mapping item
                nxt = self._peek()
                if nxt is not None and nxt.indent > indent:
                    extra = self._map(nxt.indent)
                    if isinstance(extra, dict):
                        item.update(extra)
                    else:
                        raise YamlError("expected map continuation", nxt.no)
                out.append(item)
            else:
                out.append(_scalar(rest))
                nxt = self._peek()
                if nxt is not None and nxt.indent > indent:
                    raise YamlError("unexpected nested block after scalar", nxt.no)
        return out

    def _map(self, indent):
        out = {}
        while True:
            line = self._peek()
            if line is None or line.indent != indent:
                break
            if line.text == "-" or line.text.startswith("- "):
                raise YamlError("sequence item where mapping expected", line.no)
            kv = _split_key(line.text)
            if not kv:
                raise YamlError("expected 'key: value'", line.no)
            key, rest = kv
            key = _unquote(key)
            self.i += 1
            out[key] = self._value_after(rest, indent, line.no)
        return out

    def _value_after(self, rest, indent, no):
        if rest == "":
            nxt = self._peek()
            if nxt is not None and nxt.indent > indent:
                return self._block(nxt.indent)
            return None
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            return self._block_scalar(rest, indent, no)
        return _scalar(rest)

    def _block_scalar(self, style, indent, no):
        chunks = []
        while self.i < len(self.lines) and self.lines[self.i].indent > indent:
            line = self.lines[self.i]
            chunks.append(" " * (line.indent - indent - 2) + line.text if line.indent >= indent + 2 else line.text)
            self.i += 1
        if style.startswith(">"):
            return " ".join(c.strip() for c in chunks).strip()
        return "\n".join(c.rstrip() for c in chunks).strip("\n")
