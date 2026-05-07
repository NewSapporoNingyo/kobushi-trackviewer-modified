use crate::environment::*;
use crate::track_coordinate;
use crate::track_pointer::TrackPointer;

#[derive(Debug, Copy, Clone, Default)]
struct LastPos {
    x: f64,
    y: f64,
    z: f64,
    theta: f64,
    radius: f64,
    gradient: f64,
    distance: f64,
    interpolate_func: f64, // 0 = sin, 1 = line
    cant: f64,
    center: f64,
    gauge: f64,
}

#[derive(Debug, Copy, Clone, Default)]
struct RadiusLastPos {
    distance: f64,
    theta: f64,
    radius: f64,
}

pub struct TrackGenerator {
    env: Environment,
    list_cp: Vec<f64>,
    cp_min: f64,
    cp_max: f64,
    last_pos: LastPos,
    radius_lastpos: RadiusLastPos,
}

impl TrackGenerator {
    pub fn new(env: &Environment, unitdist_default: Option<f64>) -> Self {
        let mut list_cp = env.controlpoints.list_cp.clone();
        if list_cp.is_empty() {
            list_cp.push(0.0);
        }
        let equaldist_unit = unitdist_default.unwrap_or(25.0);
        let boundary_margin = 500.0;

        let cp_min = list_cp.iter().cloned().fold(f64::INFINITY, f64::min);
        let cp_max = list_cp.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

        if let Some((arb_min, arb_max, arb_step)) = env.cp_arbdistribution {
            add_equal_cp(&mut list_cp, arb_min, arb_max, arb_step);
        } else if !env.station.position.is_empty() {
            let s_min = env
                .station
                .position
                .keys()
                .fold(f64::INFINITY, |a, b| a.min(b.0));
            let s_max = env
                .station
                .position
                .keys()
                .fold(f64::NEG_INFINITY, |a, b| a.max(b.0));
            let smin_r = (s_min / 100.0).floor() * 100.0 - boundary_margin;
            let smax_r = (s_max / 100.0).ceil() * 100.0 + boundary_margin;
            add_equal_cp(&mut list_cp, smin_r.max(0.0), smax_r, equaldist_unit);
        } else {
            let cmin_r = (cp_min / 100.0).floor() * 100.0 - boundary_margin;
            let cmax_r = (cp_max / 100.0).ceil() * 100.0 + boundary_margin;
            add_equal_cp(&mut list_cp, cmin_r.max(0.0), cmax_r, equaldist_unit);
        }

        list_cp.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        list_cp.dedup();

        let cp_min_val = list_cp.iter().cloned().fold(f64::INFINITY, f64::min);
        let cp_max_val = list_cp.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

        TrackGenerator {
            env: env.clone(),
            list_cp,
            cp_min: cp_min_val,
            cp_max: cp_max_val,
            last_pos: LastPos {
                distance: cp_min_val,
                interpolate_func: 1.0, // line
                ..Default::default()
            },
            radius_lastpos: RadiusLastPos {
                distance: cp_min_val,
                ..Default::default()
            },
        }
    }

