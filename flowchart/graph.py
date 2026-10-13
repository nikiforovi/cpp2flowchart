"""AST -> flowchart topology graph (nodes + port-labelled edges)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import nodes as N

# Node kinds: terminal | process | decision | io | connector
# Edge ports: t(top), b(bottom), l(left), r(right)
# Tail kinds: n(normal flow), b(break target), c(continue target)


@dataclass
class GNode:
    id: int
    kind: str
    text: str
    col: int = 0


@dataclass
class GEdge:
    src: int
    dst: int
    src_port: str
    dst_port: str
    label: str = ""
    branch: int = 0       # extra column offset for right-side branches
    down: bool = True     # participates in the top-down y ordering
    xmode: str = "down"   # 'down' -> same column, 'right' -> column + 1 + branch
    arrow: str = "auto"   # 'auto' | 'always' | 'never'


@dataclass
class Tail:
    node: int
    port: str
    kind: str = "n"
    xmode: str = "down"
    label: str = ""
    branch: int = 0
    arrow: str = "auto"


@dataclass
class Graph:
    name: str
    signature: str
    nodes: list[GNode] = field(default_factory=list)
    edges: list[GEdge] = field(default_factory=list)
    start: int = 0
    end: int = 0
    ret: int = -1


class _Builder:
    def __init__(self, func: N.FuncDef, user_funcs: set[str] | None = None):
        self.func = func
        self.nodes: list[GNode] = []
        self.edges: list[GEdge] = []
        self.cur_col = 0  # current layout column (x offset group)
        self.is_main = func.name == "main"
        self.user_funcs = user_funcs or set()
        self.return_edges = 0
        # main starts with "Начало", subroutines start with their name
        start_text = "Начало" if self.is_main else func.name
        self.start = self.add("terminal", start_text)
        self.end = self.add("terminal", "Конец")
        self.ret = self.add("terminal", "Возврат")

    # ---- primitives -------------------------------------------------------
    def add(self, kind: str, text: str) -> int:
        nid = len(self.nodes)
        self.nodes.append(GNode(nid, kind, text, col=self.cur_col))
        return nid

    def edge(self, src: int, dst: int, sp: str, dp: str, *,
             label: str = "", branch: int = 0, down: bool | None = None,
             xmode: str = "down", arrow: str = "auto") -> None:
        if down is None:
            down = dp == "t" and sp in ("b", "r")
        self.edges.append(
            GEdge(src, dst, sp, dp, label, branch, down, xmode, arrow)
        )

    def connect(self, tails: list[Tail], dst: int, dst_port: str = "t") -> None:
        for t in tails:
            self.edge(t.node, dst, t.port, dst_port,
                      label=t.label, branch=t.branch, xmode=t.xmode,
                      arrow=t.arrow)

    # ---- statements -------------------------------------------------------
    def wire(self, stmts: list, tails: list[Tail]) -> tuple[list[Tail], int | None]:
        n0 = len(self.nodes)
        for st in stmts:
            active = [t for t in tails if t.kind == "n"]
            passthru = [t for t in tails if t.kind != "n"]
            # break/continue tails pass through untouched to the enclosing loop
            tails = self.apply(st, active) + passthru
        first = self.nodes[n0].id if len(self.nodes) > n0 else None
        return tails, first

    def apply(self, stmt, tails: list[Tail]) -> list[Tail]:
        if isinstance(stmt, list):
            return self.wire(stmt, tails)[0]
        method = getattr(self, "_" + type(stmt).__name__, None)
        if method is None:
            return tails
        return method(stmt, tails)

    # ---- simple statements ------------------------------------------------
    def _simple(self, text: str, kind: str, tails: list[Tail]) -> list[Tail]:
        nid = self.add(kind, text)
        self.connect(tails, nid)
        return [Tail(nid, "b")]

    def _VarDecl(self, s: N.VarDecl, tails: list[Tail]) -> list[Tail]:
        # GOST: no data types on the chart; keep * and & markers
        text = s.name + (f" = {s.init}" if s.init else "")
        return self._simple(text, "process", tails)

    def _Assign(self, s: N.Assign, tails: list[Tail]) -> list[Tail]:
        return self._simple(f"{s.target} {s.op} {s.value}", "process", tails)

    def _ExprStmt(self, s: N.ExprStmt, tails: list[Tail]) -> list[Tail]:
        return self._simple(s.text, "process", tails)

    def _Call(self, s: N.Call, tails: list[Tail]) -> list[Tail]:
        args = f"({s.args})" if s.args else "()"
        kind = "predef" if s.name in self.user_funcs else "process"
        return self._simple(s.name + args, kind, tails)

    def _Input(self, s: N.Input, tails: list[Tail]) -> list[Tail]:
        items = ", ".join(s.items)
        return self._simple(f"Ввод: {items}", "io", tails)

    def _Output(self, s: N.Output, tails: list[Tail]) -> list[Tail]:
        items = " ".join(s.items)
        return self._simple(f"Вывод: {items}", "io", tails)

    def _Return(self, s: N.Return, tails: list[Tail]) -> list[Tail]:
        if self.is_main:
            # main: 'return <const>' ends the flow at the end marker;
            # 'return <expr>' is shown as a value block first (the value
            # still has to be computed before the program exits).
            if s.value and not re.fullmatch(r"[+-]?\d+", s.value.strip()):
                nid = self.add("process", s.value.strip())
                self.connect(tails, nid)
                self.edge(nid, self.end, "b", "t")
            else:
                for t in tails:
                    self.edge(t.node, self.end, t.port, "t",
                              label=t.label, branch=t.branch, xmode=t.xmode)
            return []
        text = "return" + (f" {s.value}" if s.value else "")
        nid = self.add("process", text)
        self.connect(tails, nid)
        self.edge(nid, self.ret, "b", "t")
        self.return_edges += 1
        return []

    def _Break(self, s: N.Break, tails: list[Tail]) -> list[Tail]:
        nid = self.add("connector", "break")
        self.connect(tails, nid)
        return [Tail(nid, "b", kind="b", xmode="right")]

    def _Continue(self, s: N.Continue, tails: list[Tail]) -> list[Tail]:
        nid = self.add("connector", "continue")
        self.connect(tails, nid)
        return [Tail(nid, "b", kind="c", xmode="right")]

    # ---- control flow ------------------------------------------------------
    def _If(self, s: N.If, tails: list[Tail]) -> list[Tail]:
        """Branch with an explicit merge node (GOST: branches join, then flow on)."""
        base = self.cur_col
        out: list[Tail] = []
        merge = self.add("merge", "")

        def chain(idx: int, dec: int) -> None:
            nonlocal prev_dec
            self.cur_col = base + idx
            cond_text, body = s.branches[idx]
            if idx > 0:
                self.edge(prev_dec, dec, "r", "t", label="нет")
            else:
                self.connect(tails, dec)
            # "yes" branch: body or empty direct link to the merge
            if body:
                bt, _ = self.wire(body, [Tail(dec, "b", label="да")])
                self._to_merge(bt, merge, out)
            else:
                self.edge(dec, merge, "b", "t", label="да")
            if idx + 1 < len(s.branches):
                prev_dec = dec
                nxt = self.add("decision", s.branches[idx + 1][0])
                chain(idx + 1, nxt)
            elif s.else_body is not None:
                self.cur_col = base + idx + 1
                if s.else_body:
                    et, _ = self.wire(
                        s.else_body, [Tail(dec, "r", label="нет")]
                    )
                    self._to_merge(et, merge, out)
                else:
                    self.edge(dec, merge, "r", "t", label="нет")
            else:
                # simplified if: explicit empty "no" branch to the merge
                self.edge(dec, merge, "r", "t", label="нет")

        prev_dec = -1
        first = self.add("decision", s.branches[0][0])
        chain(0, first)
        self.cur_col = base
        return [Tail(merge, "b")] + out

    def _to_merge(self, tails: list[Tail], merge: int, out: list[Tail]) -> None:
        """Connect normal tails to the merge; pass break/continue through."""
        for t in tails:
            if t.kind == "n":
                if t.node == merge:
                    continue  # body was empty-ish: edge already exists
                self.edge(t.node, merge, t.port, "t",
                          label=t.label, arrow=t.arrow)
            else:
                out.append(t)

    def _While(self, s: N.While, tails: list[Tail]) -> list[Tail]:
        dec = self.add("decision", s.cond or "true")
        self.connect(tails, dec)
        body_tails, _ = self.wire(s.body, [Tail(dec, "b", label="да")])
        out: list[Tail] = [Tail(dec, "r", label="нет")]
        for t in body_tails:
            if t.kind in ("n", "c"):
                # back edge joins the line above the condition (arrow!)
                self.edge(t.node, dec, "b", "t", down=False, arrow="always")
            else:  # break leaves the loop
                out.append(Tail(t.node, t.port, kind="n", xmode=t.xmode))
        return out

    def _DoWhile(self, s: N.DoWhile, tails: list[Tail]) -> list[Tail]:
        body_tails, first = self.wire(s.body, list(tails))
        dec = self.add("decision", s.cond or "true")
        out: list[Tail] = [Tail(dec, "r", label="нет")]
        for t in body_tails:
            if t.kind in ("n", "c"):
                self.edge(t.node, dec, t.port, "t")
            else:
                out.append(Tail(t.node, t.port, kind="n", xmode=t.xmode))
        if first is not None:
            # "да" goes back and joins the line above the body (arrow!)
            self.edge(dec, first, "b", "t", label="да",
                      down=False, arrow="always")
        return out

    def _For(self, s: N.For, tails: list[Tail]) -> list[Tail]:
        text = for_counter_text(s)
        hexagon = self.add("hexagon", text)
        self.connect(tails, hexagon)
        if not s.body:  # empty body: the back edge doubles as the branch
            self.edge(hexagon, hexagon, "b", "l", label="да",
                      down=False, arrow="always")
            return [Tail(hexagon, "r", label="нет")]
        body_tails, first = self.wire(
            s.body, [Tail(hexagon, "b", label="да")]
        )
        out: list[Tail] = [Tail(hexagon, "r", label="нет")]
        for t in body_tails:
            if t.kind in ("n", "c"):
                # back edge enters the left edge of the counter block
                if t.node == hexagon:
                    continue  # already handled (empty-ish body)
                self.edge(t.node, hexagon, "b", "l", down=False,
                          arrow="always")
            else:  # break
                out.append(Tail(t.node, t.port, kind="n", xmode=t.xmode))
        if first is None and not body_tails:
            self.edge(hexagon, hexagon, "b", "l", label="да",
                      down=False, arrow="always")
        return out

    def _Switch(self, s: N.Switch, tails: list[Tail]) -> list[Tail]:
        base = self.cur_col
        sw = self.add("decision", s.expr or "?")
        self.connect(tails, sw)
        out: list[Tail] = []
        cols: list[tuple[int | None, list[Tail]]] = []
        for i, (labels, body) in enumerate(s.cases):
            self.cur_col = base + 1 + i
            if labels is None:
                lbl = ""
            else:
                lbl = "=" + "|".join(labels)
            entry = Tail(sw, "r", label=lbl)
            bt, first = self.wire(body, [entry])
            for t in bt:
                if t.kind == "b":          # break exits the switch
                    out.append(Tail(t.node, t.port, kind="n",
                                    arrow="always"))
                elif t.kind == "c":        # continue passes through
                    out.append(t)
            normals = [t for t in bt if t.kind == "n"]
            cols.append((first, normals))
        if not any(labels is None for labels, _ in s.cases):
            # no default: an unmatched value bypasses all cases
            out.append(Tail(sw, "r", label="нет"))
        self.cur_col = base
        # fallthrough: normal exits of a non-last case flow into the next
        n = len(cols)
        for i, (entry, normals) in enumerate(cols):
            if not normals:
                continue
            target = None
            if i + 1 < n:
                for j in range(i + 1, n):
                    if cols[j][0] is not None:
                        target = cols[j][0]
                        break
            if target is not None:
                for t in normals:
                    # fallthrough is a horizontal handoff, not a new
                    # downward level: do not stack layout rows on it
                    self.edge(t.node, target, t.port, "t",
                              label=t.label, down=False)
            else:
                out.extend(normals)
        if not out and not any(c[1] for c in cols):
            out.append(Tail(sw, "r"))
        return out


def _param_names(params: str) -> list[str]:
    """Extract display names from a parameter list.

    Keeps pointer/reference markers, e.g. 'int *data, int &result'
    -> ['*data', '&result'].
    """
    import re
    names: list[str] = []
    for part in params.split(","):
        ids = re.findall(r"[A-Za-z_]\w*", part)
        if not ids:
            continue
        name = ids[-1]
        head = part[:part.rfind(name)]
        if "*" in head:
            name = "*" + name
        elif "&" in head:
            name = "&" + name
        names.append(name)
    return names


def for_counter_text(s: N.For) -> str:
    """Format a for-loop as a GOST counter hexagon: 'i = 0,10,2'.

    Returns the documented fallback '<init>; <cond>; <step>' when the
    loop cannot be reduced to a simple counter.
    """
    import re
    fallback = "; ".join(p for p in (s.init, s.cond, s.step) if p) or "true"
    init = s.init.strip()
    m = re.search(r"([A-Za-z_]\w*)\s*=\s*([^=]+)$", init)
    if not m:
        return fallback
    var, start = m.group(1), m.group(2).strip()

    # step: var++, ++var, var--, var += k, var -= k, var = var + k
    step: int | None = None
    st = s.step.strip()
    um = re.fullmatch(rf"(?:{re.escape(var)}\s*(\+\+|--)|(\+\+|--)\s*{re.escape(var)})", st)
    if um:
        op = um.group(1) or um.group(2)
        step = 1 if op == "++" else -1
    else:
        am = re.fullmatch(rf"{re.escape(var)}\s*([+\-])=\s*(-?\d+)", st)
        if am:
            step = int(am.group(2)) if am.group(1) == "+" else -int(am.group(2))
        else:
            em = re.fullmatch(
                rf"{re.escape(var)}\s*=\s*{re.escape(var)}\s*([+\-])\s*(\d+)", st
            )
            if em:
                step = int(em.group(2)) if em.group(1) == "+" else -int(em.group(2))
    if step is None or step == 0:
        return fallback

    cm = re.fullmatch(rf"{re.escape(var)}\s*(<=|<|>=|>)\s*(\S+)", s.cond.strip())
    if not cm:
        return fallback
    op, bound = cm.group(1), cm.group(2)

    # numeric bounds -> compute the last value reached by the step grid
    if re.fullmatch(r"-?\d+", start) and re.fullmatch(r"-?\d+", bound):
        s0, bnd = int(start), int(bound)
        if step > 0:
            if op == "<=":
                last = bnd
            elif op == "<":
                last = bnd - 1
            else:
                return fallback
        else:
            if op == ">=":
                last = bnd
            elif op == ">":
                last = bnd + 1
            else:
                return fallback
        if (last - s0) * step < 0:
            return fallback
        # include the limit only when the step grid reaches it
        last = s0 + ((last - s0) // step) * step
        return f"{var} = {s0},{last},{step}"
    # non-numeric bounds: show the bound as written (<=/>= semantics),
    # e.g. 'i = 0,n,1'. Types are stripped from the start value.
    if op in ("<=", ">="):
        clean = re.sub(r"^.*?\b([A-Za-z_]\w*)\s*=\s*", r"\1 = ",
                       f"{var} = {start}")
        return f"{clean},{bound},{step}"
    # strict inequalities with symbolic bounds cannot be reduced exactly:
    # show the read bound with a '~' prefix ('i = 0,~n,1').
    clean = re.sub(r"^.*?\b([A-Za-z_]\w*)\s*=\s*", r"\1 = ",
                   f"{var} = {start}")
    return f"{clean},{bound},{step}"


def build_graph(func: N.FuncDef, user_funcs: set[str] | None = None) -> Graph:
    b = _Builder(func, user_funcs)
    entry = [Tail(b.start, "b")]
    if not b.is_main:
        names = _param_names(func.params)
        if names:
            io = b.add("io", "Ввод: " + ", ".join(names))
            b.connect(entry, io)
            entry = [Tail(io, "b")]
    tails, _ = b.wire(func.body, entry)
    for t in tails:
        b.edge(t.node, b.end, t.port, "t", label=t.label,
               branch=t.branch, xmode=t.xmode)
    # hide unused terminators (GOST: no empty end blocks) - but main
    # always keeps its end marker
    if b.return_edges == 0:
        b.nodes[b.ret].kind = "skip"
    if not tails and not b.is_main:
        b.nodes[b.end].kind = "skip"
    return Graph(
        name=func.name,
        signature=func.name + (f"({func.params})" if func.params else "()"),
        nodes=b.nodes,
        edges=b.edges,
        start=b.start,
        end=b.end,
        ret=b.ret,
    )


def build_graphs(program: N.Program) -> list[Graph]:
    user_funcs = {f.name for f in program.funcs}
    graphs = [build_graph(f, user_funcs) for f in program.funcs]
    # main goes first (leftmost), subroutines follow to the side
    graphs.sort(key=lambda g: 0 if g.name == "main" else 1)
    return graphs


