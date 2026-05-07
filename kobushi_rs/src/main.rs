#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app;
mod canvas;
mod environment;
mod i18n;
mod map_plot;
mod parser;
mod track_coordinate;
mod track_generator;
mod track_pointer;

use crate::app::App;
use eframe::NativeOptions;

fn main() -> Result<(), eframe::Error> {
    env_logger::init();

    let args: Vec<String> = std::env::args().collect();
    let mut step = 25.0;
    let mut font_name = "Monospace".to_string();
    let mut file_to_open: Option<String> = None;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "-s" | "--step" => {
                if i + 1 < args.len() {
                    step = args[i + 1].parse().unwrap_or(25.0);
                    i += 1;
                }
            }
            "-f" | "--font" => {
                if i + 1 < args.len() {
                    font_name = args[i + 1].clone();
                    i += 1;
                }
            }
            other => {
                if !other.starts_with('-') {
                    file_to_open = Some(other.to_string());
                }
            }
        }
        i += 1;
    }

    let options = NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1280.0, 800.0])
            .with_min_inner_size([800.0, 600.0]),
        ..Default::default()
    };

    eframe::run_native(
        "Kobushi Track Viewer",
        options,
        Box::new(move |_cc| {
            let mut app = App::new(step, &font_name);
            if let Some(ref path) = file_to_open {
                app.open_file(path);
            }
            Ok(Box::new(app))
        }),
    )
}
