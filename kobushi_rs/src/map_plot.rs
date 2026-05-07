use crate::environment::*;
use crate::track_generator::{OtherTrackGenerator, TrackGenerator};
use crate::track_pointer::TrackPointer;
use rayon::prelude::*;
use std::collections::HashMap;

pub struct MapPlot {
    pub environment: Environment,
    pub distance_origin: f64,
    pub height_origin: f64,
    pub origin_angle: f64,
    pub distrange_plane: (f64, f64),
    pub distrange_vertical: (f64, f64),
    station_dist: Vec<f64>,
    station_pos: Vec<[f64; 11]>,
    pub no_station: bool,
}

impl MapPlot {
    pub fn new(mut env: Environment, unitdist_default: Option<f64>) -> Self {
        let mut gen = TrackGenerator::new(&env, unitdist_default);
        env.owntrack_pos = gen.generate_owntrack();
        env.owntrack_curve = gen.generate_curveradius_dist();

        // Generate other track positions in parallel
        let other_keys: Vec<String> = env.othertrack.data.keys().cloned().collect();
        let mut other_positions: HashMap<String, Vec<[f64; 8]>> = other_keys
            .par_iter()
            .filter_map(|key| {
                OtherTrackGenerator::new(&env, key).map(|gen| (key.clone(), gen.generate()))
            })
            .collect();

        for (key, pos) in other_positions.drain() {
            env.othertrack_pos.insert(key, pos);
        }

        if env.owntrack_pos.is_empty() {
            return MapPlot {
                environment: env,
                distance_origin: 0.0,
                height_origin: 0.0,
                origin_angle: 0.0,
                distrange_plane: (0.0, 0.0),
                distrange_vertical: (0.0, 0.0),
                station_dist: Vec::new(),
                station_pos: Vec::new(),
                no_station: true,
            };
        }

        let distrange = (
            env.owntrack_pos.first().map(|r| r[0]).unwrap_or(0.0),
            env.owntrack_pos.last().map(|r| r[0]).unwrap_or(0.0),
        );
        let start_distance = distrange.0;
        let height_origin = env
            .owntrack_pos
            .iter()
            .find(|r| (r[0] - start_distance).abs() < 1e-9)
            .map(|r| r[3])
            .unwrap_or(0.0);
        let origin_angle = env.owntrack_pos.first().map(|r| r[4]).unwrap_or(0.0);

        let (station_dist, station_pos, no_station) = if !env.station.position.is_empty() {
            let dist: Vec<f64> = env.station.position.keys().map(|k| k.0).collect();
            let pos: Vec<[f64; 11]> = env
                .owntrack_pos
                .iter()
                .filter(|r| env.station.position.contains_key(&StationDist(r[0])))
                .copied()
                .collect();
            (dist, pos, false)
        } else {
            (Vec::new(), Vec::new(), true)
        };

        MapPlot {
            environment: env,
            distance_origin: start_distance,
            height_origin,
            origin_angle,
            distrange_plane: distrange,
            distrange_vertical: distrange,
            station_dist,
            station_pos,
            no_station,
        }
    }

