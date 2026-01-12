\# SelectOnHover QGIS Plugin v2.0



A powerful QGIS plugin that automatically selects vector features when you hover over them with your mouse cursor.



\## Features



\### Core Functionality

\- \*\*Hover Selection\*\*: Select features simply by moving your mouse over them

\- \*\*Custom Radius\*\*: Configure selection radius in pixels or map units

\- \*\*Visual Feedback\*\*: See the selection circle both as cursor and as a rubber band on the map



\### Selection Modes

\- \*\*Add\*\*: Adds features to existing selection (union)

\- \*\*Replace\*\*: Clears previous selection before selecting new features

\- \*\*Toggle\*\*: Toggles feature selection (XOR - select if not selected, deselect if selected)



\### Layer Filtering

\- \*\*Visible \& Selectable\*\*: Only select from layers that are visible and selectable (default)

\- \*\*All Selectable\*\*: Select from all selectable layers regardless of visibility

\- \*\*Active Layer Only\*\*: Restrict selection to only the currently active layer



\### Performance Optimizations

\- \*\*Spatial Indexing\*\*: Pre-builds spatial indexes for fast feature lookup

\- \*\*Debounced Hover\*\*: Prevents excessive processing on rapid mouse movements

\- \*\*Auto-Rebuild\*\*: Automatically rebuilds indexes when layers are added/removed

\- \*\*CRS Transformation\*\*: Correctly handles layers in different coordinate systems



\### User Interface

\- \*\*Toolbar Button\*\*: Click to activate/deactivate, click arrow for settings

\- \*\*Compact Panel\*\*: All settings accessible from dropdown menu

\- \*\*Status Feedback\*\*: Shows selection count in status bar

\- \*\*Clear Selection\*\*: Quick button to clear all selections



\## Installation



1\. Copy the `select\_on\_hover` folder to your QGIS plugins directory:

&nbsp;  - \*\*Linux\*\*: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

&nbsp;  - \*\*Windows\*\*: `%APPDATA%/QGIS/QGIS3/profiles/default/python/plugins/`

&nbsp;  - \*\*macOS\*\*: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`



2\. \*\*Generate the icon\*\* (if icon.svg is missing):

&nbsp;  ```bash

&nbsp;  cd select\_on\_hover

&nbsp;  python generate\_icon.py

&nbsp;  ```



3\. Restart QGIS or click "Reload" in the Plugin Manager



4\. Enable the plugin in \*\*Plugins → Manage and Install Plugins\*\*



5\. Look for the circular icon in your toolbar



\## Usage



\### Basic Usage

1\. Click the toolbar button to activate the tool

2\. Move your mouse over vector features to select them

3\. Click the button again to deactivate



\### Accessing Settings

\- Click the small arrow on the right side of the toolbar button

\- A dropdown panel will appear with all configuration options



\### Configuration Options



\#### Radius Settings

\- \*\*Units\*\*: Choose between "Pixels" (screen-based) or "Map units" (geographic)

\- \*\*Radius (pixels)\*\*: Set radius in screen pixels (1-2000)

\- \*\*Radius (map units)\*\*: Set radius in map units (for geographic precision)



\#### Selection Settings

\- \*\*Restrict selection to\*\*: Control which layers are searched

\- \*\*Selection mode\*\*: Choose how selections are handled (add/replace/toggle)



\#### Visual Feedback

\- \*\*Show selection circle on map\*\*: Toggle the rubber band visualization



\#### Actions

\- \*\*Rebuild spatial indexes\*\*: Manually rebuild indexes if needed

\- \*\*Clear all selections\*\*: Clear selections from all layers



\## Technical Details



\### Requirements

\- QGIS 3.0 or higher

\- No external dependencies (uses only PyQGIS and PyQt)



\### How It Works

1\. \*\*Spatial Indexing\*\*: On activation, builds QgsSpatialIndex for each eligible layer

2\. \*\*Hover Detection\*\*: Mouse movements trigger debounced selection (15ms delay for responsiveness)

3\. \*\*Geometry Intersection\*\*: Creates circular geometry and tests intersection with features

4\. \*\*CRS Transformation\*\*: Automatically transforms selection geometry to each layer's CRS

5\. \*\*Selection Application\*\*: Applies selection based on chosen mode (add/replace/toggle)



\### Performance Considerations

\- Spatial indexes dramatically speed up feature lookup

\- Debouncing prevents excessive processing

\- Only visible/selectable layers are indexed (when using "visible" mode)

\- Indexes automatically rebuild when layers change



\## Improvements Over v1.0



1\. ✅ \*\*Performance\*\*: Debounced hover reduces CPU usage

2\. ✅ \*\*Selection Modes\*\*: Add, replace, and toggle modes

3\. ✅ \*\*Visual Feedback\*\*: Optional rubber band shows selection area

4\. ✅ \*\*Auto-Rebuild\*\*: Indexes rebuild automatically on layer changes

5\. ✅ \*\*Better Feedback\*\*: Status bar shows selection count

6\. ✅ \*\*Clear Selection\*\*: One-click button to clear all selections

7\. ✅ \*\*Icon Fixed\*\*: Uses PNG format for better reliability

8\. ✅ \*\*Improved Logging\*\*: Better error messages and info logging

9\. ✅ \*\*Type Hints\*\*: Cleaner code with type annotations

10\. ✅ \*\*Better UI\*\*: More organized control panel



\## Troubleshooting



\### Icon Not Showing

If the icon doesn't appear:

1\. Make sure `icon.svg` exists in the plugin folder

2\. Run `python generate\_icon.py` to create it

3\. Restart QGIS

4\. If still not working, the plugin will use QGIS default icon (functionality not affected)



\### Selection Not Working

\- Verify layers are selectable (right-click layer → Properties → check "Selectable")

\- Check layer visibility if using "Visible \& selectable" mode

\- Try clicking "Rebuild spatial indexes" in the settings panel

\- Check QGIS message log (View → Panels → Log Messages) for errors



\### Performance Issues

\- Reduce hover radius for better performance

\- Use "Active layer only" mode if working with one layer

\- Rebuild indexes if layers have changed significantly



\## License



This plugin is provided as-is for use with QGIS.



\## Credits



\- Original concept: nkkkki

\- Improvements: Enhanced by AI assistant

\- Built with: PyQGIS and PyQt



\## Support



For issues or feature requests, check the QGIS message log for detailed error information.

