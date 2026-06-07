from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStyledItemDelegate,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .exporter import export_c_header, load_project, save_project
from .generators import (
    GeneratorRange,
    apply_breathe,
    apply_center_bloom_chase,
    apply_center_expand,
    apply_center_gather,
    apply_center_pulse,
    apply_edge_fill,
    apply_flow,
    apply_layered_stack_chase,
    apply_meteor,
    apply_segment_blink,
)
from .model import LightProject, clamp_byte, normalized_range


APP_NAME = "车灯动画编辑器"

PREVIEW_COLOR_PRESETS = [
    ("白光", "#f6f8ff"),
    ("暖白", "#ffe7a6"),
    ("琥珀", "#ffbf45"),
    ("红光", "#ff3b30"),
    ("蓝光", "#3d8bff"),
    ("青色", "#39d5ff"),
]


def _frame_list_text(index: int, duration_ms: int) -> str:
    return f"{index + 1:03d}    {duration_ms} ms"


def _parse_frame_duration_text(text: str) -> int | None:
    cleaned = text.strip().lower()
    if cleaned.endswith("ms"):
        cleaned = cleaned[:-2].strip()
    if not cleaned:
        return None
    token = cleaned.split()[-1]
    try:
        value = int(token)
    except ValueError:
        return None
    if value < 1:
        return None
    return min(value, 5000)


class FrameDurationDelegate(QStyledItemDelegate):
    def createEditor(self, parent: QWidget, option, index):  # type: ignore[override]
        del option, index
        editor = QSpinBox(parent)
        editor.setRange(1, 5000)
        editor.setSuffix(" ms")
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor: QWidget, index) -> None:  # type: ignore[override]
        if isinstance(editor, QSpinBox):
            text = str(index.model().data(index, Qt.ItemDataRole.DisplayRole) or "")
            editor.setValue(_parse_frame_duration_text(text) or 40)
            editor.selectAll()

    def setModelData(self, editor: QWidget, model, index) -> None:  # type: ignore[override]
        if isinstance(editor, QSpinBox):
            model.setData(index, _frame_list_text(index.row(), editor.value()), Qt.ItemDataRole.EditRole)


