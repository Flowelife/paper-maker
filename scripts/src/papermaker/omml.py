"""LaTeX (subset) to OMML conversion.

Produces ``m:oMath`` elements that Word and WPS both render as native
equations, so variables, subscripts and fractions stay editable in the
equation editor instead of degrading into plain text.
"""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element, SubElement

from .ns import m, w, xml_space

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "omicron": "ο", "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "ϕ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ",
    "Omega": "Ω",
}

SYMBOLS = {
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠",
    "approx": "≈", "sim": "∼", "simeq": "≃", "cong": "≅", "equiv": "≡",
    "propto": "∝", "ll": "≪", "gg": "≫", "to": "→", "rightarrow": "→",
    "leftarrow": "←", "leftrightarrow": "↔", "Rightarrow": "⇒",
    "Leftarrow": "⇐", "Leftrightarrow": "⇔", "mapsto": "↦",
    "times": "×", "div": "÷", "cdot": "⋅", "ast": "∗", "star": "⋆",
    "pm": "±", "mp": "∓", "infty": "∞", "partial": "∂", "nabla": "∇",
    "forall": "∀", "exists": "∃", "in": "∈", "notin": "∉", "ni": "∋",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
    "cup": "∪", "cap": "∩", "setminus": "∖", "emptyset": "∅",
    "ldots": "…", "dots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "lvert": "|", "rvert": "|", "vert": "|", "mid": "|", "parallel": "∥",
    "langle": "⟨", "rangle": "⟩", "lceil": "⌈", "rceil": "⌉",
    "lfloor": "⌊", "rfloor": "⌋", "top": "⊤", "perp": "⊥", "angle": "∠",
    "therefore": "∴", "because": "∵", "prime": "′", "degree": "°",
    "ell": "ℓ", "hbar": "ℏ", "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ",
    "triangle": "△", "square": "□", "checkmark": "✓", "dagger": "†",
    "ddagger": "‡", "S": "§", "P": "¶", "copyright": "©", "par": "‖",
    "colon": ":",
}

FUNCTIONS = {
    "log", "ln", "lg", "exp", "sin", "cos", "tan", "cot", "sec", "csc",
    "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "coth", "max",
    "min", "sup", "inf", "lim", "liminf", "limsup", "det", "dim", "ker",
    "deg", "gcd", "hom", "arg", "Pr", "mod", "bmod", "rank", "tr",
}

NARY = {
    "sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫", "iint": "∬",
    "iiint": "∭", "oint": "∮", "bigcup": "⋃", "bigcap": "⋂",
}

ACCENTS = {
    "hat": "\u0302", "widehat": "\u0302", "tilde": "\u0303",
    "widetilde": "\u0303", "bar": "\u0304", "dot": "\u0307",
    "ddot": "\u0308", "vec": "\u20d7", "check": "\u030c", "breve": "\u0306",
}

SPACES = {
    ",": "\u2009", ";": "\u2005", ":": "\u2005", "!": "", " ": "\u00a0",
    "quad": "\u2003", "qquad": "\u2003\u2003", "enspace": "\u2002",
}

STOP_CMDS = {"right", "end", "middle", "\\"}
BINARY_CMDS = {
    "le", "leq", "ge", "geq", "ne", "neq", "approx", "sim", "simeq", "cong",
    "equiv", "propto", "ll", "gg", "to", "rightarrow", "leftarrow",
    "Rightarrow", "Leftrightarrow", "map", "mapsto", "times", "div", "cdot",
    "ast", "pm", "mp", "in", "notin", "subset", "cup", "cap", "mid",
    "quad", "qquad", "\\", "tag", "label",
}
BINARY_CHARS = set("=+-<>±×÷⋅,;:")

TEXT_FONT = "Times New Roman"
CJK_FONT = "宋体"


def _val(parent: Element, tag: str, value: str, ns=m) -> Element:
    el = SubElement(parent, ns(tag))
    el.set(m("val"), value)
    return el