    pub fn generate_owntrack(&mut self) -> Vec<[f64; 11]> {
        let data = self.env.own_track.data.clone();
        let mut radius_p = TrackPointer::new(&data, "radius");
        let mut gradient_p = TrackPointer::new(&data, "gradient");
        let mut turn_p = TrackPointer::new(&data, "turn");
        let mut interpolate_p = TrackPointer::new(&data, "interpolate_func");
        let mut cant_p = TrackPointer::new(&data, "cant");
        let mut center_p = TrackPointer::new(&data, "center");
        let mut gauge_p = TrackPointer::new(&data, "gauge");

        let mut cant_lastpos = CantLastPos::default();
        cant_lastpos.distance = 0.0;
        cant_lastpos.value = self.last_pos.cant;

        let n = self.list_cp.len();
        let mut result = vec![[0.0f64; 11]; n];

        let list_cp = self.list_cp.clone();
        for (i, dist) in list_cp.into_iter().enumerate() {
            // setfunction
            while interpolate_p.on_next_point(&data, dist) {
                if let Some(n) = interpolate_p.next {
                    if !data[n].value.is_continue() {
                        self.last_pos.interpolate_func = data[n].value.as_value();
                    }
                }
                interpolate_p.seek_next(&data);
            }

            // setcenter
            let mut center_tmp = self.last_pos.center;
            while center_p.on_next_point(&data, dist) {
                if let Some(n) = center_p.next {
                    if !data[n].value.is_continue() {
                        center_tmp = data[n].value.as_value();
                    }
                }
                center_p.seek_next(&data);
            }

            // setgauge
            let mut gauge_tmp = self.last_pos.gauge;
            while gauge_p.on_next_point(&data, dist) {
                if let Some(n) = gauge_p.next {
                    if !data[n].value.is_continue() {
                        gauge_tmp = data[n].value.as_value();
                    }
                }
                gauge_p.seek_next(&data);
            }

            // turn
            let mut tau_add = 0.0f64;
            if turn_p.next.is_some() {
                if turn_p.on_next_point(&data, dist) {
                    if let Some(n) = turn_p.next {
                        tau_add = data[n].value.as_value().atan();
                    }
                    turn_p.seek_next(&data);
                }
            }

            // radius
            let (x, y, tau_curve, radius_out) = self.process_radius(&data, &mut radius_p, dist);

            // gradient
            let (z, gradient) = self.process_gradient(&data, &mut gradient_p, dist);

            // cant
            let cant_val = self.process_cant(&data, &mut cant_p, &mut cant_lastpos, dist);

            let total_tau = tau_curve + tau_add;

            self.last_pos.x += x;
            self.last_pos.y += y;
            self.last_pos.z += z;
            self.last_pos.theta += total_tau;
            self.last_pos.radius = radius_out;
            self.last_pos.gradient = gradient;
            self.last_pos.distance = dist;
            self.last_pos.cant = cant_val;
            self.last_pos.center = center_tmp;
            self.last_pos.gauge = gauge_tmp;

            result[i] = [
                dist,
                self.last_pos.x,
                self.last_pos.y,
                self.last_pos.z,
                self.last_pos.theta,
                self.last_pos.radius,
                self.last_pos.gradient,
                self.last_pos.interpolate_func,
                self.last_pos.cant,
                self.last_pos.center,
                self.last_pos.gauge,
            ];
        }

        result
    }

    fn process_radius(
        &mut self,
        data: &[TrackElement],
        radius_p: &mut TrackPointer,
        dist: f64,
    ) -> (f64, f64, f64, f64) {
        while radius_p.over_next_point(data, dist) {
            if let Some(n) = radius_p.next {
                if let Some(origin) = radius_p.seek_origin_of_continuous(data, n) {
                    self.last_pos.radius = data[origin].value.as_value();
                    self.radius_lastpos.radius = data[origin].value.as_value();
                    self.radius_lastpos.distance = data[origin].distance;
                    self.radius_lastpos.theta = self.last_pos.theta;
                }
            }
            radius_p.seek_next(data);
        }

        if radius_p.last.is_none() {
            if radius_p.next.is_none() {
                if self.last_pos.radius == 0.0 {
                    let (x, y) = track_coordinate::curve_straight(
                        dist - self.last_pos.distance,
                        self.last_pos.theta,
                    );
                    (x, y, 0.0, self.last_pos.radius)
                } else {
                    let ((x, y), tau) = track_coordinate::circular_curve(
                        dist - self.last_pos.distance,
                        self.last_pos.radius,
                        self.last_pos.theta,
                    );
                    (x, y, tau, self.last_pos.radius)
                }
            } else {
                if self.last_pos.radius == 0.0 {
                    let (x, y) = track_coordinate::curve_straight(
                        dist - self.last_pos.distance,
                        self.last_pos.theta,
                    );
                    (x, y, 0.0, self.last_pos.radius)
                } else {
                    let ((x, y), tau) = track_coordinate::circular_curve(
                        dist - self.last_pos.distance,
                        self.last_pos.radius,
                        self.last_pos.theta,
                    );
                    (x, y, tau, self.last_pos.radius)
                }
            }
        } else if radius_p.next.is_none() {
            if self.last_pos.radius == 0.0 {
                let (x, y) = track_coordinate::curve_straight(
                    dist - self.last_pos.distance,
                    self.last_pos.theta,
                );
                (x, y, 0.0, self.last_pos.radius)
            } else {
                let ((x, y), tau) = track_coordinate::circular_curve(
                    dist - self.last_pos.distance,
                    self.last_pos.radius,
                    self.last_pos.theta,
                );
                (x, y, tau, self.last_pos.radius)
            }
        } else {
            let next_idx = radius_p.next.unwrap();
            let last_idx = radius_p.last.unwrap();
            let next_elem = &data[next_idx];
            let last_elem = &data[last_idx];

            if next_elem.value.is_continue() {
                if self.last_pos.radius == 0.0 {
                    let (x, y) = track_coordinate::curve_straight(
                        dist - self.last_pos.distance,
                        self.last_pos.theta,
                    );
                    (x, y, 0.0, self.last_pos.radius)
                } else {
                    let ((x, y), tau) = track_coordinate::circular_curve(
                        dist - self.last_pos.distance,
                        self.last_pos.radius,
                        self.last_pos.theta,
                    );
                    (x, y, tau, self.last_pos.radius)
                }
            } else if next_elem.flag == "i" || last_elem.flag == "bt" {
                let next_val = next_elem.value.as_value();
                if (self.radius_lastpos.radius - next_val).abs() > 1e-12 {
                    let segment_l = next_elem.distance - last_elem.distance;
                    let func = if self.last_pos.interpolate_func == 0.0 {
                        "sin"
                    } else {
                        "line"
                    };

                    let l_from_last = self.last_pos.distance - last_elem.distance;
                    let ((pos_last_x, pos_last_y), pos_last_tau, _) =
                        track_coordinate::transition_curve(
                            segment_l,
                            self.radius_lastpos.radius,
                            next_val,
                            self.radius_lastpos.theta,
                            func,
                            l_from_last,
                        );

                    let l_from_last_cur = dist - last_elem.distance;
                    let ((x, y), tau, r) = track_coordinate::transition_curve(
                        segment_l,
                        self.radius_lastpos.radius,
                        next_val,
                        self.radius_lastpos.theta,
                        func,
                        l_from_last_cur,
                    );

                    (x - pos_last_x, y - pos_last_y, tau - pos_last_tau, r)
                } else if next_val != 0.0 {
                    let ((x, y), tau) = track_coordinate::circular_curve(
                        dist - self.last_pos.distance,
                        self.last_pos.radius,
                        self.last_pos.theta,
                    );
                    (x, y, tau, self.last_pos.radius)
                } else {
                    let (x, y) = track_coordinate::curve_straight(
                        dist - self.last_pos.distance,
                        self.last_pos.theta,
                    );
                    (x, y, 0.0, self.last_pos.radius)
                }
            } else {
                if self.last_pos.radius == 0.0 {
                    let (x, y) = track_coordinate::curve_straight(
                        dist - self.last_pos.distance,
                        self.last_pos.theta,
                    );
                    (x, y, 0.0, self.last_pos.radius)
                } else {
                    let ((x, y), tau) = track_coordinate::circular_curve(
                        dist - self.last_pos.distance,
                        self.last_pos.radius,
                        self.last_pos.theta,
                    );
                    (x, y, tau, self.last_pos.radius)
                }
            }
        }
    }