    pub fn plane_data(
        &self,
        distmin: Option<f64>,
        distmax: Option<f64>,
        othertrack_list: &[String],
    ) -> PlaneData {
        let dmin = distmin.unwrap_or(self.distrange_plane.0);
        let dmax = distmax.unwrap_or(self.distrange_plane.1);

        let owntrack = distance_filter(&self.environment.owntrack_pos, dmin, dmax);
        if owntrack.is_empty() {
            return PlaneData::empty();
        }

        let origin_angle = owntrack[0][4];
        let owntrack = rotate_track(&owntrack, -origin_angle);

        // Other tracks
        let mut othertracks = Vec::new();
        for key in othertrack_list {
            let tk = if key == "\\" { "" } else { key };
            if let Some(ot_data) = self.environment.othertrack_pos.get(tk) {
                let filtered = distance_filter_generic(
                    ot_data,
                    self.environment
                        .othertrack
                        .cp_range
                        .get(tk)
                        .map(|r| r.min.max(dmin))
                        .unwrap_or(dmin),
                    self.environment
                        .othertrack
                        .cp_range
                        .get(tk)
                        .map(|r| r.max.min(dmax))
                        .unwrap_or(dmax),
                    |r| r[0],
                );
                if !filtered.is_empty() {
                    let rotated = rotate_track_columns_ot(&filtered, -origin_angle, 1, 2);
                    let color = self
                        .environment
                        .othertrack_linecolor
                        .get(tk)
                        .map(|c| c.current.clone())
                        .unwrap_or_else(|| "#ffffff".to_string());
                    othertracks.push(OtherTrackData {
                        key: tk.to_string(),
                        points: rotated,
                        color,
                    });
                }
            }
        }

        let stations = self.station_points(dmin, dmax);
        let stations_rotated = rotate_track_columns(&stations, -origin_angle, 1, 2);
        let station_labels = self.station_labels(&stations_rotated);

        let bounds = Self::compute_bounds(&owntrack, &othertracks);
        let speedlimits = self.speedlimit_plane_data(&owntrack, dmin, dmax, origin_angle);
        let curve_sections = self.curve_sections_plane_data(&owntrack, dmin, dmax);
        let transition_sections = self.transition_sections_plane_data(&owntrack, dmin, dmax);

        PlaneData {
            owntrack,
            othertracks,
            stations: station_labels,
            speedlimits,
            curve_sections,
            transition_sections,
            bounds,
        }
    }

    pub fn profile_data(
        &self,
        distmin: Option<f64>,
        distmax: Option<f64>,
        othertrack_list: &[String],
        ylim: Option<(f64, f64)>,
    ) -> ProfileData {
        let dmin = distmin.unwrap_or(self.distrange_vertical.0);
        let dmax = distmax.unwrap_or(self.distrange_vertical.1);

        let mut owntrack = distance_filter(&self.environment.owntrack_pos, dmin, dmax);
        let curve = distance_filter_2col(&self.environment.owntrack_curve, dmin, dmax);

        if owntrack.is_empty() {
            return ProfileData::empty();
        }

        // Apply height offset
        for row in &mut owntrack {
            row[3] -= self.height_origin;
        }

        // Other tracks
        let mut othertracks = Vec::new();
        for key in othertrack_list {
            let tk = if key == "\\" { "" } else { key };
            if let Some(ot_data) = self.environment.othertrack_pos.get(tk) {
                let filtered = distance_filter_generic(
                    ot_data,
                    self.environment
                        .othertrack
                        .cp_range
                        .get(tk)
                        .map(|r| r.min.max(dmin))
                        .unwrap_or(dmin),
                    self.environment
                        .othertrack
                        .cp_range
                        .get(tk)
                        .map(|r| r.max.min(dmax))
                        .unwrap_or(dmax),
                    |r| r[0],
                );
                if !filtered.is_empty() {
                    let mut pts = filtered;
                    for row in &mut pts {
                        row[3] -= self.height_origin;
                    }
                    let color = self
                        .environment
                        .othertrack_linecolor
                        .get(tk)
                        .map(|c| c.current.clone())
                        .unwrap_or_else(|| "#ffffff".to_string());
                    othertracks.push(OtherTrackProfileData {
                        key: tk.to_string(),
                        points: pts,
                        color,
                    });
                }
            }
        }

        // Y limits
        let (ymin, ymax) = if let Some((l, u)) = ylim {
            (l, u)
        } else {
            let hmin = owntrack.iter().map(|r| r[3]).fold(f64::INFINITY, f64::min);
            let hmax = owntrack
                .iter()
                .map(|r| r[3])
                .fold(f64::NEG_INFINITY, f64::max);
            if (hmax - hmin).abs() > 1e-9 {
                (hmin - (hmax - hmin) * 0.2, hmax + (hmax - hmin) * 0.1)
            } else {
                (hmin - 5.0, hmax + 5.0)
            }
        };

        let curve_points: Vec<[f64; 2]> = curve
            .iter()
            .map(|r| [r[0], if r[1] >= 0.0 { 1.0 } else { -1.0 }])
            .collect();

        let mut station_pts = self.station_points(dmin, dmax);
        for row in &mut station_pts {
            row[3] -= self.height_origin;
        }
        let station_labels = self.station_labels(&station_pts);

        let gradient_labels = self.gradient_labels(dmin, dmax, ymin);
        let gradient_points = self.gradient_change_points(&owntrack, dmin, dmax, ymin);
        let radius_labels = self.radius_labels(dmin, dmax, 0.0, 1.0);

        ProfileData {
            owntrack,
            curve: curve_points,
            othertracks,
            stations: station_labels,
            gradient_labels,
            gradient_points,
            radius_labels,
            station_top: ymax,
            bounds: (dmin, ymin, dmax, ymax),
            radius_bounds: (dmin, -2.2, dmax, 2.2),
        }
    }

