use crate::canvas::*;
use crate::environment::*;
use crate::i18n;
use crate::map_plot::*;
use crate::parser;

use egui::*;
use std::sync::{Arc, Mutex};
use std::time::Instant;

#[derive(PartialEq, Clone, Copy)]
enum ViewMode {
    Pan,
    Measure,
}

struct OtherTrackSettings {
    visible: bool,
    color: Color32,
    dist_min: f64,
    dist_max: f64,
}

pub struct App {
    // State
    map_plot: Option<MapPlot>,
    env: Option<Environment>,

    // Error handling
    error_state: Arc<Mutex<Option<String>>>,
    error_message: Option<String>,

    // Canvas states
    plane_canvas: CanvasState,
    profile_canvas: CanvasState,
    radius_canvas: CanvasState,

    // UI state
    mode: ViewMode,
    grid_mode: String,
    file_path: String,
    default_step: f64,

    // Checkbox states
    show_station_pos: bool,
    show_station_name: bool,
    show_station_mileage: bool,
    show_gradient_pos: bool,
    show_gradient_val: bool,
    show_curve_val: bool,
    show_prof_othert: bool,
    show_speedlimit: bool,
    show_gradient_graph: bool,
    show_curve_graph: bool,

    // Measure mode
    measure_distance: Option<f64>,
    measure_info: Option<TrackInfo>,

    // Other tracks
    othertrack_settings: std::collections::HashMap<String, OtherTrackSettings>,
    othertrack_colors: Vec<Color32>,

    // Station combo
    station_list: Vec<(f64, String, String)>,
    selected_station: usize,

    // Log
    status_text: String,
    load_time: f64,

    // Font
    font_size: f32,

    // Dialogs
    show_quit_dialog: bool,
    show_about: bool,
    show_plotlimit_dialog: bool,
    show_cp_dialog: bool,
    show_font_dialog: bool,
    plotlimit_min: String,
    plotlimit_max: String,
    cp_min: String,
    cp_max: String,
    cp_interval: String,
    dmin: Option<f64>,
    dmax: Option<f64>,
    distrange_min: f64,
    distrange_max: f64,
    cp_arbdistribution_override: Option<(f64, f64, f64)>,
}

impl App {
    pub fn new(step: f64, font: &str, error_state: Arc<Mutex<Option<String>>>) -> Self {
        let plane = CanvasState {
            title: "Plan".to_string(),
            y_axis_down: true,
            rotate_enabled: true,
            scalebar: true,
            background: Color32::BLACK,
            line_color: Color32::WHITE,
            text_color: Color32::WHITE,
            grid_color: Color32::from_rgb(0x33, 0x33, 0x33),
            font_family: font.to_string(),
            ..CanvasState::new()
        };
        let profile = CanvasState {
            title: "Gradient / Height".to_string(),
            independent_scale: true,
            zoom_x_by_default: true,
            world_grid: true,
            background: Color32::BLACK,
            line_color: Color32::WHITE,
            text_color: Color32::WHITE,
            grid_color: Color32::from_rgb(0x33, 0x33, 0x33),
            font_family: font.to_string(),
            ..CanvasState::new()
        };
        let radius = CanvasState {
            title: "Curve Radius".to_string(),
            independent_scale: true,
            lock_y_center: true,
            zoom_x_by_default: true,
            enable_lod: false,
            world_grid: true,
            background: Color32::BLACK,
            line_color: Color32::WHITE,
            text_color: Color32::WHITE,
            grid_color: Color32::from_rgb(0x33, 0x33, 0x33),
            font_family: font.to_string(),
            ..CanvasState::new()
        };

        let colors = vec![
            Color32::from_rgb(0x1f, 0x77, 0xb4),
            Color32::from_rgb(0xff, 0x7f, 0x0e),
            Color32::from_rgb(0x2c, 0xa0, 0x2c),
            Color32::from_rgb(0xd6, 0x27, 0x28),
            Color32::from_rgb(0x94, 0x67, 0xbd),
            Color32::from_rgb(0x8c, 0x56, 0x4b),
            Color32::from_rgb(0xe3, 0x77, 0xc2),
            Color32::from_rgb(0x7f, 0x7f, 0x7f),
            Color32::from_rgb(0xbc, 0xbd, 0x22),
            Color32::from_rgb(0x17, 0xbe, 0xcf),
        ];

        App {
            map_plot: None,
            env: None,
            error_state,
            error_message: None,
            plane_canvas: plane,
            profile_canvas: profile,
            radius_canvas: radius,
            mode: ViewMode::Pan,
            grid_mode: "fixed".to_string(),
            file_path: String::new(),
            default_step: step,
            show_station_pos: true,
            show_station_name: true,
            show_station_mileage: true,
            show_gradient_pos: true,
            show_gradient_val: true,
            show_curve_val: true,
            show_prof_othert: false,
            show_speedlimit: true,
            show_gradient_graph: true,
            show_curve_graph: true,
            measure_distance: None,
            measure_info: None,
            othertrack_settings: std::collections::HashMap::new(),
            othertrack_colors: colors,
            station_list: Vec::new(),
            selected_station: 0,
            status_text: String::new(),
            load_time: 0.0,
            font_size: 12.0,
            show_quit_dialog: false,
            show_about: false,
            show_plotlimit_dialog: false,
            show_cp_dialog: false,
            show_font_dialog: false,
            plotlimit_min: String::new(),
            plotlimit_max: String::new(),
            cp_min: String::new(),
            cp_max: String::new(),
            cp_interval: String::new(),
            dmin: None,
            dmax: None,
            distrange_min: 0.0,
            distrange_max: 0.0,
            cp_arbdistribution_override: None,
        }
    }

    pub fn open_file(&mut self, path: &str) {
        let is_new_file = self.file_path != path;
        if is_new_file {
            self.cp_arbdistribution_override = None;
            self.plane_canvas.reset_view();
            self.profile_canvas.reset_view();
            self.radius_canvas.reset_view();
        }
        self.file_path = path.to_string();
        self.measure_distance = None;
        self.measure_info = None;
        let t0 = Instant::now();

        match parser::MapInterpreter::load_file(path) {
            Ok(mut env) => {
                env.cp_arbdistribution = self.cp_arbdistribution_override;
                let mut map_plot = MapPlot::new(env, Some(self.default_step));

                // Set up other track colors
                self.othertrack_settings.clear();
                let mut color_idx = 0;
                let othertrack_keys: Vec<String> = map_plot
                    .environment
                    .othertrack
                    .data
                    .keys()
                    .cloned()
                    .collect();
                for key in othertrack_keys {
                    let color = self.othertrack_colors[color_idx % self.othertrack_colors.len()];
                    let color_hex = color_to_hex(color);
                    map_plot.environment.othertrack_linecolor.insert(
                        key.clone(),
                        TrackLineColor {
                            current: color_hex.clone(),
                            default: color_hex,
                        },
                    );
                    self.othertrack_settings.insert(
                        key.clone(),
                        OtherTrackSettings {
                            visible: false,
                            color,
                            dist_min: map_plot
                                .environment
                                .othertrack
                                .cp_range
                                .get(&key)
                                .map(|r| r.min)
                                .unwrap_or(0.0),
                            dist_max: map_plot
                                .environment
                                .othertrack
                                .cp_range
                                .get(&key)
                                .map(|r| r.max)
                                .unwrap_or(0.0),
                        },
                    );
                    color_idx += 1;
                }

                // Station list
                let mut stn_list: Vec<_> = map_plot
                    .environment
                    .station
                    .position
                    .iter()
                    .map(|(d, k)| {
                        let name = map_plot
                            .environment
                            .station
                            .stationkey
                            .get(k)
                            .cloned()
                            .unwrap_or_else(|| k.clone());
                        (d.0, k.clone(), name)
                    })
                    .collect();
                stn_list.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
                self.station_list = stn_list;

                // Distance range
                if !map_plot.environment.station.position.is_empty() {
                    let s_min = map_plot
                        .environment
                        .station
                        .position
                        .keys()
                        .fold(f64::INFINITY, |a, b| a.min(b.0));
                    let s_max = map_plot
                        .environment
                        .station
                        .position
                        .keys()
                        .fold(f64::NEG_INFINITY, |a, b| a.max(b.0));
                    self.distrange_min = (s_min / 100.0).floor() * 100.0 - 500.0;
                    self.distrange_max = (s_max / 100.0).ceil() * 100.0 + 500.0;
                } else {
                    let cp = &map_plot.environment.controlpoints.list_cp;
                    let cp_min = cp.iter().fold(f64::INFINITY, |a, &b| a.min(b));
                    let cp_max = cp.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
                    self.distrange_min = (cp_min / 100.0).floor() * 100.0 - 500.0;
                    self.distrange_max = (cp_max / 100.0).ceil() * 100.0 + 500.0;
                }
                self.dmin = Some(self.distrange_min);
                self.dmax = Some(self.distrange_max);

                let dur = t0.elapsed().as_secs_f64();
                self.status_text = format!("Map loaded in {:.2}s", dur);
                self.load_time = dur;

                self.env = Some(map_plot.environment.clone());
                self.map_plot = Some(map_plot);
            }
            Err(e) => {
                let msg = format!("Error loading file: {}", e);
                self.status_text = msg.clone();
                self.error_message = Some(msg);
            }
        }
    }