    fn process_gradient(
        &mut self,
        data: &[TrackElement],
        gradient_p: &mut TrackPointer,
        dist: f64,
    ) -> (f64, f64) {
        while gradient_p.over_next_point(data, dist) {
            if let Some(n) = gradient_p.next {
                if let Some(origin) = gradient_p.seek_origin_of_continuous(data, n) {
                    if !data[origin].value.is_continue() {
                        self.last_pos.gradient = data[origin].value.as_value();
                    }
                }
            }
            gradient_p.seek_next(data);
        }

        if gradient_p.last.is_none() {
            let gradient = self.last_pos.gradient;
            let z = track_coordinate::gradient_straight(dist - self.last_pos.distance, gradient);
            (z, gradient)
        } else if gradient_p.next.is_none() {
            let gradient = self.last_pos.gradient;
            let z = track_coordinate::gradient_straight(dist - self.last_pos.distance, gradient);
            (z, gradient)
        } else {
            let next_idx = gradient_p.next.unwrap();
            let last_idx = gradient_p.last.unwrap();
            let next_elem = &data[next_idx];
            let last_elem = &data[last_idx];

            if next_elem.value.is_continue() {
                let gradient = self.last_pos.gradient;
                let z =
                    track_coordinate::gradient_straight(dist - self.last_pos.distance, gradient);
                (z, gradient)
            } else if next_elem.flag == "i" || last_elem.flag == "bt" {
                let next_val = next_elem.value.as_value();
                if (self.last_pos.gradient - next_val).abs() > 1e-12 {
                    let (z, gr) = track_coordinate::gradient_transition(
                        next_elem.distance - self.last_pos.distance,
                        self.last_pos.gradient,
                        next_val,
                        dist - self.last_pos.distance,
                        0.0,
                    );
                    (z, gr)
                } else {
                    let gradient = self.last_pos.gradient;
                    let z = track_coordinate::gradient_straight(
                        dist - self.last_pos.distance,
                        gradient,
                    );
                    (z, gradient)
                }
            } else {
                let gradient = self.last_pos.gradient;
                let z =
                    track_coordinate::gradient_straight(dist - self.last_pos.distance, gradient);
                (z, gradient)
            }
        }
    }

