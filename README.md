# Kobushi Trackviewer (Modified)

[Readme（简体中文）](README_zhcn.md)

Last updated: May 1, 2026

> **Original version**: 1.2.2  
> **Authors**: Original: Konawasabi / Modified by: Sapporo Ningyo  
> **License**: Apache License, Version 2.0

---

## Table of Contents

1. [Overview](#1-overview)
2. [Installation & Launching](#2-installation--launching)
3. [Main Window Layout](#3-main-window-layout)
4. [Menu Reference](#4-menu-reference)
5. [Other Tracks Window](#5-other-tracks-window)
6. [Canvas Interactions](#6-canvas-interactions)
7. [Options](#7-options)
8. [Data Export](#8-data-export)
9. [Command-Line Arguments](#9-command-line-arguments)
10. [Internationalization (i18n)](#10-internationalization-i18n)
11. [Debug Mode](#11-debug-mode)
12. [FAQ & Caveats](#12-faq--caveats)
13. [Appendix: CSV Data Format](#13-appendix-csv-data-format)

---

## 1. Overview

Kobushi Trackviewer is a Python 3 GUI application that reads **BVE Trainsim 5/6 map files** (.txt format) and generates the following track geometry charts:

- **Plan View** — track projection onto the horizontal (XY) plane
- **Profile View** — distance vs. elevation chart with gradient transitions
- **Curve Radius Graph** — distance vs. signed curve radius chart

### 1.1 Key Features

| Feature | Description |
|---------|-------------|
| Map file parsing | Lark-based parser supporting the full BVE Map 2.00+ syntax (math expressions, variables, `rand()`, `$include` directives) |
| Track coordinate calculation | Computes full 3D coordinates (x, y, z) at every control point, including heading, curve radius, gradient, and superelevation (cant) |
| Plan view | XY projection of track alignment with rotation, pan, zoom, a scale bar, and a coordinate grid |
| Profile view | Distance vs. elevation chart showing gradient change markers and gradient value labels |
| Curve radius graph | Distance vs. signed curve radius chart with radius value labels |
| Station info | Reads station list files and marks station positions, names, and mileages on all charts |
| Other-track overlay | Overlays multiple other tracks (e.g., parallel lines, sidings) on the same charts |
| Data export | Save charts as PostScript files; export track coordinate data to CSV |
| Multi-language support | 日本語 / English / 简体中文 |

### 1.2 How Coordinate Calculation Works

Kobushi computes track coordinates at two categories of control points:

1. **Map-element control points** — distances where map elements (Curve, Gradient, Turn, Track, etc.) are explicitly placed in the map file
2. **Evenly-spaced control points** — supplemental points inserted at a regular interval (default 25 m) spanning from the first station's position to the last station's position + 500 m

Between any two adjacent control points, Kobushi evaluates:

- **Horizontal geometry** — straights, circular curves, clothoid transition curves (with optional sin half-wavelength easing)
- **Vertical geometry** — constant gradients, vertical transition curves
- **Superelevation (Cant)** — linear or sin half-wavelength easing interpolation

---

## 2. Installation & Launching

### 2.1 System Requirements

- **Python** 3.6 or later
- **OS**: Windows / macOS / Linux (requires a tkinter-capable graphical environment)

### 2.2 Installation

To be written.

### 2.3 Launching

#### Option 1: Launch with a file-picker dialog

```powershell
python -m kobushiM
```

#### Option 2: Launch and open a specific map file

```powershell
python -m kobushiM "path/to/mapfile.txt"
```

#### Option 3: Specify step interval and font on launch

```powershell
python -m kobushiM -s 10 -f "MS Gothic" "path/to/mapfile.txt"
```

---

## 3. Main Window Layout

After launch, the main window contains the following areas:

```
┌─────────────────────────────────────────────────┬──────────┐
│  Menu bar (File / Options / Language / Help)    │          │
├─────────────────────────────────────────────────┤          │
│  [Open] [_________File path entry field________]│  Control │
├─────────────────────────────────────────────────┤  Panel   │
│                                                 │ Aux. Info│
│              Plan View                          │ □ Station │
│              XY projection                      │   Pos.   │
│              Rotate / Pan / Zoom                │ □ Station │
│                                                 │   Name   │
│                                                 │ □ Station │
│                                                 │   Mileage│
├───────────────────────┬─────────────────────────┤ □ Gradient│
│ Profile View          │ Curve Radius Graph     │   Change  │
│ Distance vs. Elev.    │ Distance vs. Radius    │   Points  │
│                       │                        │ □ Gradient│
│                       │                        │   Values  │
│                       │                        │ □ Curve   │
│                       │                        │   Radius  │
│                       │                        │ □ Other   │
│                       │                        │   Tracks  │
│                       │                        │   (Prof.) │
│                       │                        ├────────────│
│                       │                        │ Visibility│
│                       │                        │ □ Gradient│
│                       │                        │   Graph   │
│                       │                        │ □ Curve   │
│                       │                        │   Graph   │
└───────────────────────┴─────────────────────────┴──────────┘
│                           [Station jump dropdown]           │
└────────────────────────────────────────────────────────────┘
```

### 3.1 Toolbar

- **Open button** — opens a file-picker dialog for selecting a BVE map file (.txt)
- **File path entry** — displays the path of the currently loaded map; you can also type or paste a path directly

### 3.2 Control Panel — Auxiliary Info

Located on the right side of the main window, this panel contains 7 checkboxes that control what auxiliary information is drawn on the plan and profile views:

| Checkbox | What it does |
|----------|--------------|
| **Station Position** | Draws a ● symbol at each `Station[*].Put` location |
| **Station Name** | Shows the station name next to the station symbol (requires Station Position to be on) |
| **Station Mileage** | Shows the mileage label next to the station symbol (yellow text) |
| **Gradient Change Points** | Draws white vertical lines on the profile view at gradient-change locations |
| **Gradient Values** | Shows gradient values (‰) on the profile view (requires Gradient Change Points to be on) |
| **Curve Radius** | Shows radius values on the curve radius graph as vertical text |
| **Other Tracks (Profile)** | Overlays other-track elevation lines on the profile view |

Defaults: all checkboxes are on except **Other Tracks (Profile)**, which is off.

### 3.3 Control Panel — Chart Visibility

| Checkbox | What it does |
|----------|--------------|
| **Gradient Graph** | Shows / hides the profile view pane |
| **Curve Graph** | Shows / hides the curve radius graph pane |

The two charts can be shown or hidden independently. When both are hidden, the pane area is removed entirely so the plan view can use the full window height.

### 3.4 Bottom Toolbar

- **Station jump dropdown** — lists every station on the map in the format `stationkey, StationName`. Selecting a station centers all three canvases on that station's location.

---

## 4. Menu Reference

### 4.1 File Menu

| Menu item | Shortcut | Function |
|-----------|----------|----------|
| **Open...** | `Ctrl+O` | Opens a file-picker dialog to select a BVE map file |
| **Reload** (再読み込み) | `F5` | Reloads the current map file (preserves other-track settings and view state) |
| **Save Image...** (画像を保存...) | `Ctrl+S` | Saves the contents of all three canvases as PostScript (.ps) files |
| **Save Trackdata...** (走行位置情報を保存...) | — | Exports own-track and other-track coordinate data as CSV files |
| **Exit** (終了) | `Alt+F4` | Quits the application (with a confirmation dialog) |

### 4.2 Options Menu

| Menu item | Function |
|-----------|----------|
| **Control Points...** (座標制御点...) | Sets the range and spacing of evenly-spaced control points |
| **Plot Limit...** (描画可能区間...) | Sets the displayable mileage range used in "full range" mode |
| **Font...** (フォント...) | Selects the font used for all text on the charts |

### 4.3 Language Menu

Three languages are supported:

- **日本語** (default)
- **English**
- **简体中文**

The UI text updates immediately upon switching languages.

### 4.4 Help Menu

| Menu item | Function |
|-----------|----------|
| **Help...** (ヘルプ...) | Opens the online reference documentation in a browser (GitHub) |
| **About Kobushi...** (Kobushiについて...) | Shows version and copyright information |

---

## 5. Other Tracks Window

The Other Tracks window is a separate sub-window for managing the display settings of other tracks defined in the map.

### 5.1 Opening It

The Other Tracks window opens automatically to the right of the main window when a map file is loaded. If it is closed, reloading the map file will reopen it.

### 5.2 Window Layout

The window uses a **checkbox-enabled tree view (CheckboxTreeview)** with the following columns:

| Column | Description |
|--------|-------------|
| **track key** | Track identifier (the key used in `Track['key']` statements in the map file) |
| **From** | Starting mileage [m] for displaying this track |
| **To** | Ending mileage [m] for displaying this track |
| **Color** | Color used to draw this track on the charts |

### 5.3 How to Use

#### Toggling Track Visibility

- Check the checkbox next to a track key to display it on the plan and profile views.
- Check or uncheck the top-level **root** node to toggle all tracks at once.
- Default state: all tracks are unchecked (hidden).

#### Changing the Display Range (From / To)

- Click the value in the **From** or **To** column for a track.
- Enter a new mileage value in the pop-up input dialog.
- The default From value is the mileage where the track first appears in the map.
- The default To value is the mileage where the track last appears in the map.

#### Changing the Display Color

- Click the **Color** column entry (shown as a ■■■ swatch) for a track.
- Select a new color from the system color picker.
- The change takes effect on the charts immediately.

#### Default Colors

Kobushi cycles through a set of 10 default colors when assigning colors to other tracks:

`#1f77b4` `#ff7f0e` `#2ca02c` `#d62728` `#9467bd` `#8c564b` `#e377c2` `#7f7f7f` `#bcbd22` `#17becf`

---

## 6. Canvas Interactions

Kobushi has three canvases: Plan View, Profile View, and Curve Radius Graph. Each supports the following interactions:

### 6.1 Plan View

| Action | Input | Notes |
|--------|-------|-------|
| **Pan** | Left-click + drag | Drag to pan the view |
| **Rotate** | Right-click + drag | Rotates the view around the canvas center |
| **Zoom** | Mouse wheel | Primarily zooms horizontally (X-axis) |
| **Y-axis Zoom** | `Shift + Mouse wheel` or `Shift + Right-click drag` | In rotation-enabled mode, Shift+wheel rotates instead |
| **Fit to window** | Double left-click | Auto-scales to show the full dataset |

Plan View characteristics:
- **Y-axis points down** (screen coordinate system)
- Includes a **scale bar** (lower-right corner)
- Background uses an **80 px pixel grid**

### 6.2 Profile View

| Action | Input | Notes |
|--------|-------|-------|
| **Pan** | Left-click + drag | Drag to pan the view |
| **X-axis Zoom** | Mouse wheel (default) | Zooms in the mileage direction |
| **Y-axis Zoom** | `Shift + Mouse wheel` | Zooms in the elevation direction |
| **Uniform Zoom** | `Ctrl + Mouse wheel` | Zooms both X and Y axes together |
| **Fit to window** | Double left-click | Auto-scales to fit the full dataset |

Profile View characteristics:
- Uses a **world-coordinate grid** with mileage (m) and elevation (m) labels on grid lines
- Has independent X and Y scaling factors
- Rotation is disabled
- Default zoom axis is X

### 6.3 Curve Radius Graph

| Action | Input | Notes |
|--------|-------|-------|
| **Pan** | Left-click + drag | Drag to pan the view |
| **X-axis Zoom** | Mouse wheel (default) | Zooms in the mileage direction |
| **Y-axis Zoom** | `Shift + Mouse wheel` | Zooms in the radius direction |
| **Uniform Zoom** | `Ctrl + Mouse wheel` | Zooms both X and Y axes together |
| **Fit to window** | Double left-click | Auto-scales to fit the full dataset |

Curve Radius Graph characteristics:
- Y-axis center is locked (Y=0 always stays at the vertical center of the canvas)
- Uses a world-coordinate grid
- Has independent X and Y scaling factors

### 6.4 Common Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open map file |
| `Ctrl+S` | Save image |
| `F5` | Reload map file |
| `Alt+F4` | Exit application |

---

## 7. Options

### 7.1 Control Points

Adjusts the parameters for the evenly-spaced control points that Kobushi uses when computing track coordinates:

| Parameter | Default | Description |
|-----------|---------|-------------|
| **min** | First station mileage | Starting mileage for evenly-spaced control points |
| **max** | Last station mileage + 500 m | Ending mileage for evenly-spaced control points |
| **interval** | 25 m | Spacing between control points |

**Steps**:
1. Click **Options → Control Points...**
2. Enter new min, max, and interval values in the dialog
3. Click **OK** to apply, or **Reset** to restore defaults
4. Upon confirmation, the map is automatically reloaded and coordinates are recalculated

> **Note**: Extremely small intervals combined with a large range can consume a significant amount of memory. Use with caution.

### 7.2 Plot Limit

Sets the mileage lower and upper bounds used in "full range" display mode:

| Parameter | Default | Description |
|-----------|---------|-------------|
| **min** | First station mileage − 500 m | Lower bound of the displayable range |
| **max** | Last station mileage + 500 m | Upper bound of the displayable range |

**Steps**:
1. Click **Options → Plot Limit...**
2. Enter min and max values in the dialog
3. Click **OK** to apply, or **Reset** to restore defaults

### 7.3 Font

Specifies the font used for all text on the plan, profile, and radius canvases:

**Steps**:
1. Click **Options → Font...**
2. Select an available system font from the dropdown list
3. Click **OK** to apply; all chart text updates immediately

The font can also be set via the `-f` command-line argument (see [Section 9](#9-command-line-arguments)).

Default font: `TkDefaultFont` (the system's default sans-serif font).

---

## 8. Data Export

### 8.1 Save Image

Saves the current content of all three canvases as PostScript files:

**Steps**:
1. Click **File → Save Image...** or press `Ctrl+S`
2. In the save dialog, choose a directory and enter a base filename (e.g., `myroute`)
3. Three files are generated:
   - `myroute_plan.ps` — Plan view
   - `myroute_profile.ps` — Profile view
   - `myroute_radius.ps` — Curve radius graph

File format options:
- **PostScript (.ps)** — default format; can be converted to PDF or PNG
- **any format** — manually specify a different extension if needed

### 8.2 Save Trackdata

Exports the own-track and other-track coordinate data as CSV files:

**Steps**:
1. Click **File → Save Trackdata...**
2. In the dialog, select an **output directory**
3. The following files are created in the chosen directory:
   - `<directory_name>_owntrack.csv` — own-track data
   - `<directory_name>_<trackkey>.csv` — one file per other track

See the [Appendix](#13-appendix-csv-data-format) for the CSV column layout.

---

## 9. Command-Line Arguments

Kobushi supports the following command-line arguments:

| Argument | Description | Example |
|----------|-------------|---------|
| `filepath` | Map file to open immediately on launch | `python -m kobushiM route.txt` |
| `-s STEP`, `--step STEP` | Spacing of evenly-spaced control points in meters (default: 25) | `-s 10` |
| `-f FONT`, `--font FONT` | Font face name for chart text (default: sans-serif) | `-f "MS Gothic"` |
| `-h`, `--help` | Show help message and exit | — |

**Examples**:

```powershell
# Calculate track coordinates at 10 m intervals
python -m kobushiM -s 10 "my_route.txt"

# Specify font and 50 m interval
python -m kobushiM -f "Arial" -s 50 "my_route.txt"

# Launch the GUI only and pick a file manually
python -m kobushiM
```

---

## 10. Internationalization (i18n)

Kobushi's UI is available in three languages:

- **日本語 (ja)** — default
- **English (en)**
- **简体中文 (zh)**

To switch: click the third menu on the menu bar (言語選択 / Select Language / 语言选择) → choose the desired language.

The language change takes effect instantly on:
- Menu labels
- Button text
- Checkbox labels
- Dialog messages
- Canvas titles
- Other Tracks window column headers

---

## 11. Debug Mode

### 11.1 Enabling Debug Mode

Launch with Python's `-O` optimization flag:

```powershell
python -O -m kobushiM
```

### 11.2 Debug Mode Behavior

1. **Data dump**: After loading a map file, the following complete datasets are printed to the console:
   - Own-track map element list
   - Control point list
   - Own-track coordinate data
   - Station list
   - Other-track map element lists
   - Other-track key list
   - Other-track coordinate data

2. **Exception debugging**: Whenever an exception occurs at runtime, Python's **pdb** (Python Debugger) is launched automatically for post-mortem debugging.

> **Note**: Printing large datasets for extensive map files may take considerable time.

---

## 12. FAQ & Caveats

### 12.1 Map File Compatibility

The following types of map files may **fail to load**:

- **BVE Map 1.x format** — use [Map Converter](https://bvets.net/jp/download/mapconv.html) to convert to Map 2.00 format
- **Variables used as map elements** — assigning map elements (Track, Curve, etc.) to variables is not supported
- **Map element keys not enclosed in single quotes** — `Track[hoge]` should be written as `Track['hoge']`
- **Mismatch between header encoding declaration and actual file encoding**
- **Other deviations from the [Map 2.02+ syntax specification](https://bvets.net/jp/edit/formats/route/map.html)**

> Multi-byte characters in variable names have been supported since v1.1.7.

### 12.2 Encoding Detection

Kobushi determines file encoding using the following procedure:

1. Read the encoding specified in the file's header.
2. If reading fails:
   - Header specifies UTF-8 → retry with Shift-JIS (CP932)
   - Header specifies Shift-JIS → retry with UTF-8

### 12.3 Memory Usage

Combining extremely long routes with very fine control-point spacing can consume a large amount of memory. Only reduce the control-point interval when necessary.

### 12.4 Other-Track Y Coordinates

Version 1.2.2 fixed the calculation method for other-track Y coordinates. If other tracks appear in incorrect positions on the plan view, upgrade to the latest version.

---

## 13. Appendix: CSV Data Format

### 13.1 Own-Track CSV (`*_owntrack.csv`)

Header (column names):

```
distance,x,y,z,direction,radius,gradient,interpolate_func,cant,center,gauge
```

| Column | Unit | Description |
|--------|------|-------------|
| `distance` | m | Mileage (chainage) |
| `x` | m | X coordinate |
| `y` | m | Y coordinate |
| `z` | m | Z coordinate (elevation) |
| `direction` | radian | Heading angle relative to the X axis |
| `radius` | m | Curve radius (0 = straight, positive = right turn, negative = left turn) |
| `gradient` | ‰ | Gradient (per mille) |
| `interpolate_func` | — | Transition curve function: `0` = sin half-wavelength easing, `1` = linear easing |
| `cant` | m | Superelevation (cant) amount |
| `center` | m | Cant rotation center |
| `gauge` | m | Track gauge |

### 13.2 Other-Track CSV (`*_<trackkey>.csv`)

Header (column names):

```
distance,x,y,z,interpolate_func,cant,center,gauge
```

| Column | Unit | Description |
|--------|------|-------------|
| `distance` | m | Mileage (chainage) |
| `x` | m | X coordinate |
| `y` | m | Y coordinate |
| `z` | m | Z coordinate (elevation) |
| `interpolate_func` | — | Transition curve function type |
| `cant` | m | Superelevation (cant) amount |
| `center` | m | Cant rotation center |
| `gauge` | m | Track gauge |

---

> **License**: Apache License, Version 2.0  
> **Author**: Konawasabi, Sapporo Ningyo  
> **Contact**: webmaster@konawasabi.riceball.jp / sapporoningyo@gmail.com  
> **Website**: https://konawasabi.riceball.jp