    fn get_checked_other_tracks(&self) -> Vec<String> {
        self.othertrack_settings
            .iter()
            .filter(|(_, s)| s.visible)
            .map(|(k, _)| k.clone())
            .collect()
    }

    fn save_trackdata(&mut self) {
        let Some(map_plot) = self.map_plot.as_ref() else {
            self.status_text = "No map loaded".to_string();
            return;
        };
        let Some(dir) = rfd::FileDialog::new().pick_folder() else {
            return;
        };

        let base = dir
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| "kobushi".to_string());

        let result = (|| -> std::io::Result<()> {
            let own_path = dir.join(format!("{}_owntrack.csv", base));
            write_owntrack_csv(&own_path, &map_plot.environment.owntrack_pos)?;

            for (key, data) in &map_plot.environment.othertrack_pos {
                let safe_key = sanitize_filename_component(key);
                let path = dir.join(format!("{}_{}.csv", base, safe_key));
                write_othertrack_csv(&path, data)?;
            }
            Ok(())
        })();

        self.status_text = match result {
            Ok(()) => format!("Track data saved to {}", dir.display()),
            Err(e) => format!("Save error: {}", e),
        };
    }

    fn save_plots(&mut self) {
        let Some(map_plot) = self.map_plot.as_ref() else {
            self.status_text = "No map loaded".to_string();
            return;
        };
        let Some(path) = rfd::FileDialog::new()
            .add_filter("SVG", &["svg"])
            .add_filter("PNG", &["png"])
            .set_file_name("kobushi.svg")
            .save_file()
        else {
            return;
        };

        let checked = self.get_checked_other_tracks();
        let is_png = path
            .extension()
            .map(|e| e.to_str().unwrap_or("") == "png")
            .unwrap_or(false);

        let result = if is_png {
            self.save_plots_png(&path, map_plot, self.dmin, self.dmax, &checked, self.show_prof_othert)
        } else {
            write_plot_svgs(
                &path,
                map_plot,
                self.dmin,
                self.dmax,
                &checked,
                self.show_prof_othert,
            )
        };
        self.status_text = match result {
            Ok(()) => format!("Plots saved near {}", path.display()),
            Err(e) => format!("Save error: {}", e),
        };
    }

    fn save_plots_png(
        &self,
        base_path: &std::path::Path,
        map_plot: &MapPlot,
        dmin: Option<f64>,
        dmax: Option<f64>,
        checked_othertracks: &[String],
        show_profile_othertracks: bool,
    ) -> std::io::Result<()> {
        let plane = map_plot.plane_data(dmin, dmax, checked_othertracks);
        let profile_other = if show_profile_othertracks { checked_othertracks } else { &[] };
        let profile = map_plot.profile_data(dmin, dmax, profile_other, None);

        let stem = base_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("kobushi");

        // Save plan view as PNG
        if !plane.owntrack.is_empty() {
            let path = base_path.with_file_name(format!("{}_plan.png", stem));
            write_png_image(&path, &render_plane_to_pixels(&plane, 1920, 1080))?;
        }

        // Save profile view as PNG
        if !profile.owntrack.is_empty() {
            let path = base_path.with_file_name(format!("{}_profile.png", stem));
            write_png_image(&path, &render_profile_to_pixels(&profile, 1920, 1080))?;
        }

        // Save radius view as PNG
        if !profile.curve.is_empty() {
            let path = base_path.with_file_name(format!("{}_radius.png", stem));
            write_png_image(&path, &render_radius_to_pixels(&profile, 1920, 1080))?;
        }

        Ok(())
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Top menu bar
        egui::TopBottomPanel::top("menu_bar").show(ctx, |ui| {
            egui::menu::bar(ui, |ui| {
                ui.menu_button(i18n::get("menu.file"), |ui| {
                    if ui.button(i18n::get("menu.open")).clicked() {
                        if let Some(path) = rfd::FileDialog::new().pick_file() {
                            let p = path.to_string_lossy().to_string();
                            self.open_file(&p);
                        }
                        ui.close_menu();
                    }
                    if ui.button(i18n::get("menu.reload")).clicked() {
                        if !self.file_path.is_empty() {
                            let p = self.file_path.clone();
                            self.open_file(&p);
                        }
                        ui.close_menu();
                    }
                    ui.separator();
                    if ui.button(i18n::get("menu.save_image")).clicked() {
                        self.save_plots();
                        ui.close_menu();
                    }
                    if ui.button(i18n::get("menu.save_trackdata")).clicked() {
                        self.save_trackdata();
                        ui.close_menu();
                    }
                    ui.separator();
                    if ui.button(i18n::get("menu.exit")).clicked() {
                        self.show_quit_dialog = true;
                        ui.close_menu();
                    }
                });

                ui.menu_button(i18n::get("menu.options"), |ui| {
                    if ui.button(i18n::get("menu.controlpoints")).clicked() {
                        if self.env.is_some() {
                            self.show_cp_dialog = true;
                            let cp = self.env.as_ref().unwrap();
                            let cp_min = cp
                                .controlpoints
                                .list_cp
                                .iter()
                                .fold(f64::INFINITY, |a, &b| a.min(b));
                            let cp_max = cp
                                .controlpoints
                                .list_cp
                                .iter()
                                .fold(f64::NEG_INFINITY, |a, &b| a.max(b));
                            self.cp_min = format!("{}", cp_min);
                            self.cp_max = format!("{}", cp_max);
                            self.cp_interval = "25".to_string();
                        }
                        ui.close_menu();
                    }
                    if ui.button(i18n::get("menu.plotlimit")).clicked() {
                        self.show_plotlimit_dialog = true;
                        self.plotlimit_min = format!("{}", self.distrange_min);
                        self.plotlimit_max = format!("{}", self.distrange_max);
                        ui.close_menu();
                    }
                    if ui.button(i18n::get("menu.font")).clicked() {
                        self.show_font_dialog = true;
                        ui.close_menu();
                    }
                });

                ui.menu_button(i18n::get("menu.lang"), |ui| {
                    if ui.button("日本語").clicked() {
                        i18n::set_language(i18n::JA);
                        ui.close_menu();
                    }
                    if ui.button("English").clicked() {
                        i18n::set_language(i18n::EN);
                        ui.close_menu();
                    }
                    if ui.button("简体中文").clicked() {
                        i18n::set_language(i18n::ZH);
                        ui.close_menu();
                    }
                });

                ui.menu_button(i18n::get("menu.help"), |ui| {
                    if ui.button(i18n::get("menu.about")).clicked() {
                        self.show_about = true;
                        ui.close_menu();
                    }
                });
            });
        });

        // Dialogs
        self.show_dialogs(ctx);

        // Check for panics / errors from other threads
        if let Ok(mut guard) = self.error_state.lock() {
            if let Some(msg) = guard.take() {
                self.error_message = Some(msg);
            }
        }

        // Error modal
        if let Some(ref msg) = self.error_message.clone() {
                egui::Window::new(i18n::get("dialog.error_title"))
                .collapsible(false)
                .resizable(false)
                .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
                .show(ctx, |ui| {
                    ui.colored_label(Color32::from_rgb(0xff, 0x55, 0x55), msg);
                    ui.add_space(8.0);
                    if ui.button("OK").clicked() {
                        self.error_message = None;
                    }
                });
        }

        // Main layout
        egui::SidePanel::right("control_panel")
            .min_width(200.0)
            .resizable(true)
            .show(ctx, |ui| {
                self.control_panel(ui);
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            // File open row
            ui.horizontal(|ui| {
                if ui.button(i18n::get("button.open")).clicked() {
                    if let Some(path) = rfd::FileDialog::new().pick_file() {
                        let p = path.to_string_lossy().to_string();
                        self.open_file(&p);
                    }
                }
                ui.label(&self.file_path);
            });

            if !self.status_text.is_empty() {
                ui.label(&self.status_text);
            }

            if let Some(map_plot) = self.map_plot.take() {
                let available = ui.available_size();
                let plane_height = available.y * 0.55;
                let profile_height = (available.y - plane_height - 20.0) * 0.5;

                // Plan view
                let (plane_resp, plane_painter) = ui.allocate_painter(
                    Vec2::new(available.x, plane_height),
                    Sense::click_and_drag(),
                );
                self.draw_view(&plane_painter, &plane_resp, ViewType::Plane, &map_plot);

                ui.separator();

                // Profile + Radius split
                let show_gradient = self.show_gradient_graph;
                let show_curve = self.show_curve_graph;
                if show_gradient || show_curve {
                    ui.horizontal(|ui| {
                        ui.spacing_mut().item_spacing.x = 10.0;
                        let both = show_gradient && show_curve;
                        let prof_width = if both {
                            available.x * 0.65
                        } else {
                            available.x
                        };
                        let rad_width = if both {
                            (available.x - prof_width - 10.0).max(1.0)
                        } else {
                            available.x
                        };

                        if show_gradient {
                            let (prof_resp, prof_painter) = ui.allocate_painter(
                                Vec2::new(prof_width, profile_height),
                                Sense::click_and_drag(),
                            );
                            self.draw_view(&prof_painter, &prof_resp, ViewType::Profile, &map_plot);
                        }

                        if show_curve {
                            let (rad_resp, rad_painter) = ui.allocate_painter(
                                Vec2::new(rad_width, profile_height),
                                Sense::click_and_drag(),
                            );
                            self.draw_view(&rad_painter, &rad_resp, ViewType::Radius, &map_plot);
                        }
                    });
                }

                // Measure info
                if let Some(ref info) = self.measure_info {
                    ui.horizontal(|ui| {
                        let speed_text = if let Some(s) = info.speed {
                            format!("{:.0} km/h", s)
                        } else {
                            i18n::get("info.no_limit")
                        };
                        ui.label(format!(
                            "{}: {:.0}m | {}: {:.1}m | {}: {:.1}‰ | {}: {:.0}m | {}: {}",
                            i18n::get("info.mileage"),
                            info.mileage,
                            i18n::get("info.elevation"),
                            info.elevation,
                            i18n::get("info.gradient"),
                            info.gradient,
                            i18n::get("info.radius"),
                            info.radius,
                            i18n::get("info.speedlimit"),
                            speed_text,
                        ));
                    });
                }

                // Station jump
                if !self.station_list.is_empty() {
                    ui.horizontal(|ui| {
                        ui.label(i18n::get("label.station_jump"));
                        let names: Vec<String> = self
                            .station_list
                            .iter()
                            .map(|(_, k, name)| format!("{}, {}", k, name))
                            .collect();
                        egui::ComboBox::new("station_jump", "")
                            .selected_text(if self.selected_station < names.len() {
                                names[self.selected_station].clone()
                            } else {
                                String::new()
                            })
                            .show_ui(ui, |ui| {
                                for (i, name) in names.iter().enumerate() {
                                    if ui
                                        .selectable_value(&mut self.selected_station, i, name)
                                        .clicked()
                                    {
                                        let dist = self.station_list[i].0;
                                        let data = map_plot.plane_data(self.dmin, self.dmax, &[]);
                                        for s in &data.stations {
                                            if (s.distance - dist).abs() < 1e-9 {
                                                self.plane_canvas.center = [s.point[1], s.point[2]];
                                                break;
                                            }
                                        }
                                        self.profile_canvas.center[0] = dist;
                                        self.radius_canvas.center[0] = dist;
                                    }
                                }
                            });
                    });
                }
                self.map_plot = Some(map_plot);
            }
        });

        ctx.request_repaint();
    }
}