    fn process_cant(
        &self,
        data: &[TrackElement],
        cant_p: &mut TrackPointer,
        lastpos: &mut CantLastPos,
        dist: f64,
    ) -> f64 {
        while cant_p.over_next_point(data, dist) {
            if let Some(n) = cant_p.next {
                if let Some(origin) = cant_p.seek_origin_of_continuous(data, n) {
                    if !data[origin].value.is_continue() {
                        lastpos.distance = data[origin].distance;
                        lastpos.value = data[origin].value.as_value();
                    }
                }
            }
            cant_p.seek_next(data);
        }

        if cant_p.last.is_none() || cant_p.next.is_none() {
            return lastpos.value;
        }

        let next_idx = cant_p.next.unwrap();
        let last_idx = cant_p.last.unwrap();

        if data[next_idx].value.is_continue() {
            return lastpos.value;
        }

        if data[next_idx].flag == "i" || data[last_idx].flag == "bt" {
            if (lastpos.value - data[next_idx].value.as_value()).abs() > 1e-12 {
                let func = if self.last_pos.interpolate_func == 0.0 {
                    "sin"
                } else {
                    "line"
                };
                track_coordinate::cant_transition(
                    data[next_idx].distance - data[last_idx].distance,
                    lastpos.value,
                    data[next_idx].value.as_value(),
                    func,
                    dist - data[last_idx].distance,
                )
            } else {
                lastpos.value
            }
        } else {
            lastpos.value
        }
    }

    pub fn generate_curveradius_dist(&self) -> Vec<[f64; 2]> {
        let data = &self.env.own_track.data;
        let mut radius_p = TrackPointer::new(data, "radius");
        let mut result = vec![[self.list_cp[0], 0.0]];
        let mut prev_radius = 0.0f64;
        let mut prev_is_bt = false;

        while radius_p.next.is_some() {
            let next_idx = radius_p.next.unwrap();
            let next_radius = &data[next_idx];
            let flag = &next_radius.flag;
            let distance = next_radius.distance;

            if next_radius.value.is_continue() {
                result.push([distance, prev_radius]);
            } else if prev_is_bt {
                result.push([distance, next_radius.value.as_value()]);
            } else if flag == "i" {
                result.push([distance, next_radius.value.as_value()]);
            } else {
                result.push([distance, prev_radius]);
                result.push([distance, next_radius.value.as_value()]);
            }

            prev_radius = next_radius.value.as_value();
            prev_is_bt = flag == "bt";
            radius_p.seek_next(data);
        }

        result.push([self.cp_max, 0.0]);
        result
    }

    pub fn list_cp(&self) -> &[f64] {
        &self.list_cp
    }
}

#[derive(Debug, Copy, Clone, Default)]
struct CantLastPos {
    distance: f64,
    value: f64,
}

fn add_equal_cp(list_cp: &mut Vec<f64>, min_val: f64, max_val: f64, step: f64) {
    if !min_val.is_finite()
        || !max_val.is_finite()
        || !step.is_finite()
        || step <= 0.0
        || max_val < min_val
    {
        return;
    }
    let mut d = min_val;
    while d <= max_val + step * 0.5 {
        list_cp.push(d);
        d += step;
    }
}

// ========== Other Track Generator ==========

pub struct OtherTrackGenerator {
    data: Vec<TrackElement>,
    owntrack_position: Vec<[f64; 11]>,
    dist_range: (f64, f64),
}

impl OtherTrackGenerator {
    pub fn new(env: &Environment, trackkey: &str) -> Option<Self> {
        let tk = if trackkey.is_empty() { "0" } else { trackkey };
        let data = env.othertrack.data.get(tk)?.clone();
        let dist_min = data
            .iter()
            .map(|e| e.distance)
            .fold(f64::INFINITY, f64::min);
        let dist_max = data
            .iter()
            .map(|e| e.distance)
            .fold(f64::NEG_INFINITY, f64::max);

        Some(OtherTrackGenerator {
            data,
            owntrack_position: env.owntrack_pos.clone(),
            dist_range: (dist_min, dist_max),
        })
    }

