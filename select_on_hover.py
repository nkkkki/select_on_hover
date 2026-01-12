import os
from qgis.PyQt.QtWidgets import QAction, QToolButton, QMenu, QWidgetAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QSettings

from qgis.core import QgsProject, QgsMessageLog, Qgis
from qgis.gui import QgsMapCanvas

from .map_tool_select_circle import MapToolSelectCircle
from .dock_widget import SelectOnHoverPanel

PLUGIN_SETTINGS_PREFIX = "SelectOnHover/"


class SelectOnHoverPlugin:
    """
    QGIS Plugin: Select features by hovering over them with a circular cursor.
    
    Features:
    - Radius configurable in pixels or map units
    - Selection modes: add, replace, toggle
    - Restrict to visible/all/active layers
    - Spatial indexing for performance
    - Visual feedback with rubber band
    - Debounced hover detection
    - Auto-rebuild indexes on layer changes
    """

    def __init__(self, iface):
        """
        Initialize plugin.
        
        Args:
            iface: QGIS interface instance
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.menu_action = None
        self.toolbutton = None
        self.panel = None
        self.map_tool = None
        self.previous_map_tool = None
        self.settings = QSettings()

    def initGui(self):
        """Initialize GUI elements"""
        # Load icon - try SVG first (best for QGIS), then fallback to PNG
        icon_svg_path = os.path.join(self.plugin_dir, "icon.svg")
        icon_png_path = os.path.join(self.plugin_dir, "icon.png")
        
        if os.path.exists(icon_svg_path):
            icon = QIcon(icon_svg_path)
        elif os.path.exists(icon_png_path):
            icon = QIcon(icon_png_path)
        else:
            # Fallback to default QGIS icon if our icon is missing
            icon = QIcon()
            QgsMessageLog.logMessage(
                "Icon file not found (tried icon.svg and icon.png), using default icon", 
                "SelectOnHover", 
                Qgis.Warning
            )

        # Create plugin menu action
        self.menu_action = QAction(icon, "Select on hover", self.iface.mainWindow())
        self.menu_action.triggered.connect(self._toggle_toolbutton_from_menu)
        self.iface.addPluginToMenu("&SelectOnHover", self.menu_action)

        # Create toolbar button
        self.toolbutton = QToolButton(self.iface.mainWindow())
        self.toolbutton.setIcon(icon)
        self.toolbutton.setToolTip("Select on hover - click to activate/deactivate, arrow for options")
        self.toolbutton.setCheckable(True)
        self.toolbutton.toggled.connect(self.toggle_activation)

        # Build popup menu with control panel
        menu = QMenu(self.toolbutton)
        widget_action = QWidgetAction(menu)
        self.panel = SelectOnHoverPanel()
        
        # Load saved settings
        self._load_settings_from_panel()
        
        # Connect panel signals
        self.panel.radiusChanged.connect(self.onRadiusChanged)
        self.panel.optionsChanged.connect(self.onOptionsChanged)
        self.panel.visualFeedbackChanged.connect(self.onVisualFeedbackChanged)
        self.panel.rebuildIndexesRequested.connect(self.onRebuildIndexesRequested)
        self.panel.clearSelectionRequested.connect(self.onClearSelectionRequested)
        
        widget_action.setDefaultWidget(self.panel)
        menu.addAction(widget_action)

        # Attach menu to button
        self.toolbutton.setMenu(menu)
        self.toolbutton.setPopupMode(QToolButton.MenuButtonPopup)

        # Add to toolbar
        self.iface.addToolBarWidget(self.toolbutton)

        # Create map tool
        canvas = self.iface.mapCanvas()
        self.map_tool = MapToolSelectCircle(
            canvas,
            radius_pixels=self.panel.pixel_radius,
            radius_map_units=self.panel.mapunit_radius,
            unit_mode=self.panel.unit_mode,
            restrict_mode=self.panel.restrict_mode,
            selection_mode=self.panel.selection_mode,
            show_rubber_band=self.panel.show_rubber_band,
        )
        
        # Build initial indexes
        self.map_tool.rebuildIndexes()

        QgsMessageLog.logMessage(
            "SelectOnHover plugin initialized successfully", 
            "SelectOnHover", 
            Qgis.Info
        )

    def unload(self):
        """Clean up plugin resources"""
        # Save settings
        self._save_settings_from_panel()

        # Remove menu action
        try:
            self.iface.removePluginMenu("&SelectOnHover", self.menu_action)
        except Exception:
            pass

        # Remove toolbar widget
        try:
            if self.toolbutton:
                self.iface.removeToolBarWidget(self.toolbutton)
        except Exception:
            pass

        # Deactivate and cleanup map tool
        if self.toolbutton and self.toolbutton.isChecked():
            self.toggle_activation(False)

        if self.map_tool:
            self.map_tool.cleanup()

        self.menu_action = None
        self.toolbutton = None
        self.panel = None
        self.map_tool = None

        QgsMessageLog.logMessage(
            "SelectOnHover plugin unloaded", 
            "SelectOnHover", 
            Qgis.Info
        )

    def _toggle_toolbutton_from_menu(self):
        """Toggle toolbar button when plugin menu entry is used"""
        if self.toolbutton:
            self.toolbutton.toggle()

    def toggle_activation(self, active: bool):
        """
        Toggle map tool activation.
        
        Args:
            active: True to activate, False to deactivate
        """
        canvas = self.iface.mapCanvas()
        
        if active:
            # Save previous tool
            self.previous_map_tool = canvas.mapTool()
            
            # Update map tool settings
            self.map_tool.setRadius(
                self.panel.pixel_radius, 
                self.panel.mapunit_radius, 
                self.panel.unit_mode
            )
            self.map_tool.setRestrictMode(self.panel.restrict_mode)
            self.map_tool.setSelectionMode(self.panel.selection_mode)
            self.map_tool.setShowRubberBand(self.panel.show_rubber_band)
            
            # Rebuild indexes
            self.map_tool.rebuildIndexes()
            
            # Activate tool
            canvas.setMapTool(self.map_tool)
            
            QgsMessageLog.logMessage(
                "Select on hover tool activated", 
                "SelectOnHover", 
                Qgis.Info
            )
        else:
            # Restore previous tool
            if self.previous_map_tool:
                canvas.setMapTool(self.previous_map_tool)
            else:
                canvas.unsetMapTool(self.map_tool)
            
            QgsMessageLog.logMessage(
                "Select on hover tool deactivated", 
                "SelectOnHover", 
                Qgis.Info
            )

    def onRadiusChanged(self, pixel_radius: int, mapunit_radius: float, unit_mode: str):
        """Handle radius changes from control panel"""
        if self.map_tool:
            self.map_tool.setRadius(pixel_radius, mapunit_radius, unit_mode)
        self._save_settings_from_panel()

    def onOptionsChanged(self, restrict_mode: str, selection_mode: str):
        """Handle option changes from control panel"""
        if self.map_tool:
            self.map_tool.setRestrictMode(restrict_mode)
            self.map_tool.setSelectionMode(selection_mode)
            # Rebuild indexes to reflect new restriction
            self.map_tool.rebuildIndexes()
        self._save_settings_from_panel()

    def onVisualFeedbackChanged(self, show_rubber_band: bool):
        """Handle visual feedback toggle"""
        if self.map_tool:
            self.map_tool.setShowRubberBand(show_rubber_band)
        self._save_settings_from_panel()

    def onRebuildIndexesRequested(self):
        """Handle manual index rebuild request"""
        if self.map_tool:
            QgsMessageLog.logMessage(
                "Manually rebuilding spatial indexes...", 
                "SelectOnHover", 
                Qgis.Info
            )
            self.map_tool.rebuildIndexes()
            
            # Show feedback
            try:
                self.iface.messageBar().pushMessage(
                    "SelectOnHover", 
                    "Spatial indexes rebuilt successfully", 
                    level=Qgis.Info, 
                    duration=3
                )
            except Exception:
                pass

    def onClearSelectionRequested(self):
        """Handle clear selection request"""
        count = 0
        for layer in QgsProject.instance().mapLayers().values():
            try:
                if hasattr(layer, 'removeSelection'):
                    selected_count = layer.selectedFeatureCount()
                    if selected_count > 0:
                        count += selected_count
                        layer.removeSelection()
            except Exception:
                pass
        
        # Show feedback
        if count > 0:
            try:
                self.iface.messageBar().pushMessage(
                    "SelectOnHover", 
                    f"Cleared selection ({count} features)", 
                    level=Qgis.Info, 
                    duration=2
                )
            except Exception:
                pass
            
            QgsMessageLog.logMessage(
                f"Cleared selection: {count} features", 
                "SelectOnHover", 
                Qgis.Info
            )

    def _load_settings_from_panel(self):
        """Load settings from QSettings and apply to panel"""
        # Default values
        pixel_radius = int(self.settings.value(PLUGIN_SETTINGS_PREFIX + "pixel_radius", 20))
        mapunit_radius = float(self.settings.value(PLUGIN_SETTINGS_PREFIX + "mapunit_radius", 10.0))
        unit_mode = str(self.settings.value(PLUGIN_SETTINGS_PREFIX + "unit_mode", "pixels"))
        restrict_mode = str(self.settings.value(PLUGIN_SETTINGS_PREFIX + "restrict_mode", "visible"))
        selection_mode = str(self.settings.value(PLUGIN_SETTINGS_PREFIX + "selection_mode", "add"))
        show_rubber_band = self.settings.value(PLUGIN_SETTINGS_PREFIX + "show_rubber_band", True, type=bool)

        if self.panel:
            self.panel.setValues(
                pixel_radius=pixel_radius,
                mapunit_radius=mapunit_radius,
                unit_mode=unit_mode,
                restrict_mode=restrict_mode,
                selection_mode=selection_mode,
                show_rubber_band=show_rubber_band,
            )

    def _save_settings_from_panel(self):
        """Save current panel values to QSettings"""
        if not self.panel:
            return
        
        self.settings.setValue(PLUGIN_SETTINGS_PREFIX + "pixel_radius", self.panel.pixel_radius)
        self.settings.setValue(PLUGIN_SETTINGS_PREFIX + "mapunit_radius", self.panel.mapunit_radius)
        self.settings.setValue(PLUGIN_SETTINGS_PREFIX + "unit_mode", self.panel.unit_mode)
        self.settings.setValue(PLUGIN_SETTINGS_PREFIX + "restrict_mode", self.panel.restrict_mode)
        self.settings.setValue(PLUGIN_SETTINGS_PREFIX + "selection_mode", self.panel.selection_mode)
        self.settings.setValue(PLUGIN_SETTINGS_PREFIX + "show_rubber_band", self.panel.show_rubber_band)