#[derive(Clone, Copy, PartialEq)]
enum ViewType {
    Plane,
    Profile,
    Radius,
}

impl App {
    fn control_panel(&mut self, ui: &mut Ui) {
        ui.strong(i18n::get("frame.mode"));
        ui.radio_value(&mut self.mode, ViewMode::Pan, i18n::get("mode.pan"));
        ui.radio_value(&mut self.mode, ViewMode::Measure, i18n::get("mode.measure"));
        ui.separator();

        ui.strong(i18n::get("frame.grid"));
        ui.radio_value(
            &mut self.grid_mode,
            "fixed".to_string(),
            i18n::get("grid.fixed"),
        );
        ui.radio_value(
            &mut self.grid_mode,
            "movable".to_string(),
            i18n::get("grid.movable"),
        );
        ui.radio_value(
            &mut self.grid_mode,
            "none".to_string(),
            i18n::get("grid.none"),
        );
        ui.separator();

        ui.strong(i18n::get("frame.chart_visibility"));
        ui.checkbox(
            &mut self.show_gradient_graph,
            i18n::get("chk.gradient_graph"),
        );
        ui.checkbox(&mut self.show_curve_graph, i18n::get("chk.curve_graph"));
        if self.show_gradient_graph {
            let mut gp = self.show_gradient_pos;
            if ui
                .checkbox(&mut gp, i18n::get("chk.gradient_pos"))
                .changed()
            {
                self.show_gradient_pos = gp;
            }
            if self.show_gradient_pos {
                ui.indent("gradient", |ui| {
                    ui.checkbox(&mut self.show_gradient_val, i18n::get("chk.gradient_val"));
                });
            }
            ui.checkbox(&mut self.show_prof_othert, i18n::get("chk.prof_othert"));
        }
        ui.separator();

        ui.strong(i18n::get("frame.aux_info"));
        let mut sp = self.show_station_pos;
        if ui.checkbox(&mut sp, i18n::get("chk.station_pos")).changed() {
            self.show_station_pos = sp;
        }
        if self.show_station_pos {
            ui.indent("station", |ui| {
                ui.checkbox(&mut self.show_station_name, i18n::get("chk.station_name"));
                ui.checkbox(
                    &mut self.show_station_mileage,
                    i18n::get("chk.station_mileage"),
                );
            });
        }
        ui.checkbox(&mut self.show_curve_val, i18n::get("chk.curve_val"));
        ui.checkbox(&mut self.show_speedlimit, i18n::get("chk.speedlimit"));

        // Other tracks
        if !self.othertrack_settings.is_empty() {
            ui.separator();
            ui.collapsing("Other Tracks", |ui| {
                let keys: Vec<String> = self.othertrack_settings.keys().cloned().collect();
                for key in &keys {
                    if let Some(settings) = self.othertrack_settings.get_mut(key) {
                        let label = if key.is_empty() {
                            "(root)"
                        } else {
                            key.as_str()
                        };
                        ui.horizontal(|ui| {
                            ui.checkbox(&mut settings.visible, label);
                            ui.colored_label(settings.color, "■");
                            ui.label(format!(
                                "{:.0} - {:.0} m",
                                settings.dist_min, settings.dist_max
                            ));
                        });
                    }
                }
            });
        }
    }

