use egui::{Color32, FontId, Painter, Pos2, Rect, Stroke};

#[derive(Debug, Clone)]
pub struct CanvasState {
    pub center: [f64; 2],
    pub scale: f64,
    pub scale_x: f64,
    pub scale_y: f64,
    pub rotation: f64,
    pub title: String,
    pub background: Color32,
    pub grid_color: Color32,
    pub line_color: Color32,
    pub text_color: Color32,
    pub font_family: String,

    pub rotate_enabled: bool,
    pub y_axis_down: bool,
    pub world_grid: bool,
    pub independent_scale: bool,
    pub scalebar: bool,
    pub lock_y_center: bool,
    pub zoom_x_by_default: bool,
    pub enable_lod: bool,

    pub grid_mode: String, // "fixed", "movable", "none"
    pub interactive: bool,
    pub view_fitted: bool,
    pub bounds: Option<(f64, f64, f64, f64)>,

    pub measure_pos: Option<f64>,
    pub measure_crosshair: bool,
}

impl CanvasState {
    pub fn new() -> Self {
        CanvasState {
            center: [0.0, 0.0],
            scale: 1.0,
            scale_x: 1.0,
            scale_y: 1.0,
            rotation: 0.0,
            title: String::new(),
            background: Color32::BLACK,
            grid_color: Color32::from_rgb(0x33, 0x33, 0x33),
            line_color: Color32::WHITE,
            text_color: Color32::WHITE,
            font_family: "Monospace".to_string(),

            rotate_enabled: true,
            y_axis_down: false,
            world_grid: false,
            independent_scale: false,
            scalebar: false,
            lock_y_center: false,
            zoom_x_by_default: false,
            enable_lod: true,

            grid_mode: "fixed".to_string(),
            interactive: true,
            view_fitted: false,
            bounds: None,

            measure_pos: None,
            measure_crosshair: false,
        }
    }

    pub fn fit(&mut self, width: f64, height: f64) {
        if let Some((xmin, ymin, xmax, ymax)) = self.bounds {
            let dx = (xmax - xmin).max(1e-6);
            let dy = (ymax - ymin).max(1e-6);
            self.center = [(xmin + xmax) / 2.0, (ymin + ymax) / 2.0];
            self.scale = (width / dx).min(height / dy) * 0.88;
            self.scale_x = width / dx * 0.88;
            self.scale_y = height / dy * 0.88;
        }
        self.view_fitted = true;
    }

    pub fn reset_rotation(&mut self) {
        self.rotation = 0.0;
    }

    pub fn reset_view(&mut self) {
        self.center = [0.0, 0.0];
        self.scale = 1.0;
        self.scale_x = 1.0;
        self.scale_y = 1.0;
        self.rotation = 0.0;
        self.view_fitted = false;
        self.bounds = None;
        self.measure_pos = None;
        self.measure_crosshair = false;
    }

    pub fn scales(&self) -> (f64, f64) {
        if self.independent_scale {
            (self.scale_x, self.scale_y)
        } else {
            (self.scale, self.scale)
        }
    }

    pub fn world_to_screen(&self, x: f64, y: f64, width: f64, height: f64) -> (f64, f64) {
        let dx = x - self.center[0];
        let dy = y - self.center[1];
        let c = self.rotation.cos();
        let s = self.rotation.sin();
        let rx = c * dx - s * dy;
        let ry = s * dx + c * dy;
        let (sx_scale, sy_scale) = self.scales();
        let screen_y_sign = if self.y_axis_down { 1.0 } else { -1.0 };
        (
            width / 2.0 + rx * sx_scale,
            height / 2.0 + screen_y_sign * ry * sy_scale,
        )
    }

    pub fn screen_to_world(&self, sx: f64, sy: f64, width: f64, height: f64) -> (f64, f64) {
        let (sx_scale, sy_scale) = self.scales();
        let rx = (sx - width / 2.0) / sx_scale;
        let screen_y_sign = if self.y_axis_down { 1.0 } else { -1.0 };
        let ry = (sy - height / 2.0) / (screen_y_sign * sy_scale);
        let c = self.rotation.cos();
        let s = self.rotation.sin();
        (
            c * rx + s * ry + self.center[0],
            -s * rx + c * ry + self.center[1],
        )
    }

    pub fn get_lod_stride(&self) -> usize {
        if !self.enable_lod {
            return 1;
        }
        let (sx, sy) = self.scales();
        let effective = sx.min(sy);
        if effective >= 0.5 {
            1
        } else if effective >= 0.1 {
            2
        } else if effective >= 0.01 {
            5
        } else {
            10
        }
    }

