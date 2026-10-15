"""PyQt6 GUI: C++ editor on the left, interactive flowchart on the right."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QAction, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF,
    QKeySequence, QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QInputDialog, QLabel,
    QPlainTextEdit, QSplitter, QToolBar, QVBoxLayout, QWidget,
    QGraphicsPathItem, QGraphicsSimpleTextItem, QFileDialog,
    QGraphicsItemGroup, QScrollArea,
)

from flowchart.convert import (
    ParseError, convert, convert_to_drawio, convert_to_svg,
)
from flowchart.layout import LGraph, LNode, edge_arrow

EXAMPLE = """#include <iostream>
using namespace std;

int main() {
    int n, sum = 0;
    cin >> n;
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    if (sum > 100) {
        cout << "big: " << sum << endl;
    } else {
        cout << "small: " << sum << endl;
    }
    int k = 0;
    do {
        k++;
    } while (k < 3);
    while (k > 0) {
        k--;
        if (k == 2) continue;
        if (k == 1) break;
    }
    switch (k) {
        case 0: cout << "zero" << endl; break;
        case 1: cout << "one" << endl; break;
        default: cout << "other" << endl;
    }
    return 0;
}
"""

_COLORS = {
    "terminal": ("#ffffff", "#000000"),
    "process": ("#ffffff", "#000000"),
    "predef": ("#ffffff", "#000000"),
    "io": ("#ffffff", "#000000"),
    "decision": ("#ffffff", "#000000"),
    "hexagon": ("#ffffff", "#000000"),
    "connector": ("#ffffff", "#000000"),
    "merge": ("#f8fafc", "#000000"),
}
_EDGE = QColor("#000000")
_TEXT = QColor("#000000")


class FlowView(QGraphicsView):
    """QGraphicsView with Ctrl+wheel zoom and zoom buttons support."""

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def zoom_in(self) -> None:
        self.scale(1.25, 1.25)

    def zoom_out(self) -> None:
        self.scale(0.8, 0.8)

    def zoom_fit(self) -> None:
        rect = self.scene().sceneRect()
        if not rect.isEmpty():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_reset(self) -> None:
        self.resetTransform()


def _node_path(n: LNode) -> QPainterPath:
    p = QPainterPath()
    x, y, w, h = n.x, n.y, n.w, n.h
    if n.kind == "terminal":
        p.addRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
    elif n.kind == "process":
        p.addRect(QRectF(x, y, w, h))
    elif n.kind == "predef":
        p.addRect(QRectF(x, y, w, h))
    elif n.kind == "io":
        sk = 14.0
        poly = QPolygonF([
            QPointF(x + sk, y), QPointF(x + w, y),
            QPointF(x + w - sk, y + h), QPointF(x, y + h),
        ])
        p.addPolygon(poly)
    elif n.kind == "decision":
        cx, cy = x + w / 2, y + h / 2
        poly = QPolygonF([
            QPointF(cx, y), QPointF(x + w, cy),
            QPointF(cx, y + h), QPointF(x, cy),
        ])
        p.addPolygon(poly)
    elif n.kind == "hexagon":
        c = w * 0.16
        poly = QPolygonF([
            QPointF(x + c, y), QPointF(x + w - c, y),
            QPointF(x + w, y + h / 2), QPointF(x + w - c, y + h),
            QPointF(x + c, y + h), QPointF(x, y + h / 2),
        ])
        p.addPolygon(poly)
    elif n.kind == "merge":
        # merge anchors are invisible: only the joining lines are drawn
        p = QPainterPath()
        return p
    else:  # connector
        p.addEllipse(QRectF(x, y, w, h))
    p.closeSubpath()
    return p


class StatusWindow(QWidget):
    """Floatable window for displaying status messages."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Статус")
        self.resize(600, 150)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.status_label = QLabel("Готово")
        self.status_label.setWordWrap(True)
        font = self.status_label.font()
        font.setPointSize(11)
        self.status_label.setFont(font)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.status_label)
        layout.addWidget(scroll)

    def set_text(self, text: str) -> None:
        self.status_label.setText(text)
        self.show()