    fn draw_view(
        &mut self,
        painter: &Painter,
        response: &Response,
        view_type: ViewType,
        map_plot: &MapPlot,
    ) {
        let rect = response.rect;
        let mut canvas = match view_type {
            ViewType::Plane => std::mem::replace(&mut self.plane_canvas, CanvasState::new()),
            ViewType::Profile => std::mem::replace(&mut self.profile_canvas, CanvasState::new()),
            ViewType::Radius => std::mem::replace(&mut self.radius_canvas, CanvasState::new()),
        };

        let width = rect.width() as f64;
        let height = rect.height() as f64;

        // Handle auto-fit on first draw
        if !canvas.view_fitted {
            if canvas.bounds.is_some() {
                canvas.fit(width, height);
            }
        }

        // Handle interactions
        let mode = self.mode;
        if mode == ViewMode::Pan {
            self.handle_canvas_input(&mut canvas, response, rect, view_type, map_plot);
        } else {
            self.handle_measure_interaction(&mut canvas, response, rect, view_type, map_plot);
        }

        // Background
        painter.rect_filled(rect, 0.0, canvas.background);

        // Grid
        canvas.grid_mode = self.grid_mode.clone();
        if canvas.grid_mode != "none" {
            self.draw_grid(painter, &canvas, rect);
        }

        // Title
        if !canvas.title.is_empty() {
            painter.text(
                Pos2::new(rect.left() + 8.0, rect.top() + 4.0),
                egui::Align2::LEFT_TOP,
                &canvas.title,
                FontId::proportional(self.font_size),
                canvas.text_color,
            );
        }

        // Content
        match view_type {
            ViewType::Plane => self.draw_plane_view(painter, &mut canvas, rect, map_plot),
            ViewType::Profile => self.draw_profile_view(painter, &mut canvas, rect, map_plot),
            ViewType::Radius => self.draw_radius_view(painter, &mut canvas, rect, map_plot),
        }

        // Scalebar
        if canvas.scalebar && view_type == ViewType::Plane {
            CanvasPainter::draw_scalebar(painter, &canvas, rect);
        }

        // Measure crosshair
        if canvas.measure_crosshair {
            if let Some(dist) = canvas.measure_pos {
                if view_type == ViewType::Plane {
                    let own = &map_plot.environment.owntrack_pos;
                    if !own.is_empty() {
                        let idx = own.partition_point(|r| r[0] < dist).min(own.len() - 1);
                        let (sx, sy) =
                            canvas.world_to_screen(own[idx][1], own[idx][2], width, height);
                        painter.line_segment(
                            [
                                Pos2::new(sx as f32 - 12.0, sy as f32 - 12.0),
                                Pos2::new(sx as f32 + 12.0, sy as f32 + 12.0),
                            ],
                            Stroke::new(2.0, Color32::from_rgb(0xff, 0x33, 0x33)),
                        );
                        painter.line_segment(
                            [
                                Pos2::new(sx as f32 - 12.0, sy as f32 + 12.0),
                                Pos2::new(sx as f32 + 12.0, sy as f32 - 12.0),
                            ],
                            Stroke::new(2.0, Color32::from_rgb(0xff, 0x33, 0x33)),
                        );
                    }
                } else {
                    let (sx, _) = canvas.world_to_screen(dist, 0.0, width, height);
                    painter.line_segment(
                        [
                            Pos2::new(sx as f32, rect.top()),
                            Pos2::new(sx as f32, rect.bottom()),
                        ],
                        Stroke::new(1.0, Color32::from_rgb(0xff, 0x33, 0x33)),
                    );
                }
            }
        }

        match view_type {
            ViewType::Plane => self.plane_canvas = canvas,
            ViewType::Profile => self.profile_canvas = canvas,
            ViewType::Radius => self.radius_canvas = canvas,
        }
    }

    fn handle_canvas_input(
        &mut self,
        canvas: &mut CanvasState,
        response: &Response,
        rect: Rect,
        view_type: ViewType,
        _map_plot: &MapPlot,
    ) -> bool {
        let width = rect.width() as f64;
        let height = rect.height() as f64;

        // Scroll zoom
        if response.hovered() {
            let scroll = response.ctx.input(|i| i.smooth_scroll_delta);
            if scroll.y != 0.0 {
                let factor = if scroll.y > 0.0 { 1.15 } else { 1.0 / 1.15 };
                if canvas.zoom_x_by_default || view_type == ViewType::Plane {
                    canvas.zoom(factor, "both");
                } else {
                    canvas.zoom(factor, "x");
                }
                return true;
            }
        }

        // Drag to pan
        if response.dragged() {
            let delta = response.drag_delta();
            canvas.pan(-delta.x as f64, -delta.y as f64, width, height);
            return true;
        }

        // Right-click rotate (plane only)
        if view_type == ViewType::Plane && response.hovered() {
            if response
                .ctx
                .input(|i| i.pointer.button_down(egui::PointerButton::Secondary))
            {
                if let Some(pos) = response.hover_pos() {
                    if let Some(prev) = canvas_prev_pos(&response.ctx) {
                        let dx = pos.x - prev.x;
                        let dy = pos.y - prev.y;
                        if dx.abs() > 0.5 || dy.abs() > 0.5 {
                            canvas.rotate(dx as f64 * 0.01);
                        }
                    }
                    set_canvas_prev_pos(&response.ctx, pos);
                }
            }
        }

        // Double-click to fit
        if response.double_clicked() {
            if canvas.bounds.is_some() {
                canvas.fit(width, height);
            }
            return true;
        }

        false
    }

    fn handle_measure_interaction(
        &mut self,
        canvas: &mut CanvasState,
        response: &Response,
        rect: Rect,
        view_type: ViewType,
        map_plot: &MapPlot,
    ) {
        let width = rect.width() as f64;
        let height = rect.height() as f64;
        let own = &map_plot.environment.owntrack_pos;

        if own.is_empty() {
            return;
        }

        if let Some(hover_pos) = response.hover_pos() {
            let (wx, wy) =
                canvas.screen_to_world(hover_pos.x as f64, hover_pos.y as f64, width, height);

            let distance = match view_type {
                ViewType::Plane => {
                    let mut min_dist = f64::INFINITY;
                    let mut best_dist = 0.0;
                    for row in own {
                        let d = ((row[1] - wx).powi(2) + (row[2] - wy).powi(2)).sqrt();
                        if d < min_dist {
                            min_dist = d;
                            best_dist = row[0];
                        }
                    }
                    // Check screen distance
                    let idx = own.partition_point(|r| r[0] < best_dist).min(own.len() - 1);
                    let (sx, sy) = canvas.world_to_screen(own[idx][1], own[idx][2], width, height);
                    let screen_d = ((sx - hover_pos.x as f64).powi(2)
                        + (sy - hover_pos.y as f64).powi(2))
                    .sqrt();
                    if screen_d <= 30.0 {
                        Some(best_dist)
                    } else {
                        None
                    }
                }
                ViewType::Profile | ViewType::Radius => {
                    if wx >= own[0][0] && wx <= own[own.len() - 1][0] {
                        Some(wx)
                    } else {
                        None
                    }
                }
            };

            if let Some(dist) = distance {
                canvas.measure_pos = Some(dist);
                canvas.measure_crosshair = true;
                self.measure_distance = Some(dist);
                self.measure_info = map_plot.get_track_info_at(dist);
            } else {
                canvas.measure_crosshair = false;
                canvas.measure_pos = None;
                self.measure_distance = None;
                self.measure_info = None;
            }
        }

        // Double-click to pan views to measured position
        if response.double_clicked() {
            if let Some(dist) = self.measure_distance {
                if view_type == ViewType::Plane {
                    let idx = own.partition_point(|r| r[0] < dist).min(own.len() - 1);
                    canvas.center = [own[idx][1], own[idx][2]];
                    self.profile_canvas.center[0] = dist;
                    self.radius_canvas.center[0] = dist;
                } else {
                    canvas.center[0] = dist;
                    match view_type {
                        ViewType::Profile => self.radius_canvas.center[0] = dist,
                        ViewType::Radius => self.profile_canvas.center[0] = dist,
                        ViewType::Plane => {}
                    }
                }
                canvas.measure_pos = Some(dist);
                canvas.measure_crosshair = true;
                if view_type != ViewType::Profile {
                    self.profile_canvas.measure_pos = Some(dist);
                    self.profile_canvas.measure_crosshair = true;
                }
                if view_type != ViewType::Radius {
                    self.radius_canvas.measure_pos = Some(dist);
                    self.radius_canvas.measure_crosshair = true;
                }
            }
        }
    }

    fn draw_grid(&self, painter: &Painter, canvas: &CanvasState, rect: Rect) {
        if canvas.grid_mode == "fixed" {
            let spacing = 80.0;
            let mut x = rect.left() as f64;
            while x <= rect.right() as f64 {
                painter.line_segment(
                    [
                        Pos2::new(x as f32, rect.top()),
                        Pos2::new(x as f32, rect.bottom()),
                    ],
                    Stroke::new(1.0, canvas.grid_color),
                );
                x += spacing;
            }
            let mut y = rect.top() as f64;
            while y <= rect.bottom() as f64 {
                painter.line_segment(
                    [
                        Pos2::new(rect.left(), y as f32),
                        Pos2::new(rect.right(), y as f32),
                    ],
                    Stroke::new(1.0, canvas.grid_color),
                );
                y += spacing;
            }
        }
    }

