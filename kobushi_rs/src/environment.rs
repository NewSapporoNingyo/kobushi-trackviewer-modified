use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct TrackElement {
    pub distance: f64,
    pub value: ValueOrContinue,
    pub key: String,
    pub flag: String,
}

#[derive(Debug, Clone)]
pub enum ValueOrContinue {
    Value(f64),
    Continue,
}

impl ValueOrContinue {
    pub fn is_continue(&self) -> bool {
        matches!(self, ValueOrContinue::Continue)
    }
    pub fn as_value(&self) -> f64 {
        match self {
            ValueOrContinue::Value(v) => *v,
            ValueOrContinue::Continue => 0.0,
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct Environment {
    pub rootpath: String,
    pub predef_vars: HashMap<String, f64>,
    pub variable: HashMap<String, f64>,
    pub own_track: Owntrack,
    pub station: Station,
    pub controlpoints: ControlPoints,
    pub othertrack: Othertrack,
    pub speedlimit: SpeedLimit,
    pub cp_arbdistribution: Option<(f64, f64, f64)>,
    pub cp_arbdistribution_default: Option<(f64, f64, f64)>,
    pub cp_defaultrange: (f64, f64),
    pub owntrack_pos: Vec<[f64; 11]>,
    pub owntrack_curve: Vec<[f64; 2]>,
    pub othertrack_pos: HashMap<String, Vec<[f64; 8]>>,
    pub othertrack_linecolor: HashMap<String, TrackLineColor>,
}

#[derive(Debug, Clone)]
pub struct TrackLineColor {
    pub current: String,
    pub default: String,
}

impl Environment {
    pub fn new() -> Self {
        let mut vars = HashMap::new();
        vars.insert("distance".to_string(), 0.0);
        Environment {
            rootpath: String::new(),
            predef_vars: vars,
            variable: HashMap::new(),
            own_track: Owntrack::default(),
            station: Station::default(),
            controlpoints: ControlPoints::default(),
            othertrack: Othertrack::default(),
            speedlimit: SpeedLimit::default(),
            cp_arbdistribution: None,
            cp_arbdistribution_default: None,
            cp_defaultrange: (0.0, 0.0),
            owntrack_pos: Vec::new(),
            owntrack_curve: Vec::new(),
            othertrack_pos: HashMap::new(),
            othertrack_linecolor: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct Owntrack {
    pub data: Vec<TrackElement>,
}

impl Owntrack {
    pub fn putdata(&mut self, key: &str, value: Option<f64>, flag: &str, distance: f64) {
        let v = match value {
            None => ValueOrContinue::Continue,
            Some(v) => ValueOrContinue::Value(v),
        };
        self.data.push(TrackElement {
            distance,
            value: v,
            key: key.to_string(),
            flag: flag.to_string(),
        });
    }

    pub fn relocate(&mut self) {
        self.data.sort_by(|a, b| {
            a.distance
                .partial_cmp(&b.distance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
    }
}

#[derive(Debug, Clone, Copy)]
pub struct StationDist(pub f64);

impl std::hash::Hash for StationDist {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.0.to_bits().hash(state);
    }
}

impl PartialEq for StationDist {
    fn eq(&self, other: &Self) -> bool {
        self.0.to_bits() == other.0.to_bits()
    }
}

impl Eq for StationDist {}

#[derive(Debug, Clone, Default)]
pub struct Station {
    pub position: HashMap<StationDist, String>,
    pub stationkey: HashMap<String, String>,
}

#[derive(Debug, Clone, Default)]
pub struct ControlPoints {
    pub list_cp: Vec<f64>,
}

impl ControlPoints {
    pub fn add(&mut self, value: f64) {
        self.list_cp.push(value);
    }
    pub fn relocate(&mut self) {
        self.list_cp
            .sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        self.list_cp.dedup();
    }
}

#[derive(Debug, Clone, Default)]
pub struct Othertrack {
    pub data: HashMap<String, Vec<TrackElement>>,
    pub cp_range: HashMap<String, CpRange>,
}

#[derive(Debug, Clone)]
pub struct CpRange {
    pub min: f64,
    pub max: f64,
}

impl Othertrack {
    pub fn putdata(
        &mut self,
        trackkey: &str,
        elementkey: &str,
        value: Option<f64>,
        flag: &str,
        distance: f64,
    ) {
        let tk = trackkey.to_lowercase();
        let v = match value {
            None => ValueOrContinue::Continue,
            Some(v) => ValueOrContinue::Value(v),
        };
        self.data.entry(tk.clone()).or_default().push(TrackElement {
            distance,
            value: v,
            key: elementkey.to_string(),
            flag: flag.to_string(),
        });
    }

    pub fn relocate(&mut self) {
        self.cp_range.clear();
        for (key, data) in self.data.iter_mut() {
            data.sort_by(|a, b| {
                a.distance
                    .partial_cmp(&b.distance)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
            if let (Some(first), Some(last)) = (data.first(), data.last()) {
                self.cp_range.insert(
                    key.clone(),
                    CpRange {
                        min: first.distance,
                        max: last.distance,
                    },
                );
            }
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct SpeedLimit {
    pub data: Vec<SpeedLimitEntry>,
}

#[derive(Debug, Clone)]
pub struct SpeedLimitEntry {
    pub distance: f64,
    pub speed: Option<f64>,
}

impl SpeedLimit {
    pub fn begin(&mut self, speed: Option<f64>, distance: f64) {
        self.data.push(SpeedLimitEntry { distance, speed });
    }
    pub fn end(&mut self, distance: f64) {
        self.data.push(SpeedLimitEntry {
            distance,
            speed: None,
        });
    }
    pub fn relocate(&mut self) {
        self.data.sort_by(|a, b| {
            a.distance
                .partial_cmp(&b.distance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
    }
}