    fn station_points(&self, dmin: f64, dmax: f64) -> Vec<[f64; 11]> {
        if self.no_station {
            return Vec::new();
        }
        self.station_pos
            .iter()
            .filter(|r| r[0] >= dmin && r[0] <= dmax)
            .copied()
            .collect()
    }

    fn station_labels(&self, pos: &[[f64; 11]]) -> Vec<StationLabel> {
        pos.iter()
            .map(|row| {
                let key = &self.environment.station.position[&StationDist(row[0])];
                let raw_name = self
                    .environment
                    .station
                    .stationkey
                    .get(key)
                    .cloned()
                    .unwrap_or_else(|| key.clone());
                let name = raw_name
                    .split(',')
                    .nth(1)
                    .map(|s| s.trim())
                    .filter(|s| !s.is_empty())
                    .unwrap_or_else(|| raw_name.split(',').next().unwrap_or(&raw_name).trim())
                    .to_string();
                StationLabel {
                    distance: row[0],
                    mileage: row[0] - self.distance_origin,
                    name,
                    point: *row,
                }
            })
            .collect()
    }

    fn gradient_change_points(
        &self,
        owntrack: &[[f64; 11]],
        dmin: f64,
        dmax: f64,
        target_y: f64,
    ) -> Vec<GradientPoint> {
        let mut points = Vec::new();
        let gradient_dists: Vec<f64> = self
            .environment
            .own_track
            .data
            .iter()
            .filter(|e| e.key == "gradient")
            .map(|e| e.distance)
            .collect();
        let mut unique_dists: Vec<f64> = gradient_dists;
        unique_dists.sort_by(|a, b| a.partial_cmp(b).unwrap());
        unique_dists.dedup();

        for d in unique_dists {
            if d >= dmin && d <= dmax {
                let z = linear_interpolate(d, owntrack);
                points.push(GradientPoint { x: d, z, target_y });
            }
        }
        points
    }