    fn draw_plane_view(
        &self,
        painter: &Painter,
        canvas: &mut CanvasState,
        rect: Rect,
        map_plot: &MapPlot,
    ) {
        let checked = self.get_checked_other_tracks();
        let data = map_plot.plane_data(self.dmin, self.dmax, &checked);

        if data.owntrack.is_empty() {
            return;
        }

        canvas.bounds = Some(data.bounds);

        // Curve sections background
        if self.show_curve_val {
            for sec in &data.curve_sections {
                let pts: Vec<[f64; 2]> = data
                    .owntrack
                    .iter()
                    .filter(|r| r[0] >= sec.start && r[0] <= sec.end)
                    .map(|r| [r[1], r[2]])
                    .collect();
                CanvasPainter::draw_world_line(
                    painter,
                    canvas,
                    &pts,
                    Color32::from_rgb(0x88, 0x88, 0x88),
                    10.0,
                    rect,
                );
            }
            for sec in &data.transition_sections {
                let pts: Vec<[f64; 2]> = data
                    .owntrack
                    .iter()
                    .filter(|r| r[0] >= sec.start && r[0] <= sec.end)
                    .map(|r| [r[1], r[2]])
                    .collect();
                CanvasPainter::draw_world_line(
                    painter,
                    canvas,
                    &pts,
                    Color32::from_rgb(0x55, 0x55, 0x55),
                    8.0,
                    rect,
                );
            }
        }

        // Own track
        let own_pts: Vec<[f64; 2]> = data.owntrack.iter().map(|r| [r[1], r[2]]).collect();
        CanvasPainter::draw_world_line(painter, canvas, &own_pts, Color32::WHITE, 2.0, rect);

        // Other tracks
        for ot in &data.othertracks {
            let hex = ot.color.trim_start_matches('#');
            let color = if hex.len() == 6 {
                let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(255);
                let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(255);
                let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(255);
                Color32::from_rgb(r, g, b)
            } else {
                Color32::WHITE
            };
            CanvasPainter::draw_world_line(painter, canvas, &ot.points, color, 1.0, rect);
        }

        // Stations
        if self.show_station_pos {
            for station in &data.stations {
                let (sx, sy) = canvas.world_to_screen(
                    station.point[1],
                    station.point[2],
                    rect.width() as f64,
                    rect.height() as f64,
                );
                painter.circle_filled(Pos2::new(sx as f32, sy as f32), 4.0, Color32::WHITE);
                if self.show_station_name {
                    CanvasPainter::draw_world_text(
                        painter,
                        canvas,
                        station.point[1],
                        station.point[2],
                        &station.name,
                        Color32::WHITE,
                        (8.0, -8.0),
                        self.font_size,
                        rect,
                        None,
                    );
                }
                if self.show_station_mileage {
                    CanvasPainter::draw_world_text(
                        painter,
                        canvas,
                        station.point[1],
                        station.point[2],
                        &format!("{:.0}m", station.mileage),
                        Color32::from_rgb(0xff, 0xd8, 0x4d),
                        (8.0, 8.0),
                        self.font_size * 0.85,
                        rect,
                        None,
                    );
                }
            }
        }

        // Speed limits
        if self.show_speedlimit {
            for sp in &data.speedlimits {
                let (sx, sy) =
                    canvas.world_to_screen(sp.x, sp.y, rect.width() as f64, rect.height() as f64);
                let t = sp.theta;
                let wx_perp = sp.x - t.sin();
                let wy_perp = sp.y + t.cos();
                let (sx_perp, sy_perp) = canvas.world_to_screen(
                    wx_perp,
                    wy_perp,
                    rect.width() as f64,
                    rect.height() as f64,
                );
                let sdx = sx_perp - sx;
                let sdy = sy_perp - sy;
                let screen_len = (sdx * sdx + sdy * sdy).sqrt();
                if screen_len > 0.0 {
                    let ndx = sdx / screen_len * 8.0;
                    let ndy = sdy / screen_len * 8.0;
                    painter.line_segment(
                        [
                            Pos2::new((sx - ndx) as f32, (sy - ndy) as f32),
                            Pos2::new((sx + ndx) as f32, (sy + ndy) as f32),
                        ],
                        Stroke::new(1.0, Color32::from_rgb(0x88, 0xcc, 0xff)),
                    );
                }
                let text = if let Some(speed) = sp.speed {
                    format!("{}", speed as i64)
                } else {
                    "x".to_string()
                };
                CanvasPainter::draw_world_text(
                    painter,
                    canvas,
                    sp.x,
                    sp.y,
                    &text,
                    Color32::from_rgb(0x88, 0xcc, 0xff),
                    (10.0, -15.0),
                    self.font_size * 0.9,
                    rect,
                    None,
                );
            }
        }

        // Curve radius labels
        if self.show_curve_val {
            for sec in &data.curve_sections {
                let mid = (sec.start + sec.end) / 2.0;
                let idx = data
                    .owntrack
                    .partition_point(|r| r[0] < mid)
                    .min(data.owntrack.len() - 1);
                let row = data.owntrack[idx];
                CanvasPainter::draw_world_text(
                    painter,
                    canvas,
                    row[1],
                    row[2],
                    &format!("{:.0}", sec.radius),
                    Color32::from_rgb(0x88, 0xff, 0x88),
                    (8.0, -16.0),
                    self.font_size * 0.85,
                    rect,
                    None,
                );
            }
        }
    }

    fn draw_profile_view(
        &self,
        painter: &Painter,
        canvas: &mut CanvasState,
        rect: Rect,
        map_plot: &MapPlot,
    ) {
        let checked = if self.show_prof_othert {
            self.get_checked_other_tracks()
        } else {
            Vec::new()
        };
        let data = map_plot.profile_data(self.dmin, self.dmax, &checked, None);

        if data.owntrack.is_empty() {
            return;
        }

        canvas.bounds = Some(data.bounds);

        // Own track
        let own_pts: Vec<[f64; 2]> = data.owntrack.iter().map(|r| [r[0], r[3]]).collect();
        CanvasPainter::draw_world_line(painter, canvas, &own_pts, Color32::WHITE, 2.0, rect);

        // Other tracks
        for ot in &data.othertracks {
            let pts: Vec<[f64; 2]> = ot.points.iter().map(|r| [r[0], r[3]]).collect();
            let hex = ot.color.trim_start_matches('#');
            let color = if hex.len() == 6 {
                let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(255);
                let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(255);
                let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(255);
                Color32::from_rgb(r, g, b)
            } else {
                Color32::WHITE
            };
            CanvasPainter::draw_world_line(painter, canvas, &pts, color, 1.0, rect);
        }

        // Stations
        if self.show_station_pos {
            for station in &data.stations {
                let (sx, sz) = canvas.world_to_screen(
                    station.point[0],
                    station.point[3],
                    rect.width() as f64,
                    rect.height() as f64,
                );
                painter.line_segment(
                    [
                        Pos2::new(sx as f32, sz as f32),
                        Pos2::new(sx as f32, rect.top() - 100.0),
                    ],
                    Stroke::new(1.0, Color32::WHITE),
                );
                painter.circle_filled(Pos2::new(sx as f32, sz as f32), 3.0, Color32::WHITE);

                if self.show_station_name {
                    CanvasPainter::draw_world_text(
                        painter,
                        canvas,
                        station.point[0],
                        station.point[3],
                        &station.name,
                        Color32::WHITE,
                        (8.0, -26.0),
                        self.font_size * 0.9,
                        rect,
                        None,
                    );
                }
                if self.show_station_mileage {
                    painter.text(
                        Pos2::new(sx as f32 + 8.0, rect.top() + 8.0),
                        egui::Align2::LEFT_TOP,
                        &format!("{:.0}m", station.mileage),
                        FontId::proportional(self.font_size * 0.85),
                        Color32::from_rgb(0xff, 0xd8, 0x4d),
                    );
                }
            }
        }

        // Gradient change points
        if self.show_gradient_pos {
            for point in &data.gradient_points {
                let (sx, sz) = canvas.world_to_screen(
                    point.x,
                    point.z,
                    rect.width() as f64,
                    rect.height() as f64,
                );
                painter.line_segment(
                    [
                        Pos2::new(sx as f32, sz as f32),
                        Pos2::new(sx as f32, rect.bottom() + 100.0),
                    ],
                    Stroke::new(1.0, Color32::WHITE),
                );
            }
            if self.show_gradient_val {
                for label in &data.gradient_labels {
                    let (sx, _) = canvas.world_to_screen(
                        label.x,
                        0.0,
                        rect.width() as f64,
                        rect.height() as f64,
                    );
                    painter.text(
                        Pos2::new(sx as f32 + 6.0, rect.bottom() - 6.0),
                        egui::Align2::RIGHT_BOTTOM,
                        &label.text,
                        FontId::proportional(self.font_size * 0.85),
                        Color32::WHITE,
                    );
                }
            }
        }
    }

