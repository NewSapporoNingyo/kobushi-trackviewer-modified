use glam::DVec2;

/// Clothoid (Euler spiral) coordinate computation via series expansion
pub fn clothoid_dist(a: f64, l: f64, elem: char) -> f64 {
    if elem == 'X' {
        l * (1.0 - 1.0 / 40.0 * (l / a).powi(4) + 1.0 / 3456.0 * (l / a).powi(8)
            - 1.0 / 599040.0 * (l / a).powi(12))
    } else {
        l * (1.0 / 6.0 * (l / a).powi(2) - 1.0 / 336.0 * (l / a).powi(6)
            + 1.0 / 42240.0 * (l / a).powi(10)
            - 1.0 / 9676800.0 * (l / a).powi(14))
    }
}

/// 2D rotation matrix
pub fn rotate(tau: f64) -> [f64; 4] {
    let c = tau.cos();
    let s = tau.sin();
    [c, -s, s, c]
}

pub fn rotate_vec(v: DVec2, tau: f64) -> DVec2 {
    let c = tau.cos();
    let s = tau.sin();
    DVec2::new(c * v.x - s * v.y, s * v.x + c * v.y)
}

/// Straight track segment: returns [x, y] at distance l_intermediate
pub fn curve_straight(l_intermediate: f64, theta: f64) -> (f64, f64) {
    let v = rotate_vec(DVec2::new(l_intermediate, 0.0), theta);
    (v.x, v.y)
}

/// Circular curve: returns ((x, y) at l_intermediate, turn)
pub fn circular_curve(l_intermediate: f64, r: f64, theta: f64) -> ((f64, f64), f64) {
    let tau = l_intermediate / r;
    let abs_r = r.abs();
    let res = DVec2::new(
        abs_r * (l_intermediate / abs_r).sin(),
        r * (1.0 - (l_intermediate / abs_r).cos()),
    );
    let rotated = rotate_vec(res, theta);
    ((rotated.x, rotated.y), tau)
}

/// Full segment circular curve: returns array of (x, y) and turn
pub fn circular_curve_full(l: f64, r: f64, theta: f64, n: usize) -> (Vec<(f64, f64)>, f64) {
    let tau = l / r;
    let abs_r = r.abs();
    let mut points = Vec::with_capacity(n);
    for i in 1..=n {
        let d = l * i as f64 / n as f64;
        let res = DVec2::new(abs_r * (d / abs_r).sin(), r * (1.0 - (d / abs_r).cos()));
        let rotated = rotate_vec(res, theta);
        points.push((rotated.x, rotated.y));
    }
    (points, tau)
}

/// Straight segment full: returns array of (x, y)
pub fn curve_straight_full(l: f64, theta: f64) -> (Vec<(f64, f64)>, f64) {
    let v = rotate_vec(DVec2::new(l, 0.0), theta);
    (vec![(v.x, v.y)], 0.0)
}

/// Transition curve (single point evaluation)
pub fn transition_curve(
    l: f64,
    r1: f64,
    r2: f64,
    theta: f64,
    func: &str,
    l_intermediate: f64,
) -> ((f64, f64), f64, f64) {
    let r1_inf = if r1 == 0.0 || r1.abs() > 1e6 {
        f64::INFINITY
    } else {
        r1
    };
    let r2_inf = if r2 == 0.0 || r2.abs() > 1e6 {
        f64::INFINITY
    } else {
        r2
    };

    if func == "line" {
        transition_clothoid(l, r1_inf, r2_inf, theta, l_intermediate)
    } else {
        transition_sin(l, r1_inf, r2_inf, theta, l_intermediate)
    }
}