    fn gradient_labels(&self, dmin: f64, dmax: f64, ypos: f64) -> Vec<GradientLabel> {
        let mut labels = Vec::new();
        let owntrack = distance_filter(&self.environment.owntrack_pos, dmin, dmax);
        if owntrack.is_empty() {
            return labels;
        }

        let mut pointer = TrackPointer::new(&self.environment.own_track.data, "gradient");

        // Skip to visible range
        while pointer.next.is_some() {
            let n = pointer.next.unwrap();
            if self.environment.own_track.data[n].distance < dmin {
                pointer.seek_next(&self.environment.own_track.data);
            } else {
                break;
            }
        }

        while pointer.next.is_some() {
            let n = pointer.next.unwrap();
            if self.environment.own_track.data[n].distance > dmax {
                break;
            }

            let next_elem = &self.environment.own_track.data[n];

            if pointer.last.is_none() {
                let start = owntrack.first().map(|r| r[0]).unwrap_or(0.0);
                let end = next_elem.distance;
                let mid = (start + end) / 2.0;
                if mid > dmin && mid < dmax {
                    labels.push(GradientLabel {
                        x: mid,
                        y: ypos,
                        text: "Lv.".to_string(),
                    });
                }
            } else {
                let last_idx = pointer.last.unwrap();
                let last_elem = &self.environment.own_track.data[last_idx];
                if next_elem.flag == "bt" {
                    let mid = (last_elem.distance + next_elem.distance) / 2.0;
                    if mid > dmin && mid < dmax {
                        let val = pointer
                            .seek_origin_of_continuous(&self.environment.own_track.data, last_idx)
                            .map(|i| self.environment.own_track.data[i].value.as_value().abs())
                            .unwrap_or(0.0);
                        let text = if val != 0.0 {
                            format!("{:.1}", val)
                        } else {
                            "Lv.".to_string()
                        };
                        labels.push(GradientLabel {
                            x: mid,
                            y: ypos,
                            text,
                        });
                    }
                } else if next_elem.flag == "i" {
                    let last_val = pointer
                        .seek_origin_of_continuous(&self.environment.own_track.data, last_idx)
                        .map(|i| self.environment.own_track.data[i].value.as_value())
                        .unwrap_or(0.0);
                    let next_val = pointer
                        .seek_origin_of_continuous(&self.environment.own_track.data, n)
                        .map(|i| self.environment.own_track.data[i].value.as_value())
                        .unwrap_or(0.0);
                    if (last_val - next_val).abs() < 1e-12 {
                        let mid = (last_elem.distance + next_elem.distance) / 2.0;
                        if mid > dmin && mid < dmax {
                            labels.push(GradientLabel {
                                x: mid,
                                y: ypos,
                                text: format!("{:.1}", last_val.abs()),
                            });
                        }
                    }
                } else if next_elem.flag.is_empty() && last_elem.flag != "bt" {
                    let mid = (last_elem.distance + next_elem.distance) / 2.0;
                    if mid > dmin && mid < dmax {
                        let val = pointer
                            .seek_origin_of_continuous(&self.environment.own_track.data, last_idx)
                            .map(|i| self.environment.own_track.data[i].value.as_value().abs())
                            .unwrap_or(0.0);
                        let text = if val != 0.0 {
                            format!("{:.1}", val)
                        } else {
                            "Lv.".to_string()
                        };
                        labels.push(GradientLabel {
                            x: mid,
                            y: ypos,
                            text,
                        });
                    }
                }
            }

            pointer.seek_next(&self.environment.own_track.data);
        }

        // Final segment
        if pointer.last.is_some() && pointer.next.is_none() {
            let end = owntrack.last().map(|r| r[0]).unwrap_or(0.0);
            if (end - dmin).abs() > 1e-9 {
                let start = self.environment.own_track.data[pointer.last.unwrap()].distance;
                let mid = (start + end) / 2.0;
                if mid > dmin && mid < dmax {
                    let val = self.environment.own_track.data[pointer.last.unwrap()]
                        .value
                        .as_value()
                        .abs();
                    let text = if val != 0.0 {
                        format!("{:.1}", val)
                    } else {
                        "Lv.".to_string()
                    };
                    labels.push(GradientLabel {
                        x: mid,
                        y: ypos,
                        text,
                    });
                }
            }
        }

        labels
    }

    fn radius_labels(&self, dmin: f64, dmax: f64, ypos: f64, yscale: f64) -> Vec<RadiusLabel> {
        let mut labels = Vec::new();
        let mut pointer = TrackPointer::new(&self.environment.own_track.data, "radius");

        while pointer.next.is_some() {
            let n = pointer.next.unwrap();
            if self.environment.own_track.data[n].distance < dmin {
                pointer.seek_next(&self.environment.own_track.data);
            } else {
                break;
            }
        }

        while pointer.next.is_some() {
            let n = pointer.next.unwrap();
            if self.environment.own_track.data[n].distance > dmax {
                break;
            }
            if let Some(last_idx) = pointer.last {
                let last_elem = &self.environment.own_track.data[last_idx];
                let next_elem = &self.environment.own_track.data[n];

                if next_elem.flag == "bt" {
                    let val = pointer
                        .seek_origin_of_continuous(&self.environment.own_track.data, last_idx)
                        .map(|i| self.environment.own_track.data[i].value.as_value())
                        .unwrap_or(0.0);
                    if val != 0.0 {
                        let mid = (last_elem.distance + next_elem.distance) / 2.0;
                        if mid > dmin && mid < dmax {
                            labels.push(RadiusLabel {
                                x: mid,
                                y: ypos + val.signum() * yscale * 1.5,
                                text: format!("{:.0}", val.abs()),
                            });
                        }
                    }
                } else if next_elem.flag == "i" {
                    let last_val = pointer
                        .seek_origin_of_continuous(&self.environment.own_track.data, last_idx)
                        .map(|i| self.environment.own_track.data[i].value.as_value())
                        .unwrap_or(0.0);
                    let next_val = pointer
                        .seek_origin_of_continuous(&self.environment.own_track.data, n)
                        .map(|i| self.environment.own_track.data[i].value.as_value())
                        .unwrap_or(0.0);
                    if (last_val - next_val).abs() < 1e-12 && last_val != 0.0 {
                        let mid = (last_elem.distance + next_elem.distance) / 2.0;
                        if mid > dmin && mid < dmax {
                            labels.push(RadiusLabel {
                                x: mid,
                                y: ypos + last_val.signum() * yscale * 1.5,
                                text: format!("{:.0}", last_val.abs()),
                            });
                        }
                    }
                } else if next_elem.flag.is_empty() && last_elem.flag != "bt" {
                    let val = pointer
                        .seek_origin_of_continuous(&self.environment.own_track.data, last_idx)
                        .map(|i| self.environment.own_track.data[i].value.as_value())
                        .unwrap_or(0.0);
                    if val != 0.0 {
                        let mid = (last_elem.distance + next_elem.distance) / 2.0;
                        if mid > dmin && mid < dmax {
                            labels.push(RadiusLabel {
                                x: mid,
                                y: ypos + val.signum() * yscale * 1.5,
                                text: format!("{:.0}", val.abs()),
                            });
                        }
                    }
                }
            }
            pointer.seek_next(&self.environment.own_track.data);
        }

        labels
    }