    fn draw_radius_view(
        &self,
        painter: &Painter,
        canvas: &mut CanvasState,
        rect: Rect,
        map_plot: &MapPlot,
    ) {
        let data = map_plot.profile_data(self.dmin, self.dmax, &[], None);

        if data.curve.is_empty() && data.stations.is_empty() {
            return;
        }

        canvas.bounds = Some(data.radius_bounds);

        // Curve line
        if !data.curve.is_empty() {
            CanvasPainter::draw_world_line(painter, canvas, &data.curve, Color32::WHITE, 2.0, rect);
        }

        // Radius labels
        for label in &data.radius_labels {
            CanvasPainter::draw_world_text(
                painter,
                canvas,
                label.x,
                label.y,
                &label.text,
                Color32::WHITE,
                (-6.0, 0.0),
                self.font_size * 0.85,
                rect,
                None,
            );
        }

        // Stations
        if self.show_station_pos && !data.stations.is_empty() {
            for station in &data.stations {
                let (sx, _) = canvas.world_to_screen(
                    station.distance,
                    0.0,
                    rect.width() as f64,
                    rect.height() as f64,
                );
                if sx >= 0.0 && sx <= rect.width() as f64 {
                    painter.line_segment(
                        [
                            Pos2::new(sx as f32, rect.top()),
                            Pos2::new(sx as f32, rect.bottom()),
                        ],
                        Stroke::new(1.0, Color32::WHITE),
                    );
                    if self.show_station_name {
                        painter.text(
                            Pos2::new(sx as f32 + 8.0, rect.top() + 8.0),
                            egui::Align2::LEFT_TOP,
                            &station.name,
                            FontId::proportional(self.font_size * 0.9),
                            Color32::WHITE,
                        );
                    }
                    if self.show_station_mileage {
                        painter.text(
                            Pos2::new(sx as f32 + 8.0, rect.bottom() - 8.0),
                            egui::Align2::LEFT_BOTTOM,
                            &format!("{:.0}m", station.mileage),
                            FontId::proportional(self.font_size * 0.85),
                            Color32::from_rgb(0xff, 0xd8, 0x4d),
                        );
                    }
                }
            }
        }
    }

    fn show_dialogs(&mut self, ctx: &egui::Context) {
        if self.show_quit_dialog {
            egui::Window::new(i18n::get("dialog.quit"))
                .collapsible(false)
                .resizable(false)
                .show(ctx, |ui| {
                    ui.label(i18n::get("dialog.quit"));
                    ui.horizontal(|ui| {
                        if ui.button(i18n::get("button.ok")).clicked() {
                            std::process::exit(0);
                        }
                        if ui.button(i18n::get("button.cancel")).clicked() {
                            self.show_quit_dialog = false;
                        }
                    });
                });
        }

        if self.show_about {
            egui::Window::new(i18n::get("menu.about"))
                .collapsible(false)
                .resizable(false)
                .show(ctx, |ui| {
                    ui.label("Kobushi Track Viewer (Rust Rewrite)");
                    ui.label("Based on original Python project by konawasabi");
                    ui.label("Optimized with Rust + egui for GPU-accelerated rendering");
                    if ui.button("OK").clicked() {
                        self.show_about = false;
                    }
                });
        }

        if self.show_font_dialog {
            egui::Window::new(i18n::get("window.font"))
                .collapsible(false)
                .resizable(false)
                .show(ctx, |ui| {
                    ui.add(egui::Slider::new(&mut self.font_size, 8.0..=24.0).text("Size"));
                    ui.horizontal(|ui| {
                        if ui.button(i18n::get("button.ok")).clicked() {
                            self.show_font_dialog = false;
                        }
                        if ui.button(i18n::get("button.cancel")).clicked() {
                            self.show_font_dialog = false;
                        }
                    });
                });
        }

        if self.show_plotlimit_dialog {
            egui::Window::new(i18n::get("dialog.set_plotlimit"))
                .collapsible(false)
                .resizable(false)
                .show(ctx, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(i18n::get("dialog.plotlimit_min"));
                        ui.text_edit_singleline(&mut self.plotlimit_min);
                    });
                    ui.horizontal(|ui| {
                        ui.label(i18n::get("dialog.plotlimit_max"));
                        ui.text_edit_singleline(&mut self.plotlimit_max);
                    });
                    ui.horizontal(|ui| {
                        if ui.button(i18n::get("button.ok")).clicked() {
                            if let (Ok(lo), Ok(hi)) = (
                                self.plotlimit_min.parse::<f64>(),
                                self.plotlimit_max.parse::<f64>(),
                            ) {
                                self.distrange_min = lo;
                                self.distrange_max = hi;
                                self.dmin = Some(lo);
                                self.dmax = Some(hi);
                            }
                            self.show_plotlimit_dialog = false;
                        }
                        if ui.button(i18n::get("button.reset")).clicked() {
                            self.show_plotlimit_dialog = false;
                        }
                        if ui.button(i18n::get("button.cancel")).clicked() {
                            self.show_plotlimit_dialog = false;
                        }
                    });
                });
        }

        if self.show_cp_dialog {
            egui::Window::new(i18n::get("dialog.set_controlpoint"))
                .collapsible(false)
                .resizable(false)
                .show(ctx, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(i18n::get("dialog.cp_min"));
                        ui.text_edit_singleline(&mut self.cp_min);
                    });
                    ui.horizontal(|ui| {
                        ui.label(i18n::get("dialog.cp_max"));
                        ui.text_edit_singleline(&mut self.cp_max);
                    });
                    ui.horizontal(|ui| {
                        ui.label(i18n::get("dialog.cp_interval"));
                        ui.text_edit_singleline(&mut self.cp_interval);
                    });
                    ui.horizontal(|ui| {
                        if ui.button(i18n::get("button.ok")).clicked() {
                            if let (Ok(min), Ok(max), Ok(step)) = (
                                self.cp_min.parse::<f64>(),
                                self.cp_max.parse::<f64>(),
                                self.cp_interval.parse::<f64>(),
                            ) {
                                if let Some(ref mut env) = self.env {
                                    env.cp_arbdistribution = Some((min, max, step));
                                }
                                self.cp_arbdistribution_override = Some((min, max, step));
                                if !self.file_path.is_empty() {
                                    let p = self.file_path.clone();
                                    self.open_file(&p);
                                }
                            }
                            self.show_cp_dialog = false;
                        }
                        if ui.button(i18n::get("button.reset")).clicked() {
                            if let Some(ref mut env) = self.env {
                                env.cp_arbdistribution = None;
                            }
                            self.cp_arbdistribution_override = None;
                            if !self.file_path.is_empty() {
                                let p = self.file_path.clone();
                                self.open_file(&p);
                            }
                            self.show_cp_dialog = false;
                        }
                        if ui.button(i18n::get("button.cancel")).clicked() {
                            self.show_cp_dialog = false;
                        }
                    });
                });
        }
    }
}

// Helper to track previous hover position for rotation
thread_local! {
    static PREV_CANVAS_POS: std::cell::RefCell<Option<Pos2>> = std::cell::RefCell::new(None);
}

fn canvas_prev_pos(_ctx: &egui::Context) -> Option<Pos2> {
    PREV_CANVAS_POS.with(|c| *c.borrow())
}

fn set_canvas_prev_pos(_ctx: &egui::Context, pos: Pos2) {
    PREV_CANVAS_POS.with(|c| *c.borrow_mut() = Some(pos));
}

fn color_to_hex(color: Color32) -> String {
    format!("#{:02x}{:02x}{:02x}", color.r(), color.g(), color.b())
}

fn write_owntrack_csv(path: &std::path::Path, data: &[[f64; 11]]) -> std::io::Result<()> {
    let mut wtr = csv::Writer::from_path(path)?;
    wtr.write_record(&[
        "distance", "x", "y", "z", "direction", "radius", "gradient",
        "interpolate_func", "cant", "center", "gauge",
    ])?;
    for row in data {
        wtr.write_record(&[
            format!("{:.6}", row[0]),
            format!("{:.6}", row[1]),
            format!("{:.6}", row[2]),
            format!("{:.6}", row[3]),
            format!("{:.6}", row[4]),
            format!("{:.6}", row[5]),
            format!("{:.6}", row[6]),
            format!("{:.6}", row[7]),
            format!("{:.6}", row[8]),
            format!("{:.6}", row[9]),
            format!("{:.6}", row[10]),
        ])?;
    }
    wtr.flush()?;
    Ok(())
}