fn transition_clothoid(
    l: f64,
    r1: f64,
    r2: f64,
    theta: f64,
    l_intermediate: f64,
) -> ((f64, f64), f64, f64) {
    let ir1 = if r1.is_infinite() { 0.0 } else { 1.0 / r1 };
    let ir2 = if r2.is_infinite() { 0.0 } else { 1.0 / r2 };

    let l0 = l * (1.0 - (1.0 / (1.0 - r2 / r1)));

    let a = if r1.is_finite() {
        (l0.abs() * r1.abs()).sqrt()
    } else {
        ((l - l0).abs() * r2.abs()).sqrt()
    };

    let rl = 1.0 / (ir1 + (ir2 - ir1) * l_intermediate / l);
    let rl_out = if rl.abs() < 1e6 { rl } else { 0.0 };

    if ir1 < ir2 {
        let tau1 = (a / r1).powi(2) / 2.0;
        let dist = l_intermediate + a * a / r1;
        let turn = ((l_intermediate - l0).powi(2) - l0.powi(2)) / (2.0 * a * a);
        let x = clothoid_dist(a, dist, 'X');
        let y = clothoid_dist(a, dist, 'Y');
        let start = DVec2::new(
            clothoid_dist(a, a * a / r1, 'X'),
            clothoid_dist(a, a * a / r1, 'Y'),
        );
        let result = DVec2::new(x, y) - start;
        let rotated = rotate_vec(rotate_vec(result, -tau1), theta);
        ((rotated.x, rotated.y), turn, rl_out)
    } else {
        let tau1 = -(a / r1).powi(2) / 2.0;
        let dist = l_intermediate - a * a / r1;
        let turn = -((l_intermediate - l0).powi(2) - l0.powi(2)) / (2.0 * a * a);
        let x = clothoid_dist(a, dist, 'X');
        let y = -clothoid_dist(a, dist, 'Y');
        let start = DVec2::new(
            clothoid_dist(a, -a * a / r1, 'X'),
            -clothoid_dist(a, -a * a / r1, 'Y'),
        );
        let result = DVec2::new(x, y) - start;
        let rotated = rotate_vec(rotate_vec(result, -tau1), theta);
        ((rotated.x, rotated.y), turn, rl_out)
    }
}

fn curvature_sin(x: f64, r1: f64, r2: f64, l: f64) -> f64 {
    (1.0 / r2 - 1.0 / r1) / 2.0
        * ((std::f64::consts::PI / l * x - std::f64::consts::PI / 2.0).sin() + 1.0)
        + 1.0 / r1
}

fn transition_sin(
    l: f64,
    r1: f64,
    r2: f64,
    theta: f64,
    l_intermediate: f64,
) -> ((f64, f64), f64, f64) {
    let (x, y, tau, r_interm) = harfsin_intermediate(l, r1, r2, l_intermediate, 1.0);
    let result = DVec2::new(x, y);
    let rotated = rotate_vec(result, theta);
    ((rotated.x, rotated.y), tau, r_interm)
}

pub fn harfsin_intermediate(
    l: f64,
    r1: f64,
    r2: f64,
    l_intermediate: f64,
    dl: f64,
) -> (f64, f64, f64, f64) {
    if l_intermediate <= 0.0 {
        let r = if r1 == 0.0 { f64::INFINITY } else { r1 };
        return (0.0, 0.0, 0.0, r);
    }

    let ir1 = if r1.is_infinite() { 0.0 } else { 1.0 / r1 };
    let ir2 = if r2.is_infinite() { 0.0 } else { 1.0 / r2 };

    let effective_dl = if l_intermediate / 5.0 <= dl {
        l_intermediate / 5.0
    } else {
        dl
    };

    let n = (l_intermediate / effective_dl) as usize + 2;
    let n = n.max(2);

    let mut x = 0.0;
    let mut y = 0.0;
    let mut tau_acc = 0.0;

    for i in 1..n {
        let x0 = (i - 1) as f64 * l_intermediate / (n - 1) as f64;
        let x1 = i as f64 * l_intermediate / (n - 1) as f64;
        let dx = x1 - x0;

        let k0 = (ir2 - ir1) / 2.0
            * ((std::f64::consts::PI / l * x0 - std::f64::consts::PI / 2.0).sin() + 1.0)
            + ir1;
        let k1 = (ir2 - ir1) / 2.0
            * ((std::f64::consts::PI / l * x1 - std::f64::consts::PI / 2.0).sin() + 1.0)
            + ir1;

        let tau0 = tau_acc;
        let tau1 = tau_acc + (k0 + k1) / 2.0 * dx;

        x += (tau0.cos() + tau1.cos()) / 2.0 * dx;
        y += (tau0.sin() + tau1.sin()) / 2.0 * dx;
        tau_acc = tau1;
    }

    let k_final = curvature_sin(l_intermediate, r1, r2, l);
    let r_interm = if k_final.abs() < 1e-12 {
        f64::INFINITY
    } else {
        1.0 / k_final
    };
    let r_out = if r_interm.abs() < 1e6 { r_interm } else { 0.0 };

    (x, y, tau_acc, r_out)
}