def math_run(text: str, *, style: str | None = None, script: str | None = None,
             font: str | None = None, east: str | None = None,
             sz: int | None = None) -> Element:
    """A single OMML run. ``style`` is 'p' (upright) / 'b' / 'i' / 'bi'."""
    run = Element(m("r"))
    rpr = SubElement(run, m("rPr"))
    if script:
        _val(rpr, "scr", script)
    if style:
        _val(rpr, "sty", style)
    if font or east or sz:
        wrpr = SubElement(run, w("rPr"))
        if font or east:
            fonts = SubElement(wrpr, w("rFonts"))
            if font:
                fonts.set(w("ascii"), font)
                fonts.set(w("hAnsi"), font)
                fonts.set(w("cs"), font)
            if east:
                fonts.set(w("eastAsia"), east)
                fonts.set(w("hint"), "eastAsia")
        if sz:
            SubElement(wrpr, w("sz")).set(w("val"), str(sz))
            SubElement(wrpr, w("szCs")).set(w("val"), str(sz))
    t = SubElement(run, m("t"))
    t.text = text
    t.set(xml_space(), "preserve")
    return run


def _container(tag: str, children) -> Element:
    el = Element(m(tag))
    for child in children:
        el.append(child)
    return el


class _Nary:
    __slots__ = ("chr", "sub", "sup", "elem")

    def __init__(self, char: str):
        self.chr = char
        self.sub: list[Element] | None = None
        self.sup: list[Element] | None = None
        self.elem: list[Element] | None = None