    pub fn zoom(&mut self, factor: f64, axis: &str) {
        self.view_fitted = true;
        if self.independent_scale {
            if axis == "x" || axis == "both" {
                self.scale_x = (self.scale_x * factor).clamp(0.001, 10000.0);
            }
            if axis == "y" || axis == "both" {
                self.scale_y = (self.scale_y * factor).clamp(0.001, 10000.0);
            }
        } else {
            self.scale = (self.scale * factor).clamp(0.001, 10000.0);
        }
    }

    pub fn pan(&mut self, screen_dx: f64, screen_dy: f64, _width: f64, _height: f64) {
        let (sx_scale, sy_scale) = self.scales();
        let screen_y_sign = if self.y_axis_down { 1.0 } else { -1.0 };
        let c = self.rotation.cos();
        let s = self.rotation.sin();
        let wx = -(c * screen_dx / sx_scale + screen_y_sign * s * screen_dy / sy_scale);
        let wy = s * screen_dx / sx_scale - screen_y_sign * c * screen_dy / sy_scale;
        // Fix 1: invert direction so the view follows the mouse (match Python _pan)
        self.center[0] -= wx;
        if !self.lock_y_center {
            self.center[1] -= wy;
        }
    }

    pub fn rotate(&mut self, angle_delta: f64) {
        if self.rotate_enabled {
            self.rotation += angle_delta;
        }
    }
}

pub struct CanvasPainter;

impl CanvasPainter {
    pub fn draw_world_line(
        painter: &Painter,
        state: &CanvasState,
        points: &[[f64; 2]],
        color: Color32,
        width_scale: f32,
        rect: Rect,
    ) {
        if points.len() < 2 {
            return;
        }
        let stride = state.get_lod_stride();
        let width = rect.width() as f64;
        let height = rect.height() as f64;

        // Viewport culling
        let corners = [
            state.screen_to_world(rect.left() as f64, rect.top() as f64, width, height),
            state.screen_to_world(rect.right() as f64, rect.top() as f64, width, height),
            state.screen_to_world(rect.left() as f64, rect.bottom() as f64, width, height),
            state.screen_to_world(rect.right() as f64, rect.bottom() as f64, width, height),
        ];
        let wx_min = corners.iter().map(|p| p.0).fold(f64::INFINITY, f64::min) - 100.0;
        let wx_max = corners
            .iter()
            .map(|p| p.0)
            .fold(f64::NEG_INFINITY, f64::max)
            + 100.0;
        let wy_min = corners.iter().map(|p| p.1).fold(f64::INFINITY, f64::min) - 100.0;
        let wy_max = corners
            .iter()
            .map(|p| p.1)
            .fold(f64::NEG_INFINITY, f64::max)
            + 100.0;

        let mut segment_start: Option<usize> = None;

        for i in (0..points.len()).step_by(stride) {
            let (wx, wy) = (points[i][0], points[i][1]);
            let visible = wx >= wx_min && wx <= wx_max && wy >= wy_min && wy <= wy_max;

            if visible {
                if segment_start.is_none() {
                    segment_start = Some(i);
                }
            } else {
                if let Some(start) = segment_start {
                    let end = i;
                    if end > start + 1 {
                        Self::draw_segment(
                            painter,
                            state,
                            points,
                            start,
                            end,
                            color,
                            width_scale,
                            rect,
                        );
                    }
                    segment_start = None;
                }
            }
        }
        if let Some(start) = segment_start {
            let end = points.len();
            if end > start + 1 {
                Self::draw_segment(painter, state, points, start, end, color, width_scale, rect);
            }
        }
    }

    fn draw_segment(
        painter: &Painter,
        state: &CanvasState,
        points: &[[f64; 2]],
        start: usize,
        end: usize,
        color: Color32,
        width_scale: f32,
        rect: Rect,
    ) {
        let width_f = rect.width() as f64;
        let height_f = rect.height() as f64;

        let actual_start = if start > 0 { start - 1 } else { start };
        let actual_end = end.min(points.len());

        let mut screen_pts: Vec<Pos2> = Vec::with_capacity(actual_end - actual_start);
        for i in actual_start..actual_end {
            let (sx, sy) = state.world_to_screen(points[i][0], points[i][1], width_f, height_f);
            if sx.is_finite() && sy.is_finite() {
                screen_pts.push(Pos2::new(sx as f32, sy as f32));
            }
        }

        if screen_pts.len() >= 2 {
            painter.add(egui::Shape::line(
                screen_pts,
                Stroke::new(width_scale, color),
            ));
        }
    }

