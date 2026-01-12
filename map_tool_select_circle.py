from qgis.PyQt.QtCore import Qt, QPoint, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QPainter, QColor, QPen, QCursor
from qgis.core import (
    QgsMapLayer,
    QgsGeometry,
    QgsPointXY,
    QgsFeatureRequest,
    QgsProject,
    QgsCoordinateTransform,
    QgsSpatialIndex,
    QgsMessageLog,
    Qgis,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool, QgsRubberBand

# Constants
DEFAULT_CIRCLE_SEGMENTS = 32
DEFAULT_HOVER_DELAY_MS = 15  # Reduced from 50ms for more responsive selection


class MapToolSelectCircle(QgsMapTool):
    """
    Map tool that selects features intersecting a circle around the mouse pointer.
    
    Features:
    - Radius in pixels or in map units
    - Per-layer spatial indexes for faster candidate lookup
    - Restricting to active layer / visible layers / all selectable layers
    - Selection modes: add, replace, toggle
    - Visual cursor that represents the circle
    - Optional rubber band showing selection area
    - Debounced hover to improve performance
    - Automatic index rebuilding on layer changes
    """

    # Signal emitted when rebuild completes
    indexesRebuilt = pyqtSignal()
    # Signal emitted with selection count
    selectionComplete = pyqtSignal(int)  # number of features selected

    def __init__(self, canvas, radius_pixels=20, radius_map_units=10.0, 
                 unit_mode="pixels", circle_segments=DEFAULT_CIRCLE_SEGMENTS, 
                 restrict_mode="visible", selection_mode="add", show_rubber_band=True):
        """
        Initialize the map tool.
        
        Args:
            canvas: QgsMapCanvas instance
            radius_pixels: Radius in screen pixels
            radius_map_units: Radius in map units
            unit_mode: "pixels" or "map_units"
            circle_segments: Number of segments to approximate circle
            restrict_mode: "all" (all selectable), "visible" (visible & selectable), "active" (active layer)
            selection_mode: "add" (union), "replace" (clear then select), "toggle" (xor)
            show_rubber_band: Whether to show visual feedback circle on map
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.radius_pixels = max(1, int(radius_pixels))
        self.radius_map_units = float(radius_map_units)
        self.unit_mode = unit_mode
        self.circle_segments = circle_segments
        self.restrict_mode = restrict_mode
        self.selection_mode = selection_mode
        self.show_rubber_band = show_rubber_band
        
        # Set initial cursor
        self.setCursor(self._cursor_for_radius(self.radius_pixels))
        
        # Spatial indexes cache
        self.layer_indexes = {}  # layer.id() -> QgsSpatialIndex
        self.indexed_layer_ids = set()

        # Rubber band for visual feedback
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(10, 120, 200, 80))
        self.rubber_band.setWidth(2)
        self.rubber_band.setLineStyle(Qt.DashLine)
        if not self.show_rubber_band:
            self.rubber_band.hide()

        # Debouncing: delay selection to avoid excessive processing on every mouse move
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._do_selection)
        self._hover_delay_ms = DEFAULT_HOVER_DELAY_MS
        self._pending_pos = None

        # Update cursor when canvas extents change (useful if unit_mode == "map_units")
        self.canvas.extentsChanged.connect(self._on_canvas_extents_changed)

        # Connect to project signals for automatic index rebuilding
        project = QgsProject.instance()
        project.layersAdded.connect(self._on_layers_changed)
        project.layersRemoved.connect(self._on_layers_changed)
        # Note: For visibility changes, ideally connect to layerTreeRoot signals,
        # but that requires more complex setup. User can manually rebuild if needed.

    # Public API
    def setRadius(self, pixel_radius: int = None, mapunit_radius: float = None, 
                  unit_mode: str = None):
        """Update radius settings"""
        if pixel_radius is not None:
            self.radius_pixels = max(1, int(pixel_radius))
        if mapunit_radius is not None:
            self.radius_map_units = float(mapunit_radius)
        if unit_mode is not None:
            if unit_mode in ("pixels", "map_units"):
                self.unit_mode = unit_mode
        # Update cursor size
        pix_radius = self._compute_pixel_radius_for_cursor()
        self.setCursor(self._cursor_for_radius(pix_radius))

    def setRestrictMode(self, restrict_mode: str):
        """Update restrict mode (all/visible/active)"""
        if restrict_mode in ("all", "visible", "active"):
            self.restrict_mode = restrict_mode

    def setSelectionMode(self, selection_mode: str):
        """Update selection mode (add/replace/toggle)"""
        if selection_mode in ("add", "replace", "toggle"):
            self.selection_mode = selection_mode

    def setShowRubberBand(self, show: bool):
        """Toggle rubber band visibility"""
        self.show_rubber_band = show
        if show:
            self.rubber_band.show()
        else:
            self.rubber_band.hide()

    def rebuildIndexes(self):
        """
        (Re)build spatial indexes for layers that match current restriction.
        This is called on activation and when the user requests rebuild.
        """
        self.layer_indexes.clear()
        self.indexed_layer_ids.clear()

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        for layer in project.mapLayers().values():
            if layer.type() != QgsMapLayer.VectorLayer:
                continue
            
            # Respect selectable flag
            try:
                if not layer.selectable():
                    continue
            except Exception:
                pass

            # Restriction handling
            if self.restrict_mode == "visible":
                node = root.findLayer(layer.id())
                if node is None or not node.isVisible():
                    continue
            elif self.restrict_mode == "active":
                active = self.canvas.currentLayer()
                if active is None or active.id() != layer.id():
                    continue

            # Build spatial index for this layer
            try:
                index = QgsSpatialIndex(layer.getFeatures())
                self.layer_indexes[layer.id()] = index
                self.indexed_layer_ids.add(layer.id())
                QgsMessageLog.logMessage(
                    f"Built spatial index for layer: {layer.name()}", 
                    "SelectOnHover", 
                    Qgis.Info
                )
            except Exception as e:
                # If indexing fails, skip layer; we will fall back to bbox filter
                QgsMessageLog.logMessage(
                    f"Failed to build index for layer {layer.name()}: {str(e)}", 
                    "SelectOnHover", 
                    Qgis.Warning
                )
                continue

        # Emit signal
        try:
            self.indexesRebuilt.emit()
        except Exception:
            pass

    # Internal helpers
    def _compute_pixel_radius_for_cursor(self) -> int:
        """Compute pixel radius to draw the cursor. If unit_mode is map_units, convert to pixels."""
        if self.unit_mode == "pixels":
            return max(1, int(self.radius_pixels))
        else:
            mup = self.canvas.mapUnitsPerPixel()
            if mup and mup > 0:
                return max(1, int(round(self.radius_map_units / mup)))
            else:
                return max(1, int(self.radius_pixels))

    def _cursor_for_radius(self, radius: int) -> QCursor:
        """Build a custom cursor showing a circle of the given radius"""
        size = max(16, radius * 2 + 8)
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        pen = QPen(QColor(10, 120, 200, 220))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPoint(size // 2, size // 2)
        painter.drawEllipse(center, radius, radius)
        # Draw crosshair
        painter.drawLine(center.x() - 4, center.y(), center.x() + 4, center.y())
        painter.drawLine(center.x(), center.y() - 4, center.x(), center.y() + 4)
        painter.end()
        cursor = QCursor(pix, hotX=size // 2, hotY=size // 2)
        return cursor

    def _on_canvas_extents_changed(self):
        """Update cursor when extents change (for map-unit mode)"""
        pix_radius = self._compute_pixel_radius_for_cursor()
        self.setCursor(self._cursor_for_radius(pix_radius))

    def _on_layers_changed(self):
        """Auto-rebuild indexes when layers are added/removed"""
        if self.canvas.mapTool() == self:
            QgsMessageLog.logMessage(
                "Layers changed, rebuilding indexes...", 
                "SelectOnHover", 
                Qgis.Info
            )
            self.rebuildIndexes()

    def canvasMoveEvent(self, event):
        """
        Called whenever mouse moves. Debounced to avoid excessive processing.
        """
        self._pending_pos = event.pos()
        self._hover_timer.start(self._hover_delay_ms)

    def _do_selection(self):
        """
        Perform the actual selection after debounce delay.
        Computes a circular geometry around the mouse and selects intersecting features.
        """
        if self._pending_pos is None:
            return

        # Center point in map (project) coordinates
        center_map_pt = self.toMapCoordinates(self._pending_pos)

        # Compute radius in map units
        if self.unit_mode == "pixels":
            mup = self.canvas.mapUnitsPerPixel()
            radius_map_units = self.radius_pixels * mup
        else:
            radius_map_units = float(self.radius_map_units)

        # Create circular geometry in project/map coordinates
        circle_geom = QgsGeometry.fromPointXY(QgsPointXY(center_map_pt)).buffer(
            radius_map_units, self.circle_segments
        )

        # Update rubber band
        if self.show_rubber_band:
            project = QgsProject.instance()
            proj_crs = project.crs()
            self.rubber_band.setToGeometry(circle_geom, proj_crs)

        project = QgsProject.instance()
        proj_crs = project.crs()
        root = project.layerTreeRoot()

        total_selected = 0

        # Iterate through layers
        for layer in project.mapLayers().values():
            if layer.type() != QgsMapLayer.VectorLayer:
                continue
            
            # Respect selectable flag
            try:
                if not layer.selectable():
                    continue
            except Exception:
                pass

            # Restriction handling
            if self.restrict_mode == "visible":
                node = root.findLayer(layer.id())
                if node is None or not node.isVisible():
                    continue
            elif self.restrict_mode == "active":
                active = self.canvas.currentLayer()
                if active is None or active.id() != layer.id():
                    continue

            layer_crs = layer.crs()
            geom_for_layer = circle_geom
            
            # Transform to layer CRS if needed
            if layer_crs != proj_crs:
                try:
                    xform = QgsCoordinateTransform(proj_crs, layer_crs, project)
                    geom_for_layer = QgsGeometry(circle_geom)  # clone
                    geom_for_layer.transform(xform)
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"CRS transform failed for layer {layer.name()}: {str(e)}", 
                        "SelectOnHover", 
                        Qgis.Warning
                    )
                    continue

            bbox = geom_for_layer.boundingBox()
            ids_to_process = set()

            # Use spatial index if available
            index = self.layer_indexes.get(layer.id(), None)
            if index:
                try:
                    candidate_ids = index.intersects(bbox)
                except Exception:
                    candidate_ids = []
                
                # Verify exact intersection for candidates
                for fid in candidate_ids:
                    try:
                        feat = layer.getFeature(int(fid))
                        g = feat.geometry()
                        if g is None:
                            continue
                        if g.intersects(geom_for_layer):
                            ids_to_process.add(feat.id())
                    except Exception:
                        continue
            else:
                # Fallback: bbox filter + precise test
                request = QgsFeatureRequest().setFilterRect(bbox)
                try:
                    for feat in layer.getFeatures(request):
                        g = feat.geometry()
                        if g is None:
                            continue
                        if g.intersects(geom_for_layer):
                            ids_to_process.add(feat.id())
                except Exception:
                    continue

            if ids_to_process:
                try:
                    current_sel = set(layer.selectedFeatureIds())
                    
                    # Apply selection mode
                    if self.selection_mode == "add":
                        # Union: add to existing selection
                        new_sel = list(current_sel.union(ids_to_process))
                    elif self.selection_mode == "replace":
                        # Replace: use only new selection
                        new_sel = list(ids_to_process)
                    elif self.selection_mode == "toggle":
                        # Toggle: XOR
                        new_sel = list(current_sel.symmetric_difference(ids_to_process))
                    else:
                        new_sel = list(current_sel.union(ids_to_process))
                    
                    layer.selectByIds(new_sel)
                    total_selected += len(ids_to_process)
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Selection failed for layer {layer.name()}: {str(e)}", 
                        "SelectOnHover", 
                        Qgis.Warning
                    )

        # Show feedback in status bar
        if total_selected > 0:
            try:
                self.canvas.window().statusBar().showMessage(
                    f"Selected {total_selected} feature(s)", 2000
                )
            except Exception:
                pass

        # Emit signal
        try:
            self.selectionComplete.emit(total_selected)
        except Exception:
            pass

    def canvasPressEvent(self, event):
        """Ignore mouse clicks - selection happens on hover only"""
        pass

    def activate(self):
        """Called when tool becomes active"""
        super().activate()
        pix_radius = self._compute_pixel_radius_for_cursor()
        self.canvas.setCursor(self._cursor_for_radius(pix_radius))
        if self.show_rubber_band:
            self.rubber_band.show()

    def deactivate(self):
        """Called when tool becomes inactive"""
        super().deactivate()
        self.rubber_band.reset()
        self.rubber_band.hide()
        self._hover_timer.stop()

    def cleanup(self):
        """Clean up resources"""
        try:
            self.canvas.extentsChanged.disconnect(self._on_canvas_extents_changed)
        except Exception:
            pass
        
        try:
            project = QgsProject.instance()
            project.layersAdded.disconnect(self._on_layers_changed)
            project.layersRemoved.disconnect(self._on_layers_changed)
        except Exception:
            pass
        
        self.rubber_band.reset()
        self._hover_timer.stop()