class LedMatrixWidget(QWidget):
    project_changed = pyqtSignal()
    frame_selected = pyqtSignal(int)
    zoom_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project: LightProject | None = None
        self.selected_frame = 0
        self.brush_value = 255
        self.zoom_percent = 100
        self.base_cell_w = 24
        self.base_cell_h = 28
        self.base_header_h = 34
        self.base_header_w = 56
        self.cell_w = self.base_cell_w
        self.cell_h = self.base_cell_h
        self.header_h = self.base_header_h
        self.header_w = self.base_header_w
        self.drag_value: int | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(500, 320)

    def set_project(self, project: LightProject) -> None:
        self.project = project
        self.selected_frame = min(self.selected_frame, len(project.frames) - 1)
        self._refresh_size()
        self.update()

    def set_selected_frame(self, index: int) -> None:
        if not self.project:
            return
        self.selected_frame = max(0, min(len(self.project.frames) - 1, int(index)))
        self.update()

    def set_brush_value(self, value: int) -> None:
        self.brush_value = clamp_byte(value)

    def set_zoom_percent(self, percent: int) -> None:
        percent = max(50, min(220, int(percent)))
        if percent == self.zoom_percent:
            return
        self.zoom_percent = percent
        self._apply_zoom_metrics()
        self._refresh_size()
        self.zoom_changed.emit(self.zoom_percent)
        self.update()

    def step_zoom(self, delta: int) -> None:
        self.set_zoom_percent(self.zoom_percent + delta)

    def sizeHint(self) -> QSize:
        if not self.project:
            return QSize(860, 520)
        return QSize(
            self.header_w + self.project.led_count * self.cell_w + 20,
            self.header_h + len(self.project.frames) * self.cell_h + 20,
        )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0b0f14"))

        if not self.project:
            return

        self._paint_headers(painter)
        for frame_index, frame in enumerate(self.project.frames):
            y = self.header_h + frame_index * self.cell_h
            row_rect = QRect(0, y, self.width(), self.cell_h)
            if frame_index == self.selected_frame:
                painter.fillRect(row_rect, QColor("#16202b"))
                painter.setPen(QPen(QColor("#3db7ff"), 1))
                painter.drawRect(1, y + 1, self.width() - 3, self.cell_h - 2)

            painter.setPen(QColor("#7f8a96"))
            painter.drawText(QRect(0, y, self.header_w - 8, self.cell_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{frame_index + 1}")

            for led_index, value in enumerate(frame.values):
                x = self.header_w + led_index * self.cell_w
                rect = QRect(x + 2, y + 3, self.cell_w - 4, self.cell_h - 6)
                painter.fillRect(rect, self._color_for_value(value))
                painter.setPen(QPen(QColor("#1d2630"), 1))
                painter.drawRect(rect)
                if value >= 180:
                    painter.setPen(QColor(255, 255, 255, 180))
                    painter.drawPoint(rect.center())

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_value = self.brush_value
            self._apply_at(event.position().toPoint(), self.drag_value)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.drag_value = 0
            self._apply_at(event.position().toPoint(), 0)
            event.accept()
            return

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.drag_value is not None:
            self._apply_at(event.position().toPoint(), self.drag_value)
            event.accept()
            return

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drag_value = None
            event.accept()
            return

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = 10 if event.angleDelta().y() > 0 else -10
            self.step_zoom(delta)
            event.accept()
            return
        super().wheelEvent(event)

    def _apply_at(self, point: QPoint, value: int | None = None) -> None:
        if not self.project:
            return
        frame_index = (point.y() - self.header_h) // self.cell_h
        led_index = (point.x() - self.header_w) // self.cell_w
        if 0 <= frame_index < len(self.project.frames):
            if frame_index != self.selected_frame:
                self.selected_frame = frame_index
                self.frame_selected.emit(frame_index)
            if 0 <= led_index < self.project.led_count:
                self.project.frames[frame_index].values[led_index] = clamp_byte(
                    self.brush_value if value is None else value
                )
                self.project.touch()
                self.project_changed.emit()
                self.update()

    def _paint_headers(self, painter: QPainter) -> None:
        assert self.project
        painter.fillRect(0, 0, self.width(), self.header_h, QColor("#101720"))
        painter.setPen(QColor("#8f9baa"))
        painter.drawText(QRect(0, 0, self.header_w - 8, self.header_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "帧")
        for led_index in range(self.project.led_count):
            x = self.header_w + led_index * self.cell_w
            painter.setPen(QColor("#52606f"))
            if led_index % 5 == 0 or self.project.led_count <= 32:
                painter.drawText(QRect(x, 0, self.cell_w, self.header_h), Qt.AlignmentFlag.AlignCenter, str(led_index))
            painter.setPen(QPen(QColor("#17202a"), 1))
            painter.drawLine(x, self.header_h - 8, x, self.height())

    def _refresh_size(self) -> None:
        self.updateGeometry()
        size = self.sizeHint()
        self.setMinimumSize(size)
        self.resize(size)

    def _apply_zoom_metrics(self) -> None:
        ratio = self.zoom_percent / 100
        self.cell_w = max(10, int(round(self.base_cell_w * ratio)))
        self.cell_h = max(14, int(round(self.base_cell_h * ratio)))
        self.header_h = max(26, int(round(self.base_header_h * ratio)))
        self.header_w = max(46, int(round(self.base_header_w * ratio)))

    @staticmethod
    def _color_for_value(value: int) -> QColor:
        value = clamp_byte(value)
        if value <= 0:
            return QColor("#121820")
        ratio = value / 255
        red = int(30 + ratio * 225)
        green = int(70 + ratio * 170)
        blue = int(95 + ratio * 55)
        return QColor(red, green, blue)


class PreviewStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: list[int] = []
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, values: list[int]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#080c11"))

        if not self.values:
            painter.setPen(QColor("#66717f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无帧数据")
            return

        margin = 18
        gap = 4
        width = self.width() - margin * 2
        cell_w = max(6, int((width - gap * (len(self.values) - 1)) / max(1, len(self.values))))
        cell_h = 34
        y = (self.height() - cell_h) // 2
        for index, value in enumerate(self.values):
            x = margin + index * (cell_w + gap)
            rect = QRect(x, y, cell_w, cell_h)
            gradient = QLinearGradient(
                float(rect.left()),
                float(rect.top()),
                float(rect.right()),
                float(rect.bottom()),
            )
            color = LedMatrixWidget._color_for_value(value)
            gradient.setColorAt(0, color.lighter(130))
            gradient.setColorAt(1, color.darker(130))
            painter.fillRect(rect, gradient)
            painter.setPen(QPen(QColor("#27313c"), 1))
            painter.drawRoundedRect(rect, 4, 4)


class PlaybackPreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: list[int] = []
        self.frame_index = 0
        self.frame_count = 0
        self.preview_color = QColor(PREVIEW_COLOR_PRESETS[0][1])
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_frame(self, values: list[int], frame_index: int, frame_count: int) -> None:
        self.values = list(values)
        self.frame_index = frame_index
        self.frame_count = frame_count
        self.update()

    def set_preview_color(self, color: QColor) -> None:
        if color.isValid():
            self.preview_color = QColor(color)
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#05080d"))

        if not self.values:
            painter.setPen(QColor("#66717f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无预览数据")
            return

        margin = 28
        width = max(1, self.width() - margin * 2)
        gap = 5 if len(self.values) <= 64 else 2
        cell_w = max(5, int((width - gap * (len(self.values) - 1)) / max(1, len(self.values))))
        cell_h = max(34, min(96, self.height() - 78))
        y = (self.height() - cell_h) // 2 + 8

        painter.setPen(QPen(QColor("#172635"), 1))
        baseline_y = min(self.height() - 38, y + cell_h + 18)
        painter.drawLine(margin, baseline_y, self.width() - margin, baseline_y)

        for index, value in enumerate(self.values):
            x = margin + index * (cell_w + gap)
            rect = QRect(x, y, cell_w, cell_h)
            value = clamp_byte(value)
            color = self._color_for_value(value)
            if value > 0:
                glow_alpha = min(150, 35 + value // 2)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), glow_alpha))
                painter.drawRoundedRect(rect.adjusted(-4, -4, 4, 4), 10, 10)

            if value <= 0:
                painter.fillRect(rect, color)
            else:
                gradient = QLinearGradient(
                    float(rect.left()),
                    float(rect.top()),
                    float(rect.right()),
                    float(rect.bottom()),
                )
                gradient.setColorAt(0, color.lighter(135))
                gradient.setColorAt(1, color.darker(140))
                painter.fillRect(rect, gradient)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#27313c"), 1))
            painter.drawRoundedRect(rect, 5, 5)

        painter.setPen(QColor("#6d7d8f"))
        painter.drawText(
            QRect(margin, baseline_y + 6, self.width() - margin * 2, 20),
            Qt.AlignmentFlag.AlignCenter,
            f"Frame {self.frame_index + 1} / {self.frame_count}",
        )

    def _color_for_value(self, value: int) -> QColor:
        value = clamp_byte(value)
        if value <= 0:
            return QColor("#000000")
        ratio = value / 255
        return QColor(
            int(self.preview_color.red() * ratio),
            int(self.preview_color.green() * ratio),
            int(self.preview_color.blue() * ratio),
        )


class PlaybackPreviewWindow(QDialog):
    def __init__(self, project: LightProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.current_frame = 0
        self.is_playing = False
        self.preview_color = QColor(PREVIEW_COLOR_PRESETS[0][1])
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_frame)

        self.setWindowTitle("播放预览")
        self.resize(980, 300)
        self.setMinimumSize(640, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("播放预览")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.status_label = QLabel()
        self.status_label.setObjectName("statusText")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self.canvas = PlaybackPreviewCanvas()
        self.canvas.set_preview_color(self.preview_color)
        layout.addWidget(self.canvas, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("颜色"))
        self.color_combo = QComboBox()
        for label, _ in PREVIEW_COLOR_PRESETS:
            self.color_combo.addItem(label)
        self.color_combo.currentIndexChanged.connect(self._apply_preset_color)
        controls.addWidget(self.color_combo)
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(22, 22)
        controls.addWidget(self.color_swatch)
        custom_color_button = QPushButton("自定义")
        custom_color_button.clicked.connect(self.choose_preview_color)
        controls.addWidget(custom_color_button)
        controls.addStretch(1)
        restart_button = QPushButton("从头")
        restart_button.clicked.connect(self.restart)
        controls.addWidget(restart_button)
        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self.toggle_playback)
        controls.addWidget(self.play_button)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        controls.addWidget(close_button)
        layout.addLayout(controls)

        self.set_preview_color(self.preview_color)
        self.refresh()

    def set_project(self, project: LightProject) -> None:
        self.project = project
        self.current_frame = min(self.current_frame, len(self.project.frames) - 1)
        self.refresh()

    def set_frame_index(self, frame_index: int) -> None:
        if not self.project.frames:
            return
        self.current_frame = max(0, min(len(self.project.frames) - 1, int(frame_index)))
        self.refresh()

    def refresh(self) -> None:
        if not self.project.frames:
            self.canvas.set_frame([], 0, 0)
            self.status_label.setText("0 ms")
            return
        self.current_frame = max(0, min(len(self.project.frames) - 1, self.current_frame))
        frame = self.project.frames[self.current_frame]
        self.canvas.set_frame(frame.values, self.current_frame, len(self.project.frames))
        self.status_label.setText(
            f"{frame.duration_ms} ms | {self.project.led_count} LEDs | {self.project.total_duration_ms()} ms"
        )

    def choose_preview_color(self) -> None:
        color = QColorDialog.getColor(self.preview_color, self, "选择预览颜色")
        if color.isValid():
            self.set_preview_color(color)

    def set_preview_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.preview_color = QColor(color)
        self.canvas.set_preview_color(self.preview_color)
        if hasattr(self, "color_swatch"):
            self.color_swatch.setStyleSheet(
                f"background: {self.preview_color.name()}; border: 1px solid #2b3a4c; border-radius: 4px;"
            )
        for index, (_, preset_hex) in enumerate(PREVIEW_COLOR_PRESETS):
            if QColor(preset_hex).name() == self.preview_color.name():
                self.color_combo.blockSignals(True)
                self.color_combo.setCurrentIndex(index)
                self.color_combo.blockSignals(False)
                break

    def _apply_preset_color(self, index: int) -> None:
        if 0 <= index < len(PREVIEW_COLOR_PRESETS):
            self.set_preview_color(QColor(PREVIEW_COLOR_PRESETS[index][1]))

    def toggle_playback(self) -> None:
        self.is_playing = not self.is_playing
        self.play_button.setText("暂停" if self.is_playing else "播放")
        if self.is_playing:
            self._start_timer_for_current_frame()
        else:
            self.timer.stop()

    def restart(self) -> None:
        self.current_frame = 0
        self.refresh()
        if self.is_playing:
            self._start_timer_for_current_frame()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.timer.stop()
        self.is_playing = False
        self.play_button.setText("播放")
        super().closeEvent(event)

    def _advance_frame(self) -> None:
        if not self.project.frames:
            return
        self.current_frame = (self.current_frame + 1) % len(self.project.frames)
        self.refresh()
        if self.is_playing:
            self._start_timer_for_current_frame()

    def _start_timer_for_current_frame(self) -> None:
        if not self.project.frames:
            return
        self.timer.start(self.project.frames[self.current_frame].duration_ms)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = LightProject.create()
        self.current_path: Path | None = None
        self.current_frame = 0
        self.is_dirty = False
        self.is_playing = False
        self.frame_clipboard: dict[str, object] | None = None
        self.selection_clipboard: dict[str, object] | None = None
        self.playback_window: PlaybackPreviewWindow | None = None
        self.event_filter_installed = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_preview)

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self._build_ui()
        self._apply_style()
        self._sync_all()
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
            self.event_filter_installed = True

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        root.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_timeline_panel())
        splitter.addWidget(self._build_workspace_panel())
        splitter.addWidget(self._build_inspector_panel())
        splitter.setSizes([220, 860, 320])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self._build_menu()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        actions = [
            ("新建", self.new_project),
            ("打开工程...", self.open_project),
            ("保存工程", self.save_project),
            ("另存为...", self.save_project_as),
            ("导出 C 头文件...", self.export_header_file),
        ]
        for label, handler in actions:
            action = QAction(label, self)
            action.triggered.connect(handler)
            file_menu.addAction(action)

        edit_menu = self.menuBar().addMenu("编辑")
        edit_actions = [
            ("复制当前帧    Ctrl+C", self.copy_current_frame),
            ("粘贴到当前帧    Ctrl+V", self.paste_current_frame),
            ("复制选区    Ctrl+Shift+C", self.copy_selection),
            ("粘贴到选区    Ctrl+Shift+V", self.paste_selection),
        ]
        for label, handler in edit_actions:
            action = QAction(label, self)
            action.triggered.connect(handler)
            edit_menu.addAction(action)

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        title = QLabel("车灯动画编辑器")
        title.setObjectName("appTitle")
        subtitle = QLabel("一维 LED 灰度动画工作站")
        subtitle.setObjectName("subtitle")

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.led_count_spin = QSpinBox()
        self.led_count_spin.setRange(1, 256)
        self.led_count_spin.setPrefix("LED ")
        self.led_count_spin.valueChanged.connect(self.change_led_count)
        layout.addWidget(self.led_count_spin)

        self.frame_count_spin = QSpinBox()
        self.frame_count_spin.setRange(1, 9999)
        self.frame_count_spin.setPrefix("帧 ")
        self.frame_count_spin.valueChanged.connect(self.change_frame_count)
        layout.addWidget(self.frame_count_spin)

        for text, handler in [
            ("新建", self.new_project),
            ("打开", self.open_project),
            ("保存", self.save_project),
            ("导出 .h", self.export_header_file),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            layout.addWidget(button)

        return bar

    def _build_timeline_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel("帧时间轴")
        label.setObjectName("panelTitle")
        layout.addWidget(label)

        self.frame_list = QListWidget()
        self.frame_list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.frame_list.setItemDelegate(FrameDurationDelegate(self.frame_list))
        self.frame_list.currentRowChanged.connect(self.select_frame)
        self.frame_list.itemChanged.connect(self.change_frame_duration_from_item)
        layout.addWidget(self.frame_list, 1)

        row = QHBoxLayout()
        for text, handler in [
            ("+", self.add_frame),
            ("复制", self.duplicate_frame),
            ("插入", self.insert_frame),
            ("删除", self.delete_frame),
        ]:
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(handler)
            row.addWidget(button)
        layout.addLayout(row)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 5000)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.valueChanged.connect(self.change_frame_duration)
        layout.addWidget(QLabel("当前帧时长"))
        layout.addWidget(self.duration_spin)

        self.status_label = QLabel()
        self.status_label.setObjectName("statusText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        return panel

    def _build_workspace_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("workspace")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("LED 灰度矩阵")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch(1)

        header.addWidget(QLabel("缩放"))
        zoom_out = QToolButton()
        zoom_out.setText("−")
        zoom_out.clicked.connect(lambda: self.zoom_matrix_by(-10))
        header.addWidget(zoom_out)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 220)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.set_matrix_zoom)
        header.addWidget(self.zoom_slider)

        zoom_in = QToolButton()
        zoom_in.setText("+")
        zoom_in.clicked.connect(lambda: self.zoom_matrix_by(10))
        header.addWidget(zoom_in)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoomLabel")
        header.addWidget(self.zoom_label)

        reset_zoom = QToolButton()
        reset_zoom.setText("100%")
        reset_zoom.clicked.connect(lambda: self.set_matrix_zoom(100))
        header.addWidget(reset_zoom)

        fit_zoom = QPushButton("适配")
        fit_zoom.clicked.connect(self.fit_matrix_to_view)
        header.addWidget(fit_zoom)

        preview_window_button = QPushButton("预览窗口")
        preview_window_button.clicked.connect(self.open_playback_preview)
        header.addWidget(preview_window_button)

        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self.toggle_playback)
        header.addWidget(self.play_button)
        layout.addLayout(header)

        self.matrix = LedMatrixWidget()
        self.matrix.project_changed.connect(self.mark_dirty_and_refresh)
        self.matrix.frame_selected.connect(self.select_frame)
        self.matrix.zoom_changed.connect(self.sync_zoom_controls)
        self.matrix_scroll = QScrollArea()
        self.matrix_scroll.setWidget(self.matrix)
        self.matrix_scroll.setWidgetResizable(False)
        self.matrix_scroll.setObjectName("matrixScroll")
        layout.addWidget(self.matrix_scroll, 1)

        self.preview = PreviewStrip()
        layout.addWidget(self.preview)

        return panel

    def _build_inspector_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("控制台")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("inspectorScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("inspectorContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_brush_group())
        content_layout.addWidget(self._build_range_group())
        content_layout.addWidget(self._build_generator_group())
        content_layout.addWidget(self._build_export_group())
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return panel

    def _build_brush_group(self) -> QGroupBox:
        group = QGroupBox("画笔")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        self.brush_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_slider.setRange(0, 255)
        self.brush_slider.setValue(255)
        self.brush_spin = QSpinBox()
        self.brush_spin.setRange(0, 255)
        self.brush_spin.setValue(255)
        self.brush_slider.valueChanged.connect(self.brush_spin.setValue)
        self.brush_spin.valueChanged.connect(self.brush_slider.setValue)
        self.brush_spin.valueChanged.connect(self.set_brush_value)

        layout.addWidget(QLabel("灰度"), 0, 0)
        layout.addWidget(self.brush_slider, 0, 1)
        layout.addWidget(self.brush_spin, 0, 2)

        fill_button = QPushButton("填充选区")
        fill_button.clicked.connect(self.fill_selection)
        clear_button = QPushButton("清空选区")
        clear_button.clicked.connect(self.clear_selection)
        copy_button = QPushButton("复制上一帧")
        copy_button.clicked.connect(self.copy_previous_frame)
        layout.addWidget(fill_button, 1, 0, 1, 3)
        layout.addWidget(clear_button, 2, 0, 1, 3)
        layout.addWidget(copy_button, 3, 0, 1, 3)
        return group

    def _build_range_group(self) -> QGroupBox:
        group = QGroupBox("选区")
        layout = QGridLayout(group)
        self.frame_start_spin = self._spin(1, 1, 9999)
        self.frame_end_spin = self._spin(9999, 1, 9999)
        self.led_start_spin = self._spin(0, 0, 255)
        self.led_end_spin = self._spin(255, 0, 255)

        layout.addWidget(QLabel("起始帧"), 0, 0)
        layout.addWidget(self.frame_start_spin, 0, 1)
        layout.addWidget(QLabel("结束帧"), 1, 0)
        layout.addWidget(self.frame_end_spin, 1, 1)
        layout.addWidget(QLabel("起始 LED"), 2, 0)
        layout.addWidget(self.led_start_spin, 2, 1)
        layout.addWidget(QLabel("结束 LED"), 3, 0)
        layout.addWidget(self.led_end_spin, 3, 1)
        return group

    def _build_generator_group(self) -> QGroupBox:
        group = QGroupBox("生成器")
        group.setMinimumHeight(292)
        layout = QGridLayout(group)
        self.generator_combo = QComboBox()
        self.generator_combo.addItems(
            [
                "流水",
                "流星",
                "双侧聚集",
                "全段呼吸",
                "中心点亮",
                "中心外扩",
                "两侧填充",
                "分段闪烁",
                "中心扩张追光",
                "分层堆叠追光",
            ]
        )
        self.gen_start_spin = self._spin(0, 0, 255)
        self.gen_end_spin = self._spin(255, 0, 255)
        self.gen_peak_spin = self._spin(255, 0, 255)
        self.gen_tail_spin = self._spin(5, 0, 64)
        self.gen_center_width_spin = self._spin(2, 1, 64)
        self.gen_hold_spin = self._spin(2, 0, 128)

        rows = [
            ("类型", self.generator_combo),
            ("起点 LED", self.gen_start_spin),
            ("终点 LED", self.gen_end_spin),
            ("峰值", self.gen_peak_spin),
            ("尾巴长度", self.gen_tail_spin),
            ("中心宽度", self.gen_center_width_spin),
            ("保持帧数", self.gen_hold_spin),
        ]
        for row, (label, widget) in enumerate(rows):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(widget, row, 1)

        button = QPushButton("应用生成器")
        button.clicked.connect(self.apply_generator)
        layout.addWidget(button, len(rows), 0, 1, 2)
        return group

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("C 导出")
        group.setMinimumHeight(250)
        layout = QVBoxLayout(group)
        self.export_text = QTextEdit()
        self.export_text.setReadOnly(True)
        self.export_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.export_text.setMinimumHeight(150)
        layout.addWidget(self.export_text, 1)

        row = QHBoxLayout()
        copy_button = QPushButton("复制")
        copy_button.clicked.connect(self.copy_export_to_clipboard)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_export)
        row.addWidget(copy_button)
        row.addWidget(refresh_button)
        layout.addLayout(row)
        return group

    def _spin(self, value: int, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #080c11;
                color: #d7dde6;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 12px;
            }
            QMenuBar, QMenu {
                background: #0d131b;
                color: #d7dde6;
                border: 1px solid #1d2733;
            }
            QFrame#topBar {
                background: #101720;
                border: 1px solid #1f2a36;
                border-radius: 8px;
            }
            QFrame#sidePanel {
                background: #0f151d;
                border: 1px solid #1d2733;
                border-radius: 8px;
            }
            QFrame#workspace {
                background: #080c11;
                border: none;
            }
            QLabel#appTitle {
                color: #f3f7fb;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#subtitle, QLabel#statusText {
                color: #7f8b99;
            }
            QLabel#zoomLabel {
                color: #9fb0c3;
                min-width: 42px;
            }
            QLabel#panelTitle {
                color: #f1f5f9;
                font-size: 15px;
                font-weight: 700;
            }
            QGroupBox {
                border: 1px solid #202b38;
                border-radius: 8px;
                margin-top: 10px;
                padding: 12px 10px 10px 10px;
                color: #aab4c0;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton, QToolButton {
                background: #182231;
                color: #e8edf4;
                border: 1px solid #2b3a4c;
                border-radius: 7px;
                padding: 7px 10px;
                min-height: 22px;
            }
            QPushButton:hover, QToolButton:hover {
                background: #223149;
                border-color: #3db7ff;
            }
            QPushButton:pressed, QToolButton:pressed {
                background: #0f88c8;
            }
            QSpinBox, QComboBox {
                background: #0b1017;
                color: #e6edf5;
                border: 1px solid #283545;
                border-radius: 6px;
                padding: 5px 8px;
                min-height: 22px;
            }
            QListWidget {
                background: #0a0f15;
                border: 1px solid #202a36;
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 8px;
                border-bottom: 1px solid #141d27;
            }
            QListWidget::item:selected {
                background: #16324a;
                color: #ffffff;
            }
            QScrollArea#matrixScroll, QTextEdit {
                background: #0a0f15;
                border: 1px solid #202a36;
                border-radius: 8px;
            }
            QTextEdit {
                color: #c9d6e2;
                font-family: Consolas, "Cascadia Mono", monospace;
                font-size: 11px;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #1b2632;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                margin: -6px 0;
                background: #3db7ff;
                border-radius: 8px;
            }
            QSplitter::handle {
                background: #080c11;
            }
            """
        )

    def _sync_all(self) -> None:
        self.project.normalize()
        self.led_count_spin.blockSignals(True)
        self.led_count_spin.setValue(self.project.led_count)
        self.led_count_spin.blockSignals(False)
        self.frame_count_spin.blockSignals(True)
        self.frame_count_spin.setValue(len(self.project.frames))
        self.frame_count_spin.blockSignals(False)

        self._sync_frame_list()
        self._sync_ranges()
        self.matrix.set_project(self.project)
        self.select_frame(min(self.current_frame, len(self.project.frames) - 1))
        self.refresh_export()
        self.refresh_playback_preview()

    def _sync_frame_list(self) -> None:
        self.frame_list.blockSignals(True)
        self.frame_list.clear()
        for index, frame in enumerate(self.project.frames):
            item = QListWidgetItem(_frame_list_text(index, frame.duration_ms))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.frame_list.addItem(item)
        self.frame_list.setCurrentRow(self.current_frame)
        self.frame_list.blockSignals(False)

    def _sync_ranges(self) -> None:
        frame_count = len(self.project.frames)
        led_last = max(0, self.project.led_count - 1)
        for spin in (self.frame_start_spin, self.frame_end_spin):
            spin.setRange(1, frame_count)
            spin.setValue(max(1, min(spin.value(), frame_count)))

        for spin in (self.led_start_spin, self.led_end_spin, self.gen_start_spin, self.gen_end_spin):
            spin.setRange(0, led_last)
            spin.setValue(max(0, min(spin.value(), led_last)))

        if self.led_end_spin.value() < self.led_start_spin.value():
            self.led_end_spin.setValue(self.led_start_spin.value())
        if self.gen_end_spin.value() < self.gen_start_spin.value():
            self.gen_end_spin.setValue(self.gen_start_spin.value())

    def select_frame(self, row: int) -> None:
        if row < 0 or row >= len(self.project.frames):
            return
        self.current_frame = row
        self.frame_list.blockSignals(True)
        self.frame_list.setCurrentRow(row)
        self.frame_list.blockSignals(False)
        self.duration_spin.blockSignals(True)
        self.duration_spin.setValue(self.project.frames[row].duration_ms)
        self.duration_spin.blockSignals(False)
        self.matrix.set_selected_frame(row)
        self.preview.set_values(list(self.project.frames[row].values))
        if self.playback_window and self.playback_window.isVisible() and not self.playback_window.is_playing:
            self.playback_window.set_frame_index(row)
        self._update_status()

    def set_brush_value(self, value: int) -> None:
        self.matrix.set_brush_value(value)

    def set_matrix_zoom(self, percent: int) -> None:
        if not hasattr(self, "matrix"):
            return
        self.matrix.set_zoom_percent(percent)

    def zoom_matrix_by(self, delta: int) -> None:
        self.set_matrix_zoom(self.matrix.zoom_percent + delta)

    def sync_zoom_controls(self, percent: int) -> None:
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(percent)
        self.zoom_slider.blockSignals(False)
        self.zoom_label.setText(f"{percent}%")

    def fit_matrix_to_view(self) -> None:
        if not self.project.frames:
            return
        viewport = self.matrix_scroll.viewport().size()
        base_width = self.matrix.base_header_w + self.project.led_count * self.matrix.base_cell_w + 20
        base_height = self.matrix.base_header_h + len(self.project.frames) * self.matrix.base_cell_h + 20
        width_ratio = max(1, viewport.width() - 24) / max(1, base_width)
        height_ratio = max(1, viewport.height() - 24) / max(1, base_height)
        percent = int(min(width_ratio, height_ratio) * 100)
        self.set_matrix_zoom(max(50, min(220, percent)))

    def open_playback_preview(self) -> None:
        if self.playback_window is None:
            self.playback_window = PlaybackPreviewWindow(self.project, self)
        else:
            self.playback_window.set_project(self.project)
        self.playback_window.set_frame_index(self.current_frame)
        self.playback_window.show()
        self.playback_window.raise_()
        self.playback_window.activateWindow()

    def refresh_playback_preview(self) -> None:
        if self.playback_window and self.playback_window.isVisible():
            self.playback_window.set_project(self.project)

    def change_led_count(self, value: int) -> None:
        self.project.set_led_count(value)
        self.mark_dirty_and_refresh()

    def change_frame_count(self, value: int) -> None:
        self.project.set_frame_count(value)
        self.current_frame = min(self.current_frame, len(self.project.frames) - 1)
        self.mark_dirty_and_refresh()

    def change_frame_duration(self, value: int) -> None:
        self.project.set_duration(self.current_frame, value)
        self.mark_dirty_and_refresh()

    def change_frame_duration_from_item(self, item: QListWidgetItem) -> None:
        row = self.frame_list.row(item)
        if row < 0 or row >= len(self.project.frames):
            return
        value = _parse_frame_duration_text(item.text())
        if value is None:
            self._restore_frame_list_item(row)
            return
        self.current_frame = row
        self.project.set_duration(row, value)
        self.mark_dirty_and_refresh()

    def _restore_frame_list_item(self, row: int) -> None:
        item = self.frame_list.item(row)
        if item is None:
            return
        self.frame_list.blockSignals(True)
        item.setText(_frame_list_text(row, self.project.frames[row].duration_ms))
        self.frame_list.blockSignals(False)

    def add_frame(self) -> None:
        self.current_frame = self.project.add_frame()
        self.mark_dirty_and_refresh()

    def insert_frame(self) -> None:
        self.current_frame = self.project.insert_frame(self.current_frame)
        self.mark_dirty_and_refresh()

    def duplicate_frame(self) -> None:
        self.current_frame = self.project.duplicate_frame(self.current_frame)
        self.mark_dirty_and_refresh()

    def delete_frame(self) -> None:
        self.current_frame = self.project.delete_frame(self.current_frame)
        self.mark_dirty_and_refresh()

    def copy_previous_frame(self) -> None:
        self.project.copy_previous_frame(self.current_frame)
        self.mark_dirty_and_refresh()

    def fill_selection(self) -> None:
        area = self._selection_area()
        self.project.fill_range(
            area.frame_start,
            area.frame_end,
            area.led_start,
            area.led_end,
            self.brush_spin.value(),
        )
        self.mark_dirty_and_refresh()

    def clear_selection(self) -> None:
        area = self._selection_area()
        self.project.clear_range(area.frame_start, area.frame_end, area.led_start, area.led_end)
        self.mark_dirty_and_refresh()

    def apply_generator(self) -> None:
        area = self._selection_area()
        gen_type = self.generator_combo.currentText()
        if gen_type == "流水":
            apply_flow(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
            )
        elif gen_type == "流星":
            apply_meteor(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
            )
        elif gen_type == "双侧聚集":
            apply_center_gather(
                self.project,
                area,
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        elif gen_type == "全段呼吸":
            apply_breathe(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_hold_spin.value(),
            )
        elif gen_type == "中心点亮":
            apply_center_pulse(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        elif gen_type == "中心外扩":
            apply_center_expand(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        elif gen_type == "两侧填充":
            apply_edge_fill(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        elif gen_type == "分段闪烁":
            apply_segment_blink(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        elif gen_type == "中心扩张追光":
            apply_center_bloom_chase(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        else:
            apply_layered_stack_chase(
                self.project,
                area,
                self.gen_start_spin.value(),
                self.gen_end_spin.value(),
                self.gen_peak_spin.value(),
                self.gen_tail_spin.value(),
                self.gen_center_width_spin.value(),
                self.gen_hold_spin.value(),
            )
        self.mark_dirty_and_refresh()

    def toggle_playback(self) -> None:
        self.is_playing = not self.is_playing
        self.play_button.setText("暂停" if self.is_playing else "播放")
        if self.is_playing:
            self.timer.start(self.project.frames[self.current_frame].duration_ms)
        else:
            self.timer.stop()

    def _advance_preview(self) -> None:
        self.current_frame = (self.current_frame + 1) % len(self.project.frames)
        self.select_frame(self.current_frame)
        if self.is_playing:
            self.timer.start(self.project.frames[self.current_frame].duration_ms)

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.project = LightProject.create(self.led_count_spin.value(), self.frame_count_spin.value())
        self.current_path = None
        self.current_frame = 0
        self.is_dirty = False
        self._sync_all()

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开工程", "", "车灯动画工程 (*.json)")
        if not path:
            return
        try:
            self.project = load_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", str(exc))
            return
        self.current_path = Path(path)
        self.current_frame = 0
        self.is_dirty = False
        self._sync_all()

    def save_project(self) -> None:
        if not self.current_path:
            self.save_project_as()
            return
        save_project(self.project, self.current_path)
        self.is_dirty = False
        self._update_status()

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存工程", "light_animation.json", "车灯动画工程 (*.json)")
        if not path:
            return
        self.current_path = Path(path)
        self.save_project()

    def export_header_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 C 头文件", "light_animation.h", "C 头文件 (*.h)")
        if not path:
            return
        Path(path).write_text(export_c_header(self.project), encoding="utf-8")

    def copy_export_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self.export_text.toPlainText())

    def refresh_export(self) -> None:
        self.export_text.setPlainText(export_c_header(self.project))

    def copy_current_frame(self) -> None:
        frame = self.project.frames[self.current_frame]
        self.frame_clipboard = {
            "duration_ms": frame.duration_ms,
            "values": list(frame.values),
        }
        self._update_status("已复制当前帧")

    def paste_current_frame(self) -> None:
        if not self.frame_clipboard:
            self._update_status("没有可粘贴的帧")
            return
        values = list(self.frame_clipboard.get("values", []))
        target = self.project.frames[self.current_frame]
        target.duration_ms = int(self.frame_clipboard.get("duration_ms", target.duration_ms))
        target.values = [clamp_byte(value) for value in values[: self.project.led_count]]
        if len(target.values) < self.project.led_count:
            target.values.extend([0] * (self.project.led_count - len(target.values)))
        self.project.touch()
        self.mark_dirty_and_refresh()
        self._update_status("已粘贴到当前帧")

    def copy_selection(self) -> None:
        area = self._selection_area()
        frame_indexes = list(normalized_range(area.frame_start, area.frame_end, len(self.project.frames)))
        led_indexes = list(normalized_range(area.led_start, area.led_end, self.project.led_count))
        values = [
            [self.project.frames[frame_index].values[led_index] for led_index in led_indexes]
            for frame_index in frame_indexes
        ]
        self.selection_clipboard = {
            "frame_count": len(frame_indexes),
            "led_count": len(led_indexes),
            "values": values,
        }
        self._update_status(f"已复制选区 {len(frame_indexes)} 帧 x {len(led_indexes)} LED")

    def paste_selection(self) -> None:
        if not self.selection_clipboard:
            self._update_status("没有可粘贴的选区")
            return
        area = self._selection_area()
        target_frames = list(normalized_range(area.frame_start, area.frame_end, len(self.project.frames)))
        target_leds = list(normalized_range(area.led_start, area.led_end, self.project.led_count))
        values = self.selection_clipboard.get("values", [])
        for frame_offset, frame_index in enumerate(target_frames):
            if frame_offset >= len(values):
                break
            row = values[frame_offset]
            if not isinstance(row, list):
                continue
            for led_offset, led_index in enumerate(target_leds):
                if led_offset >= len(row):
                    break
                self.project.frames[frame_index].values[led_index] = clamp_byte(row[led_offset])
        self.project.touch()
        self.mark_dirty_and_refresh()
        self._update_status("已粘贴到选区")

    def mark_dirty_and_refresh(self) -> None:
        self.is_dirty = True
        self._sync_frame_list()
        self._sync_ranges()
        self.matrix.set_project(self.project)
        self.select_frame(min(self.current_frame, len(self.project.frames) - 1))
        self.refresh_export()
        self.refresh_playback_preview()

    def _selection_area(self) -> GeneratorRange:
        return GeneratorRange(
            self.frame_start_spin.value() - 1,
            self.frame_end_spin.value() - 1,
            self.led_start_spin.value(),
            self.led_end_spin.value(),
        )

    def _confirm_discard(self) -> bool:
        if not self.is_dirty:
            return True
        result = QMessageBox.question(
            self,
            "未保存修改",
            "当前工程有未保存修改，是否放弃这些修改？",
        )
        return result == QMessageBox.StandardButton.Yes

    def eventFilter(self, source, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.KeyPress and self._handle_copy_paste_shortcut(event):
            return True
        return super().eventFilter(source, event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        app = QApplication.instance()
        if app and self.event_filter_installed:
            app.removeEventFilter(self)
            self.event_filter_installed = False
        if self.playback_window:
            self.playback_window.close()
        super().closeEvent(event)

    def _handle_copy_paste_shortcut(self, event) -> bool:
        if self._focus_in_export_text():
            return False
        modifiers = event.modifiers()
        if not modifiers & Qt.KeyboardModifier.ControlModifier:
            return False
        if modifiers & Qt.KeyboardModifier.AltModifier:
            return False

        key = event.key()
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_C:
            self.copy_selection() if shift else self.copy_current_frame()
            event.accept()
            return True
        if key == Qt.Key.Key_V:
            self.paste_selection() if shift else self.paste_current_frame()
            event.accept()
            return True
        return False

    def _focus_in_export_text(self) -> bool:
        focus = QApplication.focusWidget()
        return bool(focus and (focus is self.export_text or self.export_text.isAncestorOf(focus)))

    def _update_status(self, message: str | None = None) -> None:
        name = self.current_path.name if self.current_path else "未保存工程"
        dirty = "已修改" if self.is_dirty else "已保存"
        lines = [
            name,
            f"{len(self.project.frames)} 帧 | {self.project.led_count} LEDs | "
            f"{self.project.total_duration_ms()} ms | {dirty}",
        ]
        if message:
            lines.append(message)
        self.status_label.setText("\n".join(lines))


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Light Tool")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