    pub fn draw_world_text(
        painter: &Painter,
        state: &CanvasState,
        wx: f64,
        wy: f64,
        text: &str,
        color: Color32,
        offset: (f32, f32),
        font_size: f32,
        rect: Rect,
        angle: Option<f32>,
    ) {
        let (sx, sy) = state.world_to_screen(wx, wy, rect.width() as f64, rect.height() as f64);
        let pos = Pos2::new(sx as f32 + offset.0, sy as f32 + offset.1);
        let font_id = FontId::proportional(font_size);

        if let Some(_ang) = angle {
            painter.text(pos, egui::Align2::LEFT_TOP, text, font_id, color);
        } else {
            painter.text(pos, egui::Align2::LEFT_TOP, text, font_id, color);
        }
    }

    pub fn draw_scalebar(painter: &Painter, state: &CanvasState, rect: Rect) {
        let (sx_scale, _) = state.scales();
        if sx_scale <= 0.0 {
            return;
        }
        let width = rect.width() as f64;
        let height = rect.height() as f64;
        let target_px = (width * 0.18).clamp(90.0, 180.0);
        let raw_length = target_px / sx_scale;
        let length = friendly_scalebar_length(raw_length);
        let bar_px = length * sx_scale;
        let margin = 24.0;
        let x2 = width - margin;
        let x1 = x2 - bar_px;
        let y = height - margin;

        let color = state.text_color;
        let tick = 10.0;

        painter.line_segment(
            [
                Pos2::new(x1 as f32, (y - tick) as f32),
                Pos2::new(x1 as f32, y as f32),
            ],
            Stroke::new(2.0, color),
        );
        painter.line_segment(
            [
                Pos2::new(x1 as f32, y as f32),
                Pos2::new(x2 as f32, y as f32),
            ],
            Stroke::new(2.0, color),
        );
        painter.line_segment(
            [
                Pos2::new(x2 as f32, (y - tick) as f32),
                Pos2::new(x2 as f32, y as f32),
            ],
            Stroke::new(2.0, color),
        );

        let label = format_scalebar_label(length);
        painter.text(
            Pos2::new(((x1 + x2) / 2.0) as f32, (y - tick - 4.0) as f32),
            egui::Align2::CENTER_BOTTOM,
            label,
            FontId::proportional(12.0),
            color,
        );
    }
}

fn friendly_scalebar_length(raw: f64) -> f64 {
    if raw <= 0.0 {
        return 1.0;
    }
    let magnitude = 10.0f64.powf(raw.log10().floor());
    let mut candidates: Vec<f64> = Vec::new();
    for exp in [-1, 0, 1, 2] {
        let base = magnitude * (10.0f64.powi(exp));
        for factor in [1.0, 2.0, 3.0, 5.0] {
            candidates.push(factor * base);
        }
    }
    candidates.sort_by(|a, b| a.partial_cmp(b).unwrap());
    candidates
        .into_iter()
        .min_by(|a, b| (a - raw).abs().partial_cmp(&(b - raw).abs()).unwrap())
        .unwrap_or(1.0)
}

fn format_scalebar_label(length: f64) -> String {
    if length >= 1000.0 {
        let km = length / 1000.0;
        if (km - km.round()).abs() < 1e-9 {
            format!("{:.0}km", km)
        } else {
            format!("{:.1}km", km)
        }
    } else if (length - length.round()).abs() < 1e-9 {
        format!("{:.0}m", length)
    } else {
        format!("{:.1}m", length)
    }
}

pub fn compute_movable_grid(
    canvas: &CanvasState,
    rect: Rect,
) -> Option<(f64, f64, f64)> {
    // Computes (step, x_start, y_start) for movable grid lines
    let width = rect.width() as f64;
    let height = rect.height() as f64;

    let corners = [
        canvas.screen_to_world(rect.left() as f64, rect.top() as f64, width, height),
        canvas.screen_to_world(rect.right() as f64, rect.top() as f64, width, height),
        canvas.screen_to_world(rect.left() as f64, rect.bottom() as f64, width, height),
        canvas.screen_to_world(rect.right() as f64, rect.bottom() as f64, width, height),
    ];

    let xmin = corners.iter().map(|p| p.0).fold(f64::INFINITY, f64::min);
    let xmax = corners.iter().map(|p| p.0).fold(f64::NEG_INFINITY, f64::max);
    let ymin = corners.iter().map(|p| p.1).fold(f64::INFINITY, f64::min);
    let ymax = corners.iter().map(|p| p.1).fold(f64::NEG_INFINITY, f64::max);

    let dx = xmax - xmin;
    if dx <= 0.0 || !dx.is_finite() {
        return None;
    }

    let order_of_mag = (dx / 5.0).log10().floor();
    let step = 10_f64.powf(order_of_mag);
    if step <= 0.0 || !step.is_finite() {
        return None;
    }

    let x_start = (xmin / step).floor() * step;
    let y_start = (ymin / step).floor() * step;

    Some((step, x_start, y_start))
}
