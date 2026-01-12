from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSpinBox,
    QHBoxLayout,
    QComboBox,
    QPushButton,
    QDoubleSpinBox,
    QCheckBox,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal


class SelectOnHoverPanel(QWidget):
    """
    Compact control panel implemented as a QWidget so it can be embedded into a QWidgetAction
    and shown inside a QMenu (popup under the toolbar button). This contains controls for:
    - Units (pixels/map units)
    - Radius inputs
    - Restrict mode (visible/all/active layers)
    - Selection mode (add/replace/toggle)
    - Visual feedback options
    - Rebuild spatial indexes
    - Clear selection
    """
    radiusChanged = pyqtSignal(int, float, str)  # pixel_radius, mapunit_radius, unit_mode
    optionsChanged = pyqtSignal(str, str)  # restrict_mode, selection_mode
    visualFeedbackChanged = pyqtSignal(bool)  # show_rubber_band
    rebuildIndexesRequested = pyqtSignal()
    clearSelectionRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        self.setLayout(layout)

        # Units selector
        label_units = QLabel("<b>Radius Settings</b>")
        layout.addWidget(label_units)
        
        units_label = QLabel("Units for radius:")
        layout.addWidget(units_label)
        self.units_combo = QComboBox()
        self.units_combo.addItems(["Pixels", "Map units"])
        self.units_combo.currentIndexChanged.connect(self._on_units_changed)
        layout.addWidget(self.units_combo)

        # Pixel radius
        label_pix = QLabel("Radius (pixels):")
        layout.addWidget(label_pix)
        self.spin_pixels = QSpinBox()
        self.spin_pixels.setRange(1, 2000)
        self.spin_pixels.setValue(20)
        self.spin_pixels.setSingleStep(1)
        self.spin_pixels.valueChanged.connect(self._on_pixel_changed)
        layout.addWidget(self.spin_pixels)

        # Map-unit radius
        label_map = QLabel("Radius (map units):")
        layout.addWidget(label_map)
        self.spin_mapunits = QDoubleSpinBox()
        self.spin_mapunits.setRange(0.000001, 1e9)
        self.spin_mapunits.setDecimals(6)
        self.spin_mapunits.setValue(10.0)
        self.spin_mapunits.setSingleStep(1.0)
        self.spin_mapunits.valueChanged.connect(self._on_mapunit_changed)
        layout.addWidget(self.spin_mapunits)

        # Separator
        layout.addSpacing(10)
        label_selection = QLabel("<b>Selection Settings</b>")
        layout.addWidget(label_selection)

        # Restrict mode selector
        label_restrict = QLabel("Restrict selection to:")
        layout.addWidget(label_restrict)
        self.restrict_combo = QComboBox()
        self.restrict_combo.addItem("Visible & selectable layers", "visible")
        self.restrict_combo.addItem("All selectable layers", "all")
        self.restrict_combo.addItem("Active layer only", "active")
        self.restrict_combo.currentIndexChanged.connect(self._on_options_changed)
        layout.addWidget(self.restrict_combo)

        # Selection mode selector
        label_mode = QLabel("Selection mode:")
        layout.addWidget(label_mode)
        self.selection_mode_combo = QComboBox()
        self.selection_mode_combo.addItem("Add to selection", "add")
        self.selection_mode_combo.addItem("Replace selection", "replace")
        self.selection_mode_combo.addItem("Toggle selection", "toggle")
        self.selection_mode_combo.currentIndexChanged.connect(self._on_options_changed)
        layout.addWidget(self.selection_mode_combo)

        # Visual feedback
        layout.addSpacing(10)
        label_visual = QLabel("<b>Visual Feedback</b>")
        layout.addWidget(label_visual)
        
        self.show_rubber_band_cb = QCheckBox("Show selection circle on map")
        self.show_rubber_band_cb.setChecked(True)
        self.show_rubber_band_cb.stateChanged.connect(self._on_visual_feedback_changed)
        layout.addWidget(self.show_rubber_band_cb)

        # Actions
        layout.addSpacing(10)
        label_actions = QLabel("<b>Actions</b>")
        layout.addWidget(label_actions)

        # Rebuild indexes button
        self.rebuild_btn = QPushButton("Rebuild spatial indexes")
        self.rebuild_btn.clicked.connect(self._on_rebuild_clicked)
        layout.addWidget(self.rebuild_btn)

        # Clear selection button
        self.clear_btn = QPushButton("Clear all selections")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        layout.addWidget(self.clear_btn)

        # Keep the widget compact
        layout.addStretch(0)

        # Initial UI state: map units input only shown when Map units selected
        self._apply_units_ui()

    # Properties to access current values
    @property
    def pixel_radius(self) -> int:
        return int(self.spin_pixels.value())

    @property
    def mapunit_radius(self) -> float:
        return float(self.spin_mapunits.value())

    @property
    def unit_mode(self) -> str:
        return "map_units" if self.units_combo.currentText() == "Map units" else "pixels"

    @property
    def restrict_mode(self) -> str:
        return str(self.restrict_combo.currentData())

    @property
    def selection_mode(self) -> str:
        return str(self.selection_mode_combo.currentData())

    @property
    def show_rubber_band(self) -> bool:
        return self.show_rubber_band_cb.isChecked()

    # Public method to programmatically set values (used when loading settings)
    def setValues(self, pixel_radius=20, mapunit_radius=10.0, unit_mode="pixels", 
                  restrict_mode="visible", selection_mode="add", show_rubber_band=True):
        """Set all control values (used when loading settings)"""
        self.spin_pixels.setValue(int(pixel_radius))
        self.spin_mapunits.setValue(float(mapunit_radius))
        
        # Set unit mode
        if unit_mode == "map_units":
            self.units_combo.setCurrentIndex(1)
        else:
            self.units_combo.setCurrentIndex(0)

        # Set restrict mode
        idx = 0
        for i in range(self.restrict_combo.count()):
            if self.restrict_combo.itemData(i) == restrict_mode:
                idx = i
                break
        self.restrict_combo.setCurrentIndex(idx)

        # Set selection mode
        idx = 0
        for i in range(self.selection_mode_combo.count()):
            if self.selection_mode_combo.itemData(i) == selection_mode:
                idx = i
                break
        self.selection_mode_combo.setCurrentIndex(idx)

        # Set visual feedback
        self.show_rubber_band_cb.setChecked(show_rubber_band)
        
        self._apply_units_ui()

    # Internal callbacks
    def _on_units_changed(self, i):
        self._apply_units_ui()
        self._emit_radius_changed()

    def _apply_units_ui(self):
        """Enable/disable radius inputs based on selected unit mode"""
        if self.unit_mode == "map_units":
            self.spin_mapunits.setEnabled(True)
            self.spin_pixels.setEnabled(False)
        else:
            self.spin_mapunits.setEnabled(False)
            self.spin_pixels.setEnabled(True)

    def _on_pixel_changed(self, v):
        self._emit_radius_changed()

    def _on_mapunit_changed(self, v):
        self._emit_radius_changed()

    def _on_options_changed(self, i):
        self.optionsChanged.emit(self.restrict_mode, self.selection_mode)

    def _on_visual_feedback_changed(self, state):
        self.visualFeedbackChanged.emit(self.show_rubber_band)

    def _on_rebuild_clicked(self):
        self.rebuildIndexesRequested.emit()

    def _on_clear_clicked(self):
        self.clearSelectionRequested.emit()

    def _emit_radius_changed(self):
        self.radiusChanged.emit(self.pixel_radius, self.mapunit_radius, self.unit_mode)