def _arrow_head(a: QPointF, b: QPointF) -> QPolygonF:
    """Triangle at point b pointing along a->b."""
    import math
    ang = math.atan2(b.y() - a.y(), b.x() - a.x())
    size = 9.0
    wing = 0.45
    p1 = QPointF(b.x(), b.y())
    p2 = QPointF(
        b.x() - size * math.cos(ang - wing),
        b.y() - size * math.sin(ang - wing),
    )
    p3 = QPointF(
        b.x() - size * math.cos(ang + wing),
        b.y() - size * math.sin(ang + wing),
    )
    return QPolygonF([p1, p2, p3])


def build_scene(graphs: list[LGraph]) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setBackgroundBrush(QColor("#f8fafc"))
    if not graphs:
        return scene
    pad = 30.0
    hgap = 80.0
    x_off = pad
    oy = pad + 24
    for g in graphs:
        group = QGraphicsItemGroup()

        for e in g.edges:
            if len(e.points) < 2:
                continue
            pts = [QPointF(px + x_off, py + oy) for px, py in e.points]
            path = QPainterPath(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(_EDGE, 1.6))
            item.setZValue(-1)
            group.addToGroup(item)
            # GOST 19.701-90: arrows only off the default flow direction
            if edge_arrow(e.points, e.arrow):
                head_poly = _arrow_head(pts[-2], pts[-1])
                hp = QPainterPath()
                hp.addPolygon(head_poly)
                hp.closeSubpath()
                head = QGraphicsPathItem(hp)
                head.setPen(QPen(_EDGE, 1))
                head.setBrush(_EDGE)
                head.setZValue(-1)
                group.addToGroup(head)
            if e.label:
                lbl = QGraphicsSimpleTextItem(e.label)
                lbl.setBrush(QColor("#334155"))
                lf = lbl.font()
                lf.setPointSize(9)
                lbl.setFont(lf)
                lbl.setPos(e.lx + x_off, e.ly + oy - 8)
                group.addToGroup(lbl)

        for n in g.nodes:
            fill, stroke = _COLORS.get(n.kind, ("#ffffff", "#475569"))
            item = QGraphicsPathItem(_node_path(
                LNode(n.id, n.kind, n.x + x_off, n.y + oy, n.w, n.h, n.lines)
            ))
            item.setPen(QPen(QColor(stroke), 1.6))
            item.setBrush(QColor(fill))
            group.addToGroup(item)
            if n.kind == "predef":
                for dx in (8.0, n.w - 8.0):
                    path = QPainterPath()
                    path.moveTo(QPointF(n.x + x_off + dx, n.y + oy))
                    path.lineTo(QPointF(n.x + x_off + dx, n.y + oy + n.h))
                    line = QGraphicsPathItem(path)
                    line.setPen(QPen(QColor(stroke), 1.6))
                    group.addToGroup(line)
            lh = 16.0
            total = len(n.lines) * lh
            ty = n.y + oy + n.h / 2 - total / 2 + lh * 0.72
            for i, line_text in enumerate(n.lines):
                t = QGraphicsSimpleTextItem(line_text)
                t.setBrush(_TEXT)
                tf = t.font()
                tf.setPointSize(10)
                t.setFont(tf)
                tw = t.boundingRect().width()
                t.setPos(n.x + x_off + (n.w - tw) / 2, ty + i * lh - 8)
                group.addToGroup(t)

        scene.addItem(group)
        x_off += g.width + hgap
    scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
    return scene


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("C++ → блок-схема")
        self.resize(1280, 800)
        self.current_path: Path | None = None

        self.editor = QPlainTextEdit()
        font = QFont("DejaVu Sans Mono, Consolas, monospace")
        font.setPointSize(11)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("Вставьте C++ код здесь…")

        self.view = FlowView()
        self.view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
        )
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.status = StatusWindow(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(splitter)

        self._build_toolbar()
        self._bind_shortcuts()

    # ---- UI setup ----------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = QToolBar()
        act_open = QAction("Открыть…", self)
        act_open.triggered.connect(self.open_file)
        act_save = QAction("Сохранить SVG…", self)
        act_save.triggered.connect(self.save_svg)
        act_drawio = QAction("Сохранить draw.io…", self)
        act_drawio.triggered.connect(self.save_drawio)
        act_run = QAction("Сгенерировать", self)
        act_run.triggered.connect(self.generate)
        act_demo = QAction("Пример", self)
        act_demo.triggered.connect(self.load_example)
        act_zin = QAction("Масштаб +", self)
        act_zin.triggered.connect(self.view.zoom_in)
        act_zout = QAction("Масштаб −", self)
        act_zout.triggered.connect(self.view.zoom_out)
        act_fit = QAction("Вписать", self)
        act_fit.triggered.connect(self.view.zoom_fit)
        act_reset = QAction("100%", self)
        act_reset.triggered.connect(self.view.zoom_reset)
        bar.addAction(act_open)
        bar.addAction(act_save)
        bar.addAction(act_drawio)
        bar.addSeparator()
        bar.addAction(act_run)
        bar.addAction(act_demo)
        bar.addSeparator()
        bar.addAction(act_zin)
        bar.addAction(act_zout)
        bar.addAction(act_fit)
        bar.addAction(act_reset)
        self.layout().insertWidget(0, bar)

    def _bind_shortcuts(self) -> None:
        act = QAction(self)
        act.setShortcut(QKeySequence("Ctrl+Return"))
        act.triggered.connect(self.generate)
        self.addAction(act)

    # ---- actions -----------------------------------------------------------
    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть C++ файл", "", "C++ файлы (*.cpp *.cc *.cxx *.h);;Все (*)"
        )
        if not path:
            return
        p = Path(path)
        try:
            self.editor.setPlainText(p.read_text(encoding="utf-8"))
        except OSError as exc:
            self.status.set_text(f"Не удалось прочитать файл: {exc}")
            return
        self.current_path = p
        self.status.set_text(f"Открыт {p.name}")
        self.generate()

    def save_svg(self) -> None:
        self._save("Сохранить SVG", ".svg", "SVG (*.svg)", convert_to_svg)

    def save_drawio(self) -> None:
        self._save("Сохранить draw.io", ".drawio",
                   "draw.io (*.drawio);;XML (*.xml)", convert_to_drawio)

    def _save(self, title: str, ext: str, filters: str, render) -> None:
        start = str(self.current_path.with_suffix(ext)) if self.current_path \
            else "flowchart" + ext
        path, _ = QFileDialog.getSaveFileName(self, title, start, filters)
        if not path:
            return
        try:
            doc = render(self.editor.toPlainText())
        except ParseError as exc:
            self.status.set_text(f"Ошибка парсинга (строка {exc.line}): {exc}")
            return
        Path(path).write_text(doc, encoding="utf-8")
        self.status.set_text(f"Сохранено: {path}")

    def load_example(self) -> None:
        self.editor.setPlainText(EXAMPLE)
        self.generate()

    def generate(self) -> None:
        source = self.editor.toPlainText()
        self._clear_error()
        try:
            graphs = convert(source)
        except ParseError as exc:
            self.status.set_text(
                f"Ошибка парсинга (строка {exc.line}): {exc}"
            )
            self._highlight_line(exc.line)
            self.view.setScene(QGraphicsScene())
            return
        if not graphs:
            self.status.set_text("В коде не найдено функций")
            self.view.setScene(QGraphicsScene())
            return
        scene = build_scene(graphs)
        self.view.setScene(scene)
        # keep 100% zoom, just scroll back to the top-left corner
        self.view.zoom_reset()
        self.view.verticalScrollBar().setValue(0)
        self.view.horizontalScrollBar().setValue(0)
        self.status.set_text(
            f"Готово: {len(graphs)} функция(и), "
            f"{sum(len(g.nodes) for g in graphs)} блоков. "
            f"Ctrl+колесо — масштаб, кнопка «Вписать» — показать целиком."
        )

    # ---- error highlight -----------------------------------------------------
    def _clear_error(self) -> None:
        self.editor.setExtraSelections([])

    def _highlight_line(self, line: int) -> None:
        if line <= 0:
            return
        cursor = self.editor.textCursor()
        block = self.editor.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return
        cursor.setPosition(block.position())
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        from PyQt6.QtWidgets import QTextEdit
        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format.setBackground(QColor("#fecaca"))
        self.editor.setExtraSelections([sel])


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