class LatexParser:
    def __init__(self, source: str, display: bool = True):
        self.src = source
        self.pos = 0
        self.n = len(source)
        self.display = display

    # -- primitive readers -------------------------------------------------
    def peek(self) -> str:
        return self.src[self.pos] if self.pos < self.n else ""

    def eof(self) -> bool:
        return self.pos >= self.n

    def skip_spaces(self) -> None:
        while self.pos < self.n and self.src[self.pos] in " \t\r\n":
            self.pos += 1

    def read_command(self) -> str:
        """Consume a control sequence, returning its name without backslash."""
        assert self.src[self.pos] == "\\"
        self.pos += 1
        if self.pos >= self.n:
            return "\\"
        ch = self.src[self.pos]
        if ch.isalpha():
            start = self.pos
            while self.pos < self.n and self.src[self.pos].isalpha():
                self.pos += 1
            return self.src[start:self.pos]
        self.pos += 1
        return ch

    def peek_command(self) -> str | None:
        if self.pos < self.n and self.src[self.pos] == "\\":
            save = self.pos
            name = self.read_command()
            self.pos = save
            return name
        return None

    # -- parsing -----------------------------------------------------------
    def parse(self) -> list[Element]:
        items = self.parse_sequence(stop_chars="", stop_cmds=frozenset())
        return items

    def parse_sequence(self, stop_chars: str, stop_cmds: frozenset | set) -> list[Element]:
        items: list[Element] = []
        while True:
            self.skip_spaces()
            if self.eof():
                break
            ch = self.peek()
            if ch in stop_chars:
                break
            if ch == "\\":
                cmd = self.peek_command()
                if cmd in stop_cmds:
                    break
                if cmd == "\\":
                    # line break outside environments: ignore
                    self.read_command()
                    continue
            if ch == "&":
                self.pos += 1
                continue
            atom = self.parse_scripted()
            if atom is None:
                break
            items.extend(self.materialize(atom))
        return items

    def materialize(self, atom) -> list[Element]:
        if isinstance(atom, _Nary):
            return [self.build_nary(atom)]
        return atom

    def parse_group(self) -> list[Element]:
        """Parse ``{...}`` returning its content."""
        self.skip_spaces()
        if self.peek() != "{":
            return self.parse_atom_material()
        self.pos += 1
        inner = self.parse_sequence(stop_chars="}", stop_cmds=frozenset())
        if self.peek() == "}":
            self.pos += 1
        return inner

    def parse_atom_material(self) -> list[Element]:
        atom = self.parse_scripted()
        if atom is None:
            return []
        return self.materialize(atom)

    def parse_scripted(self):
        atom = self.parse_atom()
        if atom is None:
            return None
        if isinstance(atom, _Nary):
            self.attach_limits(atom)
            return atom
        base: list[Element] = atom
        sub = sup = None
        while True:
            self.skip_spaces()
            ch = self.peek()
            if ch == "^":
                self.pos += 1
                sup = self.parse_script_arg()
            elif ch == "_":
                self.pos += 1
                sub = self.parse_script_arg()
            else:
                break
        if sub is None and sup is None:
            return base
        if not base:
            base = [math_run("", style="p")]
        if sub is not None and sup is not None:
            el = Element(m("sSubSup"))
            el.append(_container("e", base))
            el.append(_container("sub", sub))
            el.append(_container("sup", sup))
            return [el]
        if sub is not None:
            el = Element(m("sSub"))
            el.append(_container("e", base))
            el.append(_container("sub", sub))
            return [el]
        el = Element(m("sSup"))
        el.append(_container("e", base))
        el.append(_container("sup", sup))
        return [el]

    def parse_script_arg(self) -> list[Element]:
        self.skip_spaces()
        if self.peek() == "{":
            return self.parse_group()
        atom = self.parse_atom()
        if atom is None:
            return []
        return self.materialize(atom)

    def attach_limits(self, nary: _Nary) -> None:
        while True:
            self.skip_spaces()
            ch = self.peek()
            if ch == "_":
                self.pos += 1
                nary.sub = self.parse_script_arg()
            elif ch == "^":
                self.pos += 1
                nary.sup = self.parse_script_arg()
            else:
                break
        nary.elem = self.parse_operand()

    def parse_operand(self) -> list[Element]:
        self.skip_spaces()
        if self.eof():
            return []
        ch = self.peek()
        if ch in BINARY_CHARS or ch in ")]}":
            return []
        if ch == "\\":
            cmd = self.peek_command()
            if cmd in BINARY_CMDS or cmd in STOP_CMDS:
                return []
        items: list[Element] = []
        while True:
            self.skip_spaces()
            if self.eof():
                break
            ch = self.peek()
            if ch in BINARY_CHARS or ch in ")]}":
                break
            if ch == "\\":
                cmd = self.peek_command()
                if cmd in BINARY_CMDS or cmd in STOP_CMDS:
                    break
            atom = self.parse_scripted()
            if atom is None:
                break
            items.extend(self.materialize(atom))
        return items

    def build_nary(self, nary: _Nary) -> Element:
        el = Element(m("nary"))
        pr = SubElement(el, m("naryPr"))
        _val(pr, "chr", nary.chr)
        _val(pr, "limLoc", "undOvr" if nary.chr not in "∫∬∭∮" else "subSup")
        _val(pr, "grow", "1")
        if nary.sub is None:
            SubElement(pr, m("subHide")).set(m("val"), "1")
        if nary.sup is None:
            SubElement(pr, m("supHide")).set(m("val"), "1")
        el.append(_container("sub", nary.sub or []))
        el.append(_container("sup", nary.sup or []))
        el.append(_container("e", nary.elem or []))
        return el

    # -- atoms -------------------------------------------------------------
    def parse_atom(self):
        self.skip_spaces()
        if self.eof():
            return None
        ch = self.peek()
        if ch == "{":
            return self.parse_group()
        if ch == "\\":
            return self.parse_command()
        if ch.isdigit():
            start = self.pos
            while self.pos < self.n and (self.src[self.pos].isdigit() or
                                         (self.src[self.pos] == "." and
                                          self.pos + 1 < self.n and self.src[self.pos + 1].isdigit())):
                self.pos += 1
            return [math_run(self.src[start:self.pos], style="p")]
        if ch.isalpha():
            start = self.pos
            while self.pos < self.n and self.src[self.pos].isalpha() and ord(self.src[self.pos]) < 0x2E80:
                self.pos += 1
            return [math_run(self.src[start:self.pos])]
        if ord(ch) > 0x2E80:
            start = self.pos
            while self.pos < self.n and ord(self.src[self.pos]) > 0x2E80:
                self.pos += 1
            return [math_run(self.src[start:self.pos], style="p", east=CJK_FONT)]
        self.pos += 1
        if ch in "=+-<>":
            char = "−" if ch == "-" else ch
            return [math_run(f" {char} " if self.display else char, style="p")]
        if ch == ",":
            return [math_run(", " if self.display else ",", style="p")]
        if ch in ";:":
            return [math_run(f"{ch} " if self.display else ch, style="p")]
        if ch == "|":
            return [math_run("|", style="p")]
        return [math_run(ch, style="p")]

    def parse_command(self):
        name = self.read_command()
        if name in GREEK:
            char = GREEK[name]
            if name[0].isupper():
                return [math_run(char, style="p")]
            return [math_run(char)]
        if name in SYMBOLS:
            return [math_run(SYMBOLS[name], style="p")]
        if name in FUNCTIONS:
            return self.parse_function(name)
        if name in NARY:
            return _Nary(NARY[name])
        if name in ACCENTS:
            inner = self.parse_group()
            el = Element(m("acc"))
            pr = SubElement(el, m("accPr"))
            _val(pr, "chr", ACCENTS[name])
            el.append(_container("e", inner))
            return [el]
        if name in ("overline", "underline"):
            inner = self.parse_group()
            el = Element(m("bar"))
            pr = SubElement(el, m("barPr"))
            _val(pr, "pos", "top" if name == "overline" else "bot")
            el.append(_container("e", inner))
            return [el]
        if name == "frac" or name == "dfrac" or name == "tfrac":
            num = self.parse_group()
            den = self.parse_group()
            el = Element(m("f"))
            el.append(_container("num", num))
            el.append(_container("den", den))
            return [el]
        if name == "sqrt":
            degree: list[Element] | None = None
            self.skip_spaces()
            if self.peek() == "[":
                self.pos += 1
                degree = self.parse_sequence(stop_chars="]", stop_cmds=frozenset())
                if self.peek() == "]":
                    self.pos += 1
            body = self.parse_group()
            el = Element(m("rad"))
            pr = SubElement(el, m("radPr"))
            if degree is None:
                SubElement(pr, m("degHide")).set(m("val"), "1")
            el.append(_container("deg", degree or []))
            el.append(_container("e", body))
            return [el]
        if name == "left":
            return self.parse_delimited()
        if name == "right":
            # unbalanced \right: consume the delimiter and continue
            self.read_delimiter()
            return []
        if name in SPACES:
            text = SPACES[name]
            return [math_run(text, style="p")] if text else []
        if name in ("text", "textrm", "mbox", "textnormal", "hbox"):
            return [self.text_run()]
        if name in ("mathrm", "operatorname", "mathsf", "rm", "mathit"):
            inner = self.parse_group()
            self.force_style(inner, "p" if name != "mathit" else "i")
            return inner
        if name in ("mathbf", "bm"):
            inner = self.parse_group()
            self.force_style(inner, "b")
            return inner
        if name == "boldsymbol":
            inner = self.parse_group()
            self.force_style(inner, "bi")
            return inner
        if name == "mathbb":
            inner = self.parse_group()
            self.force_style(inner, "p", script="double-struck")
            return inner
        if name == "mathcal":
            inner = self.parse_group()
            self.force_style(inner, "p", script="script")
            return inner
        if name == "mathfrak":
            inner = self.parse_group()
            self.force_style(inner, "p", script="fraktur")
            return inner
        if name in ("begin",):
            return self.parse_environment()
        if name in ("limits", "nolimits", "displaystyle", "textstyle",
                    "scriptstyle", "label", "nonumber", "notag", "middle"):
            if name == "middle":
                return [math_run("|", style="p")]
            return []
        if name == "tag":
            # tag is handled by the equation renderer; ignore here
            self.parse_group()
            return []
        if name in ("|",):
            return [math_run("‖", style="p")]
        if name in ("{", "}", "%", "&", "#", "$", "_"):
            return [math_run(name, style="p")]
        if name == "\\":
            return []
        # unknown command: degrade to its name, upright
        return [math_run(name, style="p")]

    def text_run(self) -> Element:
        self.skip_spaces()
        if self.peek() != "{":
            return math_run("", style="p", font=TEXT_FONT, east=CJK_FONT)
        start = self.pos
        depth = 0
        while self.pos < self.n:
            ch = self.src[self.pos]
            if ch == "\\" and self.pos + 1 < self.n:
                self.pos += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            self.pos += 1
        text = self.src[start + 1:self.pos]
        if self.peek() == "}":
            self.pos += 1
        return math_run(text, style="p", font=TEXT_FONT, east=CJK_FONT)

    def parse_function(self, name: str):
        run = math_run(name, style="p")
        self.skip_spaces()
        if self.eof():
            return [run]
        ch = self.peek()
        if ch == "\\":
            cmd = self.peek_command()
            if cmd in BINARY_CMDS or cmd in STOP_CMDS:
                return [run]
        if ch in BINARY_CHARS or ch in ")]}":
            return [run]
        if ch == "[":
            self.pos += 1
            inner = self.parse_sequence(stop_chars="]", stop_cmds=frozenset())
            if self.peek() == "]":
                self.pos += 1
            arg = [self.delimited(inner, "[", "]")]
        elif ch == "(":
            self.pos += 1
            inner = self.parse_sequence(stop_chars=")", stop_cmds=frozenset())
            if self.peek() == ")":
                self.pos += 1
            arg = [self.delimited(inner, "(", ")")]
        else:
            arg = self.parse_atom_material()
        if not arg:
            return [run]
        el = Element(m("func"))
        el.append(_container("fName", [run]))
        el.append(_container("e", arg))
        return [el]

    @staticmethod
    def delimited(inner: list[Element], beg: str, end: str) -> Element:
        d = Element(m("d"))
        pr = SubElement(d, m("dPr"))
        _val(pr, "begChr", beg)
        _val(pr, "endChr", end)
        _val(pr, "grow", "1")
        d.append(_container("e", inner))
        return d

    def read_delimiter(self) -> str:
        self.skip_spaces()
        if self.eof():
            return ""
        ch = self.peek()
        if ch == "\\":
            name = self.read_command()
            if name == "{":
                return "{"
            if name == "}":
                return "}"
            if name == "|":
                return "‖"
            return SYMBOLS.get(name, "")
        self.pos += 1
        return "" if ch == "." else ch

    def parse_delimited(self) -> list[Element]:
        beg = self.read_delimiter()
        inner = self.parse_sequence(stop_chars="", stop_cmds=frozenset({"right"}))
        end = ""
        self.skip_spaces()
        if self.peek_command() == "right":
            self.read_command()
            end = self.read_delimiter()
        return [self.delimited(inner, beg, end)]

    def force_style(self, elements: list[Element], style: str,
                    script: str | None = None) -> None:
        for el in elements:
            if el.tag == m("r"):
                rpr = el.find(m("rPr"))
                if rpr is None:
                    rpr = Element(m("rPr"))
                    el.insert(0, rpr)
                if script is not None:
                    existing = rpr.find(m("scr"))
                    if existing is None:
                        existing = Element(m("scr"))
                        rpr.insert(0, existing)
                    existing.set(m("val"), script)
                sty = rpr.find(m("sty"))
                if sty is None:
                    sty = SubElement(rpr, m("sty"))
                sty.set(m("val"), style)
            else:
                self.force_style(list(el), style, script)

    # -- environments ------------------------------------------------------
    def parse_environment(self) -> list[Element]:
        name = ""
        self.skip_spaces()
        if self.peek() == "{":
            self.pos += 1
            start = self.pos
            while self.pos < self.n and self.src[self.pos] != "}":
                self.pos += 1
            name = self.src[start:self.pos]
            if self.peek() == "}":
                self.pos += 1
        rows = self.split_rows(lambda cmd: cmd == "end")
        if name in ("cases", "dcases"):
            body = self.eq_array(rows)
            return [self.delimited([body], "{", "")]
        if name in ("aligned", "align", "align*", "gathered", "gather",
                    "split", "eqnarray", "array", "alignedat"):
            return [self.eq_array(rows)]
        if name in ("matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix",
                    "Vmatrix", "smallmatrix"):
            matrix = self.matrix(rows)
            if name == "pmatrix":
                return [self.delimited([matrix], "(", ")")]
            if name == "bmatrix":
                return [self.delimited([matrix], "[", "]")]
            if name == "Bmatrix":
                return [self.delimited([matrix], "{", "}")]
            if name == "vmatrix":
                return [self.delimited([matrix], "|", "|")]
            return [matrix]
        return [self.eq_array(rows)]

    def split_rows(self, is_end) -> list[list[list[Element]]]:
        rows: list[list[list[Element]]] = []
        cells: list[list[Element]] = []
        current: list[Element] = []
        while True:
            self.skip_spaces()
            if self.eof():
                break
            if self.peek() == "\\":
                cmd = self.peek_command()
                if is_end(cmd):
                    self.read_command()
                    self.skip_spaces()
                    if self.peek() == "{":
                        while self.pos < self.n and self.src[self.pos] != "}":
                            self.pos += 1
                        if self.peek() == "}":
                            self.pos += 1
                    break
                if cmd == "\\":
                    self.read_command()
                    cells.append(current)
                    rows.append(cells)
                    cells = []
                    current = []
                    continue
                if cmd == "cr":
                    self.read_command()
                    cells.append(current)
                    rows.append(cells)
                    cells = []
                    current = []
                    continue
            if self.peek() == "&":
                self.pos += 1
                cells.append(current)
                current = []
                continue
            atom = self.parse_scripted()
            if atom is None:
                break
            current.extend(self.materialize(atom))
        if current:
            cells.append(current)
        if cells:
            rows.append(cells)
        return [row for row in rows if row]

    @staticmethod
    def eq_array(rows: list[list[list[Element]]]) -> Element:
        arr = Element(m("eqArr"))
        for row in rows:
            merged: list[Element] = []
            for idx, cell in enumerate(row):
                if idx:
                    merged.append(math_run("\u2003", style="p"))
                merged.extend(cell)
            arr.append(_container("e", merged or [math_run("", style="p")]))
        return arr

    @staticmethod
    def matrix(rows: list[list[list[Element]]]) -> Element:
        matrix = Element(m("m"))
        pr = SubElement(matrix, m("mPr"))
        base_jc = SubElement(pr, m("baseJc"))
        base_jc.set(m("val"), "center")
        for row in rows:
            mr = SubElement(matrix, m("mr"))
            for cell in row:
                mr.append(_container("e", cell or [math_run("", style="p")]))
        return matrix


def latex_to_omath(latex: str, display: bool = True) -> Element:
    """Convert LaTeX source into an ``m:oMath`` element.

    ``display`` keeps spaces around binary operators (block equations); inline
    formulas use TeX's tight spacing, matching how Word typesets them.
    """
    source = latex.strip()
    parser = LatexParser(source, display=display)
    omath = Element(m("oMath"))
    try:
        for child in parser.parse():
            omath.append(child)
    except Exception:  # noqa: BLE001 - never let math break the build
        omath.clear()
        omath.append(math_run(source, style="p", font=TEXT_FONT))
    if len(omath) == 0:
        omath.append(math_run("", style="p"))
    return omath


TAG_RE = re.compile(r"\\tag\*?\s*\{([^{}]*)\}")


def extract_tag(latex: str) -> tuple[str, str | None]:
    match = TAG_RE.search(latex)
    if not match:
        return latex, None
    return latex[:match.start()] + latex[match.end():], match.group(1).strip()