// ========== Gradient math ==========

pub fn gradient_straight(l_intermediate: f64, gr: f64) -> f64 {
    let theta = (gr / 1000.0).atan();
    l_intermediate * theta.sin()
}

pub fn gradient_transition(l: f64, gr1: f64, gr2: f64, l_intermediate: f64, y0: f64) -> (f64, f64) {
    let theta1 = (gr1 / 1000.0).atan();
    let theta2 = (gr2 / 1000.0).atan();
    let z = y0 + l / (theta2 - theta1) * theta1.cos()
        - l / (theta2 - theta1) * ((theta2 - theta1) / l * l_intermediate + theta1).cos();
    let gradient = 1000.0 * ((theta2 - theta1) / l * l_intermediate + theta1).tan();
    (z, gradient)
}

// ========== Cant (superelevation) ==========

pub fn cant_transition(l: f64, c1: f64, c2: f64, func: &str, l_intermediate: f64) -> f64 {
    if func == "sin" {
        (c2 - c1) / 2.0
            * ((std::f64::consts::PI / l * l_intermediate - std::f64::consts::PI / 2.0).sin() + 1.0)
            + c1
    } else {
        (c2 - c1) / l * l_intermediate + c1
    }
}

// ========== Other track positioning ==========

pub fn relative_position(l: f64, radius: f64, ya: f64, yb: f64, l_intermediate: f64) -> f64 {
    if l == 0.0 {
        return yb;
    }
    if radius != 0.0 {
        let dy = yb - ya;
        let sintheta = (l * l + dy * dy).sqrt() / (2.0 * radius);
        if sintheta.abs() <= 1.0 {
            let tau = dy.atan2(l);
            let theta = 2.0 * sintheta.asin();
            let phi_a = theta / 2.0 - tau;
            let x0 = radius * phi_a.sin();
            let y0 = ya + radius * phi_a.cos();
            let sin_val = (l_intermediate - x0) / radius;
            if sin_val.abs() <= 1.0 {
                y0 - radius * sin_val.asin().cos()
            } else {
                dy / l * l_intermediate + ya
            }
        } else {
            dy / l * l_intermediate + ya
        }
    } else {
        (yb - ya) / l * l_intermediate + ya
    }
}

pub fn absolute_position_x(
    l: f64,
    radius: f64,
    xa: f64,
    xb: f64,
    l_intermediate: f64,
    pos_ownt_x: f64,
    pos_ownt_y: f64,
    pos_ownt_theta: f64,
) -> (f64, f64) {
    let y_rel = relative_position(l, radius, xa, xb, l_intermediate);
    let rotated = rotate_vec(DVec2::new(0.0, y_rel), pos_ownt_theta);
    (rotated.x + pos_ownt_x, rotated.y + pos_ownt_y)
}

pub fn absolute_position_y(
    l: f64,
    radius: f64,
    ya: f64,
    yb: f64,
    l_intermediate: f64,
    pos_ownt_dist: f64,
    pos_ownt_z: f64,
) -> (f64, f64) {
    let y_rel = relative_position(l, radius, ya, yb, l_intermediate);
    (pos_ownt_dist, pos_ownt_z + y_rel)
}