fn write_othertrack_csv(path: &std::path::Path, data: &[[f64; 8]]) -> std::io::Result<()> {
    let mut wtr = csv::Writer::from_path(path)?;
    wtr.write_record(&[
        "distance", "x", "y", "z", "interpolate_func", "cant", "center", "gauge",
    ])?;
    for row in data {
        wtr.write_record(&[
            format!("{:.6}", row[0]),
            format!("{:.6}", row[1]),
            format!("{:.6}", row[2]),
            format!("{:.6}", row[3]),
            format!("{:.6}", row[4]),
            format!("{:.6}", row[5]),
            format!("{:.6}", row[6]),
            format!("{:.6}", row[7]),
        ])?;
    }
    wtr.flush()?;
    Ok(())
}

fn sanitize_filename_component(value: &str) -> String {
    let cleaned: String = value
        .chars()
        .map(|c| {
            if matches!(c, '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*') || c.is_control() {
                '_'
            } else {
                c
            }
        })
        .collect();
    if cleaned.is_empty() {
        "root".to_string()
    } else {
        cleaned
    }
}

#[derive(Clone)]
struct SvgLine {
    points: Vec<[f64; 2]>,
    color: String,
    width: f64,
}

struct SvgLabel {
    x: f64,
    y: f64,
    text: String,
    color: String,
}

fn write_plot_svgs(
    base_path: &std::path::Path,
    map_plot: &MapPlot,
    dmin: Option<f64>,
    dmax: Option<f64>,
    checked_othertracks: &[String],
    show_profile_othertracks: bool,
) -> std::io::Result<()> {
    let plane = map_plot.plane_data(dmin, dmax, checked_othertracks);
    let mut plane_lines = Vec::new();
    for sec in &plane.curve_sections {
        let points: Vec<[f64; 2]> = plane
            .owntrack
            .iter()
            .filter(|r| r[0] >= sec.start && r[0] <= sec.end)
            .map(|r| [r[1], r[2]])
            .collect();
        plane_lines.push(SvgLine {
            points,
            color: "#888888".to_string(),
            width: 10.0,
        });
    }
    for sec in &plane.transition_sections {
        let points: Vec<[f64; 2]> = plane
            .owntrack
            .iter()
            .filter(|r| r[0] >= sec.start && r[0] <= sec.end)
            .map(|r| [r[1], r[2]])
            .collect();
        plane_lines.push(SvgLine {
            points,
            color: "#555555".to_string(),
            width: 8.0,
        });
    }
    plane_lines.push(SvgLine {
        points: plane.owntrack.iter().map(|r| [r[1], r[2]]).collect(),
        color: "#ffffff".to_string(),
        width: 2.0,
    });
    for ot in &plane.othertracks {
        plane_lines.push(SvgLine {
            points: ot.points.clone(),
            color: ot.color.clone(),
            width: 1.0,
        });
    }
    let plane_labels: Vec<SvgLabel> = plane
        .stations
        .iter()
        .map(|s| SvgLabel {
            x: s.point[1],
            y: s.point[2],
            text: s.name.clone(),
            color: "#ffffff".to_string(),
        })
        .collect();
    std::fs::write(
        sibling_svg_path(base_path, "plan"),
        svg_document("Plan", plane.bounds, true, &plane_lines, &plane_labels),
    )?;

    let profile_othertracks = if show_profile_othertracks {
        checked_othertracks
    } else {
        &[]
    };
    let profile = map_plot.profile_data(dmin, dmax, profile_othertracks, None);
    let mut profile_lines = vec![SvgLine {
        points: profile.owntrack.iter().map(|r| [r[0], r[3]]).collect(),
        color: "#ffffff".to_string(),
        width: 2.0,
    }];
    for ot in &profile.othertracks {
        profile_lines.push(SvgLine {
            points: ot.points.iter().map(|r| [r[0], r[3]]).collect(),
            color: ot.color.clone(),
            width: 1.0,
        });
    }
    let profile_labels: Vec<SvgLabel> = profile
        .stations
        .iter()
        .map(|s| SvgLabel {
            x: s.point[0],
            y: s.point[3],
            text: s.name.clone(),
            color: "#ffffff".to_string(),
        })
        .collect();
    std::fs::write(
        sibling_svg_path(base_path, "profile"),
        svg_document(
            "Gradient / Height",
            profile.bounds,
            false,
            &profile_lines,
            &profile_labels,
        ),
    )?;

    let radius_lines = vec![SvgLine {
        points: profile.curve.clone(),
        color: "#ffffff".to_string(),
        width: 2.0,
    }];
    let radius_labels: Vec<SvgLabel> = profile
        .radius_labels
        .iter()
        .map(|l| SvgLabel {
            x: l.x,
            y: l.y,
            text: l.text.clone(),
            color: "#ffffff".to_string(),
        })
        .collect();
    std::fs::write(
        sibling_svg_path(base_path, "radius"),
        svg_document(
            "Curve Radius",
            profile.radius_bounds,
            false,
            &radius_lines,
            &radius_labels,
        ),
    )?;

    Ok(())
}

fn sibling_svg_path(base_path: &std::path::Path, suffix: &str) -> std::path::PathBuf {
    let stem = base_path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "kobushi".to_string());
    let filename = format!("{}_{}.svg", stem, suffix);
    base_path.with_file_name(filename)
}