    pub fn generate(&self) -> Vec<[f64; 8]> {
        let trackkeys = [
            "x.position",
            "x.radius",
            "y.position",
            "y.radius",
            "interpolate_func",
            "cant",
            "center",
            "gauge",
        ];

        let mut pointers: Vec<TrackPointer> = trackkeys
            .iter()
            .map(|k| TrackPointer::new(&self.data, k))
            .collect();
        let mut cant_p = TrackPointer::new(&self.data, "cant");

        let mut pos_last = vec![0.0f64; trackkeys.len()];
        let mut pos_next = vec![0.0f64; trackkeys.len()];

        // Initialize next values
        for (i, p) in pointers.iter().enumerate() {
            if let Some(n) = p.next {
                if !self.data[n].value.is_continue() {
                    pos_next[i] = self.data[n].value.as_value();
                }
                pos_last[i] = pos_next[i];
            }
        }

        let mut result = Vec::new();
        let mut cant_lastpos = CantLastPos::default();

        for element in &self.owntrack_position {
            if self.dist_range.0 > element[0] {
                continue;
            }

            // Advance pointers
            for tpkey_idx in [0usize, 1, 2, 3] {
                while pointers[tpkey_idx].over_next_point(&self.data, element[0]) {
                    pointers[tpkey_idx].seek_next(&self.data);
                    pos_last[tpkey_idx] = pos_next[tpkey_idx];
                    if let Some(n) = pointers[tpkey_idx].next {
                        if self.data[n].value.is_continue() {
                            pos_next[tpkey_idx] = pos_last[tpkey_idx];
                        } else {
                            pos_next[tpkey_idx] = self.data[n].value.as_value();
                        }
                    }
                }
            }

            for tpkey_idx in [4usize, 6, 7] {
                while pointers[tpkey_idx].on_next_point(&self.data, element[0]) {
                    pointers[tpkey_idx].seek_next(&self.data);
                    pos_last[tpkey_idx] = pos_next[tpkey_idx];
                    if let Some(n) = pointers[tpkey_idx].next {
                        if self.data[n].value.is_continue() {
                            pos_next[tpkey_idx] = pos_last[tpkey_idx];
                        } else {
                            pos_next[tpkey_idx] = self.data[n].value.as_value();
                        }
                    }
                }
            }

            // Cant
            while cant_p.over_next_point(&self.data, element[0]) {
                if let Some(n) = cant_p.next {
                    if let Some(origin) = cant_p.seek_origin_of_continuous(&self.data, n) {
                        if !self.data[origin].value.is_continue() {
                            cant_lastpos.distance = self.data[origin].distance;
                            cant_lastpos.value = self.data[origin].value.as_value();
                        }
                    }
                }
                cant_p.seek_next(&self.data);
            }

            // Compute absolute positions
            let x_result = if pointers[0].last.is_some() && pointers[0].next.is_some() {
                let last_idx = pointers[0].last.unwrap();
                let next_idx = pointers[0].next.unwrap();
                let l = self.data[next_idx].distance - self.data[last_idx].distance;
                let l_inter = element[0] - self.data[last_idx].distance;
                track_coordinate::absolute_position_x(
                    l,
                    pos_last[1],
                    pos_last[0],
                    pos_next[0],
                    l_inter,
                    element[1],
                    element[2],
                    element[4],
                )
            } else {
                let theta = element[4];
                let x_pos = pos_last[0];
                (
                    -theta.sin() * x_pos + element[1],
                    theta.cos() * x_pos + element[2],
                )
            };

            let y_result = if pointers[2].last.is_some() && pointers[2].next.is_some() {
                let last_idx = pointers[2].last.unwrap();
                let next_idx = pointers[2].next.unwrap();
                let l = self.data[next_idx].distance - self.data[last_idx].distance;
                let l_inter = element[0] - self.data[last_idx].distance;
                track_coordinate::absolute_position_y(
                    l,
                    pos_last[3],
                    pos_last[2],
                    pos_next[2],
                    l_inter,
                    element[0],
                    element[3],
                )
            } else {
                (element[0], element[3] + pos_last[2])
            };

            let cant_val = if cant_p.last.is_some() && cant_p.next.is_some() {
                let last_idx = cant_p.last.unwrap();
                let next_idx = cant_p.next.unwrap();
                let c1 = cant_lastpos.value;
                let c2 = if self.data[next_idx].value.is_continue() {
                    c1
                } else {
                    self.data[next_idx].value.as_value()
                };
                if (c1 - c2).abs() < 1e-12 {
                    c1
                } else {
                    let func = if pos_last[4] == 0.0 { "sin" } else { "line" };
                    track_coordinate::cant_transition(
                        self.data[next_idx].distance - self.data[last_idx].distance,
                        c1,
                        c2,
                        func,
                        element[0] - self.data[last_idx].distance,
                    )
                }
            } else {
                cant_lastpos.value
            };

            result.push([
                element[0],
                x_result.0,
                x_result.1,
                y_result.1,
                pos_last[4],
                cant_val,
                pos_last[6],
                pos_last[7],
            ]);
        }

        result
    }
}