    fn speedlimit_plane_data(
        &self,
        owntrack: &[[f64; 11]],
        dmin: f64,
        dmax: f64,
        origin_angle: f64,
    ) -> Vec<SpeedLimitDisplay> {
        let mut result = Vec::new();
        for entry in &self.environment.speedlimit.data {
            let d = entry.distance;
            if d < dmin || d > dmax {
                continue;
            }
            let idx = owntrack
                .partition_point(|r| r[0] < d)
                .min(owntrack.len() - 1);
            let pos = owntrack[idx];
            result.push(SpeedLimitDisplay {
                distance: d,
                x: pos[1],
                y: pos[2],
                theta: pos[4] - origin_angle,
                speed: entry.speed,
            });
        }
        result
    }

    fn curve_sections_plane_data(
        &self,
        _owntrack: &[[f64; 11]],
        dmin: f64,
        dmax: f64,
    ) -> Vec<CurveSection> {
        let mut sections = Vec::new();
        let radius_entries: Vec<&TrackElement> = self
            .environment
            .own_track
            .data
            .iter()
            .filter(|e| e.key == "radius")
            .collect();

        let mut i = 0;
        while i < radius_entries.len() {
            let entry = radius_entries[i];
            if entry.flag.is_empty() && !entry.value.is_continue() && entry.value.as_value() != 0.0
            {
                let start_d = entry.distance.max(dmin);
                let radius_val = entry.value.as_value();
                i += 1;
                let end_d = loop {
                    if i >= radius_entries.len() {
                        break dmax;
                    }
                    let next = radius_entries[i];
                    if next.flag.is_empty() {
                        break next.distance.min(dmax);
                    }
                    i += 1;
                };
                if end_d > start_d {
                    sections.push(CurveSection {
                        start: start_d,
                        end: end_d,
                        radius: radius_val,
                    });
                }
            } else {
                i += 1;
            }
        }
        sections
    }

    fn transition_sections_plane_data(
        &self,
        _owntrack: &[[f64; 11]],
        dmin: f64,
        dmax: f64,
    ) -> Vec<TransitionSection> {
        let mut sections = Vec::new();
        let radius_entries: Vec<&TrackElement> = self
            .environment
            .own_track
            .data
            .iter()
            .filter(|e| e.key == "radius")
            .collect();

        let mut i = 0;
        while i < radius_entries.len() {
            let entry = radius_entries[i];
            if entry.flag == "bt" {
                let start_d = entry.distance.max(dmin);
                i += 1;
                let end_d = loop {
                    if i >= radius_entries.len() {
                        break dmax;
                    }
                    let next = radius_entries[i];
                    if next.flag.is_empty() {
                        break next.distance.min(dmax);
                    }
                    i += 1;
                };
                if end_d > start_d {
                    sections.push(TransitionSection {
                        start: start_d,
                        end: end_d,
                    });
                }
            } else {
                i += 1;
            }
        }
        sections
    }