fn svg_document(
    title: &str,
    bounds: (f64, f64, f64, f64),
    y_axis_down: bool,
    lines: &[SvgLine],
    labels: &[SvgLabel],
) -> String {
    let width = 1400.0;
    let height = 900.0;
    let margin = 48.0;
    let (xmin, ymin, xmax, ymax) = normalize_bounds(bounds);
    let scale = ((width - margin * 2.0) / (xmax - xmin))
        .min((height - margin * 2.0) / (ymax - ymin))
        .max(1e-9);
    let content_w = (xmax - xmin) * scale;
    let content_h = (ymax - ymin) * scale;
    let x_offset = margin + (width - margin * 2.0 - content_w) / 2.0;
    let y_offset = margin + (height - margin * 2.0 - content_h) / 2.0;

    let project = |x: f64, y: f64| -> (f64, f64) {
        let sx = x_offset + (x - xmin) * scale;
        let sy = if y_axis_down {
            y_offset + (y - ymin) * scale
        } else {
            y_offset + (ymax - y) * scale
        };
        (sx, sy)
    };

    let mut out = String::new();
    out.push_str(&format!(
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{:.0}" height="{:.0}" viewBox="0 0 {:.0} {:.0}">"#,
        width, height, width, height,
    ));
    out.push_str(r##"<rect width="100%" height="100%" fill="#000000"/>"##);
    out.push_str(&format!(
        r##"<text x="16" y="24" fill="#ffffff" font-family="monospace" font-size="16">{}</text>"##,
        escape_xml(title),
    ));

    for line in lines {
        let points: Vec<String> = line
            .points
            .iter()
            .filter(|p| p[0].is_finite() && p[1].is_finite())
            .map(|p| {
                let (x, y) = project(p[0], p[1]);
                format!("{:.2},{:.2}", x, y)
            })
            .collect();
        if points.len() >= 2 {
            out.push_str(&format!(
                r#"<polyline points="{}" fill="none" stroke="{}" stroke-width="{:.2}" stroke-linejoin="round" stroke-linecap="round"/>"#,
                points.join(" "),
                escape_xml(&line.color),
                line.width,
            ));
        }
    }

    for label in labels {
        if label.x.is_finite() && label.y.is_finite() {
            let (x, y) = project(label.x, label.y);
            out.push_str(&format!(
                r#"<text x="{:.2}" y="{:.2}" dx="6" dy="-6" fill="{}" font-family="monospace" font-size="12">{}</text>"#,
                x,
                y,
                escape_xml(&label.color),
                escape_xml(&label.text),
            ));
        }
    }

    out.push_str("</svg>");
    out
}

fn normalize_bounds(bounds: (f64, f64, f64, f64)) -> (f64, f64, f64, f64) {
    let (mut xmin, mut ymin, mut xmax, mut ymax) = bounds;
    if !xmin.is_finite() || !ymin.is_finite() || !xmax.is_finite() || !ymax.is_finite() {
        return (-1.0, -1.0, 1.0, 1.0);
    }
    if (xmax - xmin).abs() < 1e-9 {
        xmin -= 1.0;
        xmax += 1.0;
    }
    if (ymax - ymin).abs() < 1e-9 {
        ymin -= 1.0;
        ymax += 1.0;
    }
    (xmin, ymin, xmax, ymax)
}

fn escape_xml(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

// ========== PNG image export ==========

fn write_png_image(path: &std::path::Path, pixels: &image::RgbaImage) -> std::io::Result<()> {
    pixels
        .save(path)
        .map_err(std::io::Error::other)
}

type PixelBuffer = image::ImageBuffer<image::Rgba<u8>, Vec<u8>>;

fn render_plane_to_pixels(data: &PlaneData, img_w: u32, img_h: u32) -> PixelBuffer {
    let margin = 48u32;
    let (xmin, ymin, xmax, ymax) = normalize_bounds(data.bounds);
    let scale = ((img_w - margin * 2) as f64 / (xmax - xmin))
        .min((img_h - margin * 2) as f64 / (ymax - ymin))
        .max(1e-9);
    let content_w = (xmax - xmin) * scale;
    let content_h = (ymax - ymin) * scale;
    let x_off = margin as f64 + ((img_w - margin * 2) as f64 - content_w) / 2.0;
    let y_off = margin as f64 + ((img_h - margin * 2) as f64 - content_h) / 2.0;

    let project = |x: f64, y: f64| -> (i32, i32) {
        let sx = x_off + (x - xmin) * scale;
        let sy = y_off + (y - ymin) * scale;
        (sx.round() as i32, sy.round() as i32)
    };

    let mut img = PixelBuffer::from_pixel(img_w, img_h, image::Rgba([0, 0, 0, 255]));

    // Curve sections background
    for sec in &data.curve_sections {
        let pts: Vec<(i32, i32)> = data
            .owntrack
            .iter()
            .filter(|r| r[0] >= sec.start && r[0] <= sec.end)
            .map(|r| project(r[1], r[2]))
            .collect();
        draw_polyline(&mut img, &pts, [0x88, 0x88, 0x88, 255], 5);
    }

    // Transition sections background
    for sec in &data.transition_sections {
        let pts: Vec<(i32, i32)> = data
            .owntrack
            .iter()
            .filter(|r| r[0] >= sec.start && r[0] <= sec.end)
            .map(|r| project(r[1], r[2]))
            .collect();
        draw_polyline(&mut img, &pts, [0x55, 0x55, 0x55, 255], 3);
    }

    // Own track
    let own_pts: Vec<(i32, i32)> = data.owntrack.iter().map(|r| project(r[1], r[2])).collect();
    draw_polyline(&mut img, &own_pts, [0xff, 0xff, 0xff, 255], 1);

    // Other tracks
    for ot in &data.othertracks {
        let hex = ot.color.trim_start_matches('#');
        let color = if hex.len() == 6 {
            [
                u8::from_str_radix(&hex[0..2], 16).unwrap_or(255),
                u8::from_str_radix(&hex[2..4], 16).unwrap_or(255),
                u8::from_str_radix(&hex[4..6], 16).unwrap_or(255),
                255,
            ]
        } else {
            [255, 255, 255, 255]
        };
        let pts: Vec<(i32, i32)> = ot.points.iter().map(|p| project(p[0], p[1])).collect();
        draw_polyline(&mut img, &pts, color, 1);
    }

    img
}

fn render_profile_to_pixels(data: &ProfileData, img_w: u32, img_h: u32) -> PixelBuffer {
    let margin = 48u32;
    let (xmin, ymin, xmax, ymax) = normalize_bounds(data.bounds);
    let scale = ((img_w - margin * 2) as f64 / (xmax - xmin))
        .min((img_h - margin * 2) as f64 / (ymax - ymin))
        .max(1e-9);
    let content_w = (xmax - xmin) * scale;
    let content_h = (ymax - ymin) * scale;
    let x_off = margin as f64 + ((img_w - margin * 2) as f64 - content_w) / 2.0;
    let y_off = margin as f64 + ((img_h - margin * 2) as f64 - content_h) / 2.0;

    let project = |x: f64, y: f64| -> (i32, i32) {
        let sx = x_off + (x - xmin) * scale;
        let sy = y_off + (ymax - y) * scale;
        (sx.round() as i32, sy.round() as i32)
    };

    let mut img = PixelBuffer::from_pixel(img_w, img_h, image::Rgba([0, 0, 0, 255]));

    // Own track
    let own_pts: Vec<(i32, i32)> = data.owntrack.iter().map(|r| project(r[0], r[3])).collect();
    draw_polyline(&mut img, &own_pts, [0xff, 0xff, 0xff, 255], 1);

    // Other tracks
    for ot in &data.othertracks {
        let pts: Vec<(i32, i32)> = ot.points.iter().map(|r| project(r[0], r[3])).collect();
        let hex = ot.color.trim_start_matches('#');
        let color = if hex.len() == 6 {
            [
                u8::from_str_radix(&hex[0..2], 16).unwrap_or(255),
                u8::from_str_radix(&hex[2..4], 16).unwrap_or(255),
                u8::from_str_radix(&hex[4..6], 16).unwrap_or(255),
                255,
            ]
        } else {
            [255, 255, 255, 255]
        };
        draw_polyline(&mut img, &pts, color, 1);
    }

    img
}

fn render_radius_to_pixels(data: &ProfileData, img_w: u32, img_h: u32) -> PixelBuffer {
    let margin = 48u32;
    let (xmin, ymin, xmax, ymax) = normalize_bounds(data.radius_bounds);
    let scale = ((img_w - margin * 2) as f64 / (xmax - xmin))
        .min((img_h - margin * 2) as f64 / (ymax - ymin))
        .max(1e-9);
    let content_w = (xmax - xmin) * scale;
    let content_h = (ymax - ymin) * scale;
    let x_off = margin as f64 + ((img_w - margin * 2) as f64 - content_w) / 2.0;
    let y_off = margin as f64 + ((img_h - margin * 2) as f64 - content_h) / 2.0;

    let project = |x: f64, y: f64| -> (i32, i32) {
        let sx = x_off + (x - xmin) * scale;
        let sy = y_off + (ymax - y) * scale;
        (sx.round() as i32, sy.round() as i32)
    };

    let mut img = PixelBuffer::from_pixel(img_w, img_h, image::Rgba([0, 0, 0, 255]));

    // Curve
    let curve_pts: Vec<(i32, i32)> = data.curve.iter().map(|r| project(r[0], r[1])).collect();
    draw_polyline(&mut img, &curve_pts, [0xff, 0xff, 0xff, 255], 1);

    img
}

fn draw_polyline(img: &mut PixelBuffer, points: &[(i32, i32)], color: [u8; 4], thickness: i32) {
    if points.len() < 2 {
        return;
    }
    for window in points.windows(2) {
        draw_line(img, window[0], window[1], color, thickness);
    }
}

fn draw_line(img: &mut PixelBuffer, start: (i32, i32), end: (i32, i32), color: [u8; 4], thickness: i32) {
    let (x0, y0) = start;
    let (x1, y1) = end;
    let dx = (x1 - x0).abs();
    let dy = -(y1 - y0).abs();
    let sx = if x0 < x1 { 1 } else { -1 };
    let sy = if y0 < y1 { 1 } else { -1 };
    let mut err = dx + dy;
    let (mut x, mut y) = (x0, y0);

    loop {
        for dy_off in -(thickness / 2)..=(thickness / 2) {
            for dx_off in -(thickness / 2)..=(thickness / 2) {
                let px = x + dx_off;
                let py = y + dy_off;
                if px >= 0 && (px as u32) < img.width() && py >= 0 && (py as u32) < img.height() {
                    img.put_pixel(px as u32, py as u32, image::Rgba(color));
                }
            }
        }
        if x == x1 && y == y1 {
            break;
        }
        let e2 = 2 * err;
        if e2 >= dy {
            if x == x1 {
                break;
            }
            err += dy;
            x += sx;
        }
        if e2 <= dx {
            if y == y1 {
                break;
            }
            err += dx;
            y += sy;
        }
    }
}
