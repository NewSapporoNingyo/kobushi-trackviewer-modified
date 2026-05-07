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
use std::sync::{Arc, Mutex};

fn load_cjk_font() -> Option<Vec<u8>> {
    let font_paths = [
        // Windows
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\msyh.ttf",
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "C:\\Windows\\Fonts\\yugoth.ttc",
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\simsun.ttc",
        // Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        // macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        // Bundled font (next to executable)
        "fonts/NotoSansSC-Regular.ttf",
        "font.ttf",
    ];

    for path in &font_paths {
        if let Ok(data) = std::fs::read(path) {
            log::info!("Loaded CJK font from: {}", path);
            return Some(data);
        }
    }
    log::warn!("No CJK font found. UI text may display as white boxes (tofu).");
    None
}

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

    let error_state: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));

    // Global panic hook: capture panic message for display in UI
    {
        let error_state = Arc::clone(&error_state);
        let default_hook = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            let msg = if let Some(s) = info.payload().downcast_ref::<&str>() {
                s.to_string()
            } else if let Some(s) = info.payload().downcast_ref::<String>() {
                s.clone()
            } else {
                "Unknown panic".to_string()
            };
            let location = info
                .location()
                .map(|l| format!(" at {}:{}", l.file(), l.line()))
                .unwrap_or_default();
            let full_msg = format!("PANIC: {}{}", msg, location);
            log::error!("{}", full_msg);
            if let Ok(mut guard) = error_state.lock() {
                *guard = Some(full_msg);
            }
            default_hook(info);
        }));
    }

    let cjk_font_data = load_cjk_font();

    let options = NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1280.0, 800.0])
            .with_min_inner_size([800.0, 600.0]),
        ..Default::default()
    };

    eframe::run_native(
        "Kobushi.rs",
        options,
        Box::new(move |cc| {
            // Configure egui fonts with CJK support
            if let Some(ref cjk_bytes) = cjk_font_data {
                let mut fonts = egui::FontDefinitions::default();
                let font_data = egui::FontData::from_owned(cjk_bytes.clone());
                fonts.font_data.insert("cjk".to_string(), std::sync::Arc::new(font_data));

                if let Some(proportional) = fonts.families.get_mut(&egui::FontFamily::Proportional) {
                    proportional.insert(0, "cjk".to_string());
                }
                if let Some(monospace) = fonts.families.get_mut(&egui::FontFamily::Monospace) {
                    monospace.insert(0, "cjk".to_string());
                }

                cc.egui_ctx.set_fonts(fonts);
            }

            let mut app = App::new(step, &font_name, error_state);
            if let Some(ref path) = file_to_open {
                app.open_file(path);
            }
            Ok(Box::new(app))
        }),
    )
}