    fn compute_bounds(
        owntrack: &[[f64; 11]],
        othertracks: &[OtherTrackData],
    ) -> (f64, f64, f64, f64) {
        let mut xmin = owntrack.iter().map(|r| r[1]).fold(f64::INFINITY, f64::min);
        let mut xmax = owntrack
            .iter()
            .map(|r| r[1])
            .fold(f64::NEG_INFINITY, f64::max);
        let mut ymin = owntrack.iter().map(|r| r[2]).fold(f64::INFINITY, f64::min);
        let mut ymax = owntrack
            .iter()
            .map(|r| r[2])
            .fold(f64::NEG_INFINITY, f64::max);

        for ot in othertracks {
            if ot.points.is_empty() {
                continue;
            }
            xmin = xmin.min(ot.points.iter().map(|r| r[0]).fold(f64::INFINITY, f64::min));
            xmax = xmax.max(
                ot.points
                    .iter()
                    .map(|r| r[0])
                    .fold(f64::NEG_INFINITY, f64::max),
            );
            ymin = ymin.min(ot.points.iter().map(|r| r[1]).fold(f64::INFINITY, f64::min));
            ymax = ymax.max(
                ot.points
                    .iter()
                    .map(|r| r[1])
                    .fold(f64::NEG_INFINITY, f64::max),
            );
        }

        if xmin.is_infinite() {
            return (-1.0, -1.0, 1.0, 1.0);
        }

        let pad = (xmax - xmin).max(ymax - ymin).max(1.0) * 0.05;
        (xmin - pad, ymin - pad, xmax + pad, ymax + pad)
    }

    pub fn get_track_info_at(&self, distance: f64) -> Option<TrackInfo> {
        let own = &self.environment.owntrack_pos;
        if own.is_empty() {
            return None;
        }
        let first_dist = own.first().map(|r| r[0]).unwrap_or(0.0);
        let last_dist = own.last().map(|r| r[0]).unwrap_or(0.0);
        if distance < first_dist || distance > last_dist {
            return None;
        }
        let idx = own.partition_point(|r| r[0] < distance).min(own.len() - 1);
        let pos = own[idx];
        let mileage = distance - self.distance_origin;
        let elevation = pos[3] - self.height_origin;
        let gradient = pos[6];
        let radius = pos[5];

        let mut speed = None;
        for entry in &self.environment.speedlimit.data {
            if entry.distance > distance {
                break;
            }
            speed = entry.speed;
        }

        Some(TrackInfo {
            distance,
            mileage,
            elevation,
            gradient,
            radius,
            speed,
        })
    }
}

#[derive(Debug, Clone)]
pub struct PlaneData {
    pub owntrack: Vec<[f64; 11]>,
    pub othertracks: Vec<OtherTrackData>,
    pub stations: Vec<StationLabel>,
    pub speedlimits: Vec<SpeedLimitDisplay>,
    pub curve_sections: Vec<CurveSection>,
    pub transition_sections: Vec<TransitionSection>,
    pub bounds: (f64, f64, f64, f64),
}

impl PlaneData {
    fn empty() -> Self {
        PlaneData {
            owntrack: Vec::new(),
            othertracks: Vec::new(),
            stations: Vec::new(),
            speedlimits: Vec::new(),
            curve_sections: Vec::new(),
            transition_sections: Vec::new(),
            bounds: (-1.0, -1.0, 1.0, 1.0),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ProfileData {
    pub owntrack: Vec<[f64; 11]>,
    pub curve: Vec<[f64; 2]>,
    pub othertracks: Vec<OtherTrackProfileData>,
    pub stations: Vec<StationLabel>,
    pub gradient_labels: Vec<GradientLabel>,
    pub gradient_points: Vec<GradientPoint>,
    pub radius_labels: Vec<RadiusLabel>,
    pub station_top: f64,
    pub bounds: (f64, f64, f64, f64),
    pub radius_bounds: (f64, f64, f64, f64),
}

impl ProfileData {
    fn empty() -> Self {
        ProfileData {
            owntrack: Vec::new(),
            curve: Vec::new(),
            othertracks: Vec::new(),
            stations: Vec::new(),
            gradient_labels: Vec::new(),
            gradient_points: Vec::new(),
            radius_labels: Vec::new(),
            station_top: 1.0,
            bounds: (-1.0, -1.0, 1.0, 1.0),
            radius_bounds: (-1.0, -2.2, 1.0, 2.2),
        }
    }
}

#[derive(Debug, Clone)]
pub struct OtherTrackData {
    pub key: String,
    pub points: Vec<[f64; 2]>,
    pub color: String,
}

#[derive(Debug, Clone)]
pub struct OtherTrackProfileData {
    pub key: String,
    pub points: Vec<[f64; 8]>,
    pub color: String,
}

#[derive(Debug, Clone)]
pub struct StationLabel {
    pub distance: f64,
    pub mileage: f64,
    pub name: String,
    pub point: [f64; 11],
}

#[derive(Debug, Clone)]
pub struct SpeedLimitDisplay {
    pub distance: f64,
    pub x: f64,
    pub y: f64,
    pub theta: f64,
    pub speed: Option<f64>,
}

#[derive(Debug, Clone)]
pub struct CurveSection {
    pub start: f64,
    pub end: f64,
    pub radius: f64,
}

#[derive(Debug, Clone)]
pub struct TransitionSection {
    pub start: f64,
    pub end: f64,
}

#[derive(Debug, Clone)]
pub struct GradientLabel {
    pub x: f64,
    pub y: f64,
    pub text: String,
}

#[derive(Debug, Clone)]
pub struct GradientPoint {
    pub x: f64,
    pub z: f64,
    pub target_y: f64,
}

#[derive(Debug, Clone)]
pub struct RadiusLabel {
    pub x: f64,
    pub y: f64,
    pub text: String,
}

#[derive(Debug, Clone)]
pub struct TrackInfo {
    pub distance: f64,
    pub mileage: f64,
    pub elevation: f64,
    pub gradient: f64,
    pub radius: f64,
    pub speed: Option<f64>,
}

fn distance_filter(data: &[[f64; 11]], distmin: f64, distmax: f64) -> Vec<[f64; 11]> {
    data.iter()
        .filter(|r| r[0] >= distmin && r[0] <= distmax)
        .copied()
        .collect()
}

fn distance_filter_generic<T: Copy>(
    data: &[T],
    distmin: f64,
    distmax: f64,
    get_dist: impl Fn(&T) -> f64,
) -> Vec<T> {
    data.iter()
        .filter(|r| get_dist(r) >= distmin && get_dist(r) <= distmax)
        .copied()
        .collect()
}

fn distance_filter_2col(data: &[[f64; 2]], distmin: f64, distmax: f64) -> Vec<[f64; 2]> {
    data.iter()
        .filter(|r| r[0] >= distmin && r[0] <= distmax)
        .copied()
        .collect()
}

fn rotate_track(track: &[[f64; 11]], angle: f64) -> Vec<[f64; 11]> {
    let c = angle.cos();
    let s = angle.sin();
    track
        .iter()
        .map(|row| {
            let x = row[1];
            let y = row[2];
            let mut new_row = *row;
            new_row[1] = c * x - s * y;
            new_row[2] = s * x + c * y;
            new_row
        })
        .collect()
}

fn rotate_track_columns(
    track: &[[f64; 11]],
    angle: f64,
    col_x: usize,
    col_y: usize,
) -> Vec<[f64; 11]> {
    let c = angle.cos();
    let s = angle.sin();
    track
        .iter()
        .map(|row| {
            let x = row[col_x];
            let y = row[col_y];
            let mut new_row = *row;
            new_row[col_x] = c * x - s * y;
            new_row[col_y] = s * x + c * y;
            new_row
        })
        .collect()
}

fn rotate_track_columns_ot(
    track: &[[f64; 8]],
    angle: f64,
    col_x: usize,
    col_y: usize,
) -> Vec<[f64; 2]> {
    let c = angle.cos();
    let s = angle.sin();
    track
        .iter()
        .map(|row| {
            let x = row[col_x];
            let y = row[col_y];
            [c * x - s * y, s * x + c * y]
        })
        .collect()
}

fn linear_interpolate(x: f64, data: &[[f64; 11]]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    let idx = data.partition_point(|r| r[0] < x);
    if idx == 0 {
        return data[0][3];
    }
    if idx >= data.len() {
        return data[data.len() - 1][3];
    }
    let a = data[idx - 1];
    let b = data[idx];
    let t = (x - a[0]) / (b[0] - a[0]);
    a[3] + t * (b[3] - a[3])
}
