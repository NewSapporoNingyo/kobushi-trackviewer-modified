use crate::environment::*;
use nom::{
    branch::alt,
    bytes::complete::{is_not, tag, take_while1},
    character::complete::char as char_p,
    combinator::{map, opt},
    multi::{many0, many1, separated_list0},
    number::complete::double,
    sequence::{delimited, pair, preceded, terminated},
    IResult,
};

fn skip_ignored(mut input: &str) -> &str {
    loop {
        let trimmed = input.trim_start_matches(|c: char| {
            c.is_whitespace() || c == '\\' || c == '\u{00a0}' || c == '\u{3000}'
        });
        input = trimmed;

        if input.starts_with('#') || input.starts_with("//") {
            let pos = input.find('\n').unwrap_or(input.len());
            input = &input[pos..];
            continue;
        }

        if input.starts_with("/*") {
            let pos = input.find("*/").map(|p| p + 2).unwrap_or(input.len());
            input = &input[pos..];
            continue;
        }

        return input;
    }
}

fn ignored(input: &str) -> IResult<&str, ()> {
    Ok((skip_ignored(input), ()))
}

fn ws<'a, F: 'a, O>(inner: F) -> impl FnMut(&'a str) -> IResult<&'a str, O>
where
    F: FnMut(&'a str) -> IResult<&'a str, O>,
{
    delimited(ignored, inner, ignored)
}

fn identifier(input: &str) -> IResult<&str, &str> {
    take_while1(|c: char| c.is_alphanumeric() || c == '_' || (c as u32) >= 0x80)(input)
}

fn string_literal(input: &str) -> IResult<&str, &str> {
    map(
        delimited(char_p('\''), opt(is_not("'")), char_p('\'')),
        |s: Option<&str>| s.unwrap_or(""),
    )(input)
}

fn factor(input: &str) -> IResult<&str, Expression> {
    alt((
        map(double, Expression::Number),
        map(string_literal, |s: &str| Expression::String(s.to_string())),
        map(preceded(tag("$"), identifier), |n: &str| {
            Expression::Variable(n.to_string())
        }),
        map(preceded(char_p('-'), factor), |e| {
            Expression::Neg(Box::new(e))
        }),
        map(preceded(char_p('+'), factor), |e| e),
        map(delimited(char_p('('), expression, char_p(')')), |e| e),
        map(identifier, |n: &str| Expression::Label(n.to_string())),
    ))(input)
}

fn function_call(input: &str) -> IResult<&str, Expression> {
    let (input, name) = ws(identifier)(input)?;
    let (input, _) = ws(char_p('('))(input)?;
    let (input, args) = separated_list0(ws(char_p(',')), expression)(input)?;
    let (input, _) = ws(char_p(')'))(input)?;
    Ok((input, Expression::FunctionCall(name.to_string(), args)))
}

fn factor_with_func(input: &str) -> IResult<&str, Expression> {
    alt((function_call, factor))(input)
}

fn term(input: &str) -> IResult<&str, Expression> {
    let (input, init) = factor_with_func(input)?;
    let (input, ops) = many0(pair(
        ws(alt((char_p('*'), char_p('/'), char_p('%')))),
        factor_with_func,
    ))(input)?;
    let result = ops.into_iter().fold(init, |acc, (op, val)| match op {
        '*' => Expression::Mul(Box::new(acc), Box::new(val)),
        '/' => Expression::Div(Box::new(acc), Box::new(val)),
        '%' => Expression::Mod(Box::new(acc), Box::new(val)),
        _ => unreachable!(),
    });
    Ok((input, result))
}

fn expression(input: &str) -> IResult<&str, Expression> {
    alt((map(tag("null"), |_| Expression::Null), expression_inner))(input)
}

fn expression_inner(input: &str) -> IResult<&str, Expression> {
    let (input, init) = term(input)?;
    let (input, ops) = many0(pair(ws(alt((char_p('+'), char_p('-')))), term))(input)?;
    let result = ops.into_iter().fold(init, |acc, (op, val)| match op {
        '+' => Expression::Add(Box::new(acc), Box::new(val)),
        '-' => Expression::Sub(Box::new(acc), Box::new(val)),
        _ => unreachable!(),
    });
    Ok((input, result))
}

fn set_variable(input: &str) -> IResult<&str, Statement> {
    let (input, _) = char_p('$')(input)?;
    let (input, name) = identifier(input)?;
    let (input, _) = ws(char_p('='))(input)?;
    let (input, expr) = expression(input)?;
    let (input, _) = ws(char_p(';'))(input)?;
    Ok((input, Statement::SetVariable(name.to_string(), expr)))
}

fn map_object(input: &str) -> IResult<&str, (String, Option<Expression>)> {
    let (input, label) = ws(identifier)(input)?;
    let (input, key) = opt(delimited(ws(char_p('[')), expression, ws(char_p(']'))))(input)?;
    Ok((input, (label.to_string(), key)))
}

fn map_func(input: &str) -> IResult<&str, (String, Vec<Expression>)> {
    let (input, label) = ws(identifier)(input)?;
    let (input, _) = ws(char_p('('))(input)?;
    let (input, args) = separated_list0(ws(char_p(',')), opt(expression))(input)?;
    let (input, _) = ws(char_p(')'))(input)?;
    let args: Vec<Expression> = args
        .into_iter()
        .map(|a| a.unwrap_or(Expression::Null))
        .collect();
    Ok((input, (label.to_string(), args)))
}

fn map_element(input: &str) -> IResult<&str, Statement> {
    let (input, objects) = many1(terminated(map_object, ws(char_p('.'))))(input)?;
    let (input, func) = map_func(input)?;
    let (input, _) = ws(char_p(';'))(input)?;
    Ok((input, Statement::MapElement(objects, func)))
}

fn set_distance(input: &str) -> IResult<&str, Statement> {
    let (input, expr) = expression(input)?;
    let (input, _) = ws(char_p(';'))(input)?;
    Ok((input, Statement::SetDistance(expr)))
}

fn include_file(input: &str) -> IResult<&str, Statement> {
    let (input, _) = alt((tag("Include"), tag("include")))(input)?;
    let (input, expr) = expression(input)?;
    let (input, _) = ws(char_p(';'))(input)?;
    Ok((input, Statement::Include(expr)))
}

fn null_statement(input: &str) -> IResult<&str, Statement> {
    let (input, _) = char_p(';')(input)?;
    Ok((input, Statement::Null))
}

fn statement(input: &str) -> IResult<&str, Statement> {
    let input = skip_ignored(input);
    alt((
        set_variable,
        map_element,
        include_file,
        set_distance,
        null_statement,
    ))(input)
}

pub fn parse_map(input: &str) -> IResult<&str, Vec<Statement>> {
    let mut rest = skip_ignored(input);
    let mut stmts = Vec::new();

    while !rest.is_empty() {
        let before = rest;
        let (next, stmt) = statement(rest)?;
        if next.len() == before.len() {
            return Err(nom::Err::Error(nom::error::Error::new(
                rest,
                nom::error::ErrorKind::Many0,
            )));
        }
        stmts.push(stmt);
        rest = skip_ignored(next);
    }

    Ok((rest, stmts))
}

#[derive(Debug, Clone)]
pub enum Expression {
    Number(f64),
    String(String),
    Variable(String),
    Label(String),
    Add(Box<Expression>, Box<Expression>),
    Sub(Box<Expression>, Box<Expression>),
    Mul(Box<Expression>, Box<Expression>),
    Div(Box<Expression>, Box<Expression>),
    Mod(Box<Expression>, Box<Expression>),
    Neg(Box<Expression>),
    FunctionCall(String, Vec<Expression>),
    Null,
}

#[derive(Debug, Clone)]
pub enum Statement {
    SetDistance(Expression),
    SetVariable(String, Expression),
    MapElement(Vec<(String, Option<Expression>)>, (String, Vec<Expression>)),
    Include(Expression),
    Null,
}

pub struct MapInterpreter {
    pub env: Environment,
    is_root: bool,
    random_state: u64,
}

impl MapInterpreter {
    pub fn new() -> Self {
        MapInterpreter {
            env: Environment::new(),
            is_root: true,
            random_state: 0xDEADBEEF,
        }
    }

    pub fn new_child(env: Environment) -> Self {
        MapInterpreter {
            env,
            is_root: false,
            random_state: 0xDEADBEEF,
        }
    }

    fn pseudo_random(&mut self) -> f64 {
        self.random_state = self
            .random_state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.random_state as f64) / (u64::MAX as f64)
    }

    pub fn eval_expression(&mut self, expr: &Expression) -> f64 {
        match expr {
            Expression::Number(n) => *n,
            Expression::String(_) => 0.0,
            Expression::Variable(name) => {
                let name_lower = name.to_lowercase();
                if let Some(v) = self.env.predef_vars.get(&name_lower) {
                    *v
                } else {
                    self.env.variable.get(&name_lower).copied().unwrap_or(0.0)
                }
            }
            Expression::Label(name) => {
                let name_lower = name.to_lowercase();
                self.env
                    .predef_vars
                    .get(&name_lower)
                    .copied()
                    .unwrap_or(0.0)
            }
            Expression::Add(a, b) => {
                let av = self.eval_expression(a);
                let bv = self.eval_expression(b);
                av + bv
            }
            Expression::Sub(a, b) => {
                let av = self.eval_expression(a);
                let bv = self.eval_expression(b);
                av - bv
            }
            Expression::Mul(a, b) => {
                let av = self.eval_expression(a);
                let bv = self.eval_expression(b);
                av * bv
            }
            Expression::Div(a, b) => {
                let av = self.eval_expression(a);
                let bv = self.eval_expression(b);
                if bv == 0.0 {
                    if av >= 0.0 {
                        f64::INFINITY
                    } else {
                        f64::NEG_INFINITY
                    }
                } else {
                    av / bv
                }
            }
            Expression::Mod(a, b) => {
                let av = self.eval_expression(a);
                let bv = self.eval_expression(b);
                if bv == 0.0 {
                    0.0
                } else {
                    av % bv
                }
            }
            Expression::Neg(a) => -self.eval_expression(a),
            Expression::FunctionCall(name, args) => self.call_function(name, args),
            Expression::Null => 0.0,
        }
    }

    fn call_function(&mut self, name: &str, args: &[Expression]) -> f64 {
        let name_lower = name.to_lowercase();
        if name_lower == "rand" {
            if args.is_empty() {
                self.pseudo_random()
            } else {
                let max = self.eval_expression(&args[0]);
                self.pseudo_random() * max
            }
        } else if name_lower == "abs" {
            if args.is_empty() {
                0.0
            } else {
                self.eval_expression(&args[0]).abs()
            }
        } else {
            let val = if args.is_empty() {
                1.0
            } else {
                self.eval_expression(&args[0])
            };
            match name_lower.as_str() {
                "sin" => val.sin(),
                "cos" => val.cos(),
                "tan" => val.tan(),
                "asin" => val.asin(),
                "acos" => val.acos(),
                "atan" => val.atan(),
                "sinh" => val.sinh(),
                "cosh" => val.cosh(),
                "tanh" => val.tanh(),
                "exp" => val.exp(),
                "log" => val.ln(),
                "log10" => val.log10(),
                "sqrt" => val.sqrt(),
                "ceil" => val.ceil(),
                "floor" => val.floor(),
                "round" => val.round(),
                "atan2" => {
                    if args.len() >= 2 {
                        let x = self.eval_expression(&args[1]);
                        val.atan2(x)
                    } else {
                        0.0
                    }
                }
                "pow" => {
                    if args.len() >= 2 {
                        let exp = self.eval_expression(&args[1]);
                        val.powf(exp)
                    } else {
                        val
                    }
                }
                _ => val,
            }
        }
    }

    pub fn eval_string(&mut self, expr: &Expression) -> String {
        match expr {
            Expression::String(s) => s.clone(),
            Expression::Number(n) => format_number_for_key(*n),
            Expression::Variable(_) => format_number_for_key(self.eval_expression(expr)),
            Expression::Label(name) => name.clone(),
            Expression::Add(a, b) => {
                let sa = self.eval_string(a);
                let sb = self.eval_string(b);
                format!("{}{}", sa, sb)
            }
            Expression::Null => String::new(),
            _ => format_number_for_key(self.eval_expression(expr)),
        }
    }

    pub fn interpret(&mut self, statements: &[Statement]) {
        for stmt in statements {
            self.interpret_statement(stmt);
        }
        if self.is_root {
            self.env.controlpoints.relocate();
            self.env.own_track.relocate();
            self.env.othertrack.relocate();
            self.env.speedlimit.relocate();
        }
    }

    fn interpret_statement(&mut self, stmt: &Statement) {
        match stmt {
            Statement::SetDistance(expr) => {
                let val = self.eval_expression(expr);
                self.env.predef_vars.insert("distance".to_string(), val);
                self.env.controlpoints.add(val);
            }
            Statement::SetVariable(name, expr) => {
                let val = self.eval_expression(expr);
                self.env.variable.insert(name.to_lowercase(), val);
            }
            Statement::MapElement(objects, (func_name, func_args)) => {
                self.interpret_map_element(objects, func_name, func_args);
            }
            Statement::Include(expr) => {
                let path = self.eval_string(expr);
                self.include_file(&path);
            }
            Statement::Null => {}
        }
    }

    fn interpret_map_element(
        &mut self,
        objects: &[(String, Option<Expression>)],
        func_name: &str,
        func_args: &[Expression],
    ) {
        let first_obj = objects[0].0.to_lowercase();

        match first_obj.as_str() {
            "curve" | "gradient" | "legacy" => {
                self.handle_owntrack(objects, func_name, func_args, &first_obj);
            }
            "station" => {
                self.handle_station(objects, func_name, func_args);
            }
            "track" => {
                self.handle_othertrack(objects, func_name, func_args);
            }
            "speedlimit" => {
                self.handle_speedlimit(func_name, func_args);
            }
            _ => {}
        }
    }

    fn handle_owntrack(
        &mut self,
        _objects: &[(String, Option<Expression>)],
        func_name: &str,
        func_args: &[Expression],
        category: &str,
    ) {
        let distance = *self.env.predef_vars.get("distance").unwrap_or(&0.0);
        let func_name_l = func_name.to_lowercase();

        match (category, func_name_l.as_str()) {
            ("curve", "setgauge") | ("curve", "gauge") => {
                let v = self.extract_arg(func_args, 0);
                self.env.own_track.putdata("gauge", Some(v), "", distance);
            }
            ("curve", "setcenter") => {
                let v = self.extract_arg(func_args, 0);
                self.env.own_track.putdata("center", Some(v), "", distance);
            }
            ("curve", "setfunction") => {
                let v = self.extract_arg(func_args, 0);
                self.env.own_track.putdata(
                    "interpolate_func",
                    Some(if v == 0.0 { 0.0 } else { 1.0 }),
                    "",
                    distance,
                );
            }
            ("curve", "begintransition") => {
                self.env.own_track.putdata("radius", None, "bt", distance);
                self.env.own_track.putdata("cant", None, "bt", distance);
            }
            ("curve", "begincircular") | ("curve", "begin") => {
                let r = self.extract_arg(func_args, 0);
                let c = if func_args.len() >= 2 {
                    self.eval_expression(&func_args[1])
                } else {
                    0.0
                };
                self.env.own_track.putdata("radius", Some(r), "", distance);
                self.env.own_track.putdata("cant", Some(c), "", distance);
            }
            ("curve", "end") => {
                self.env
                    .own_track
                    .putdata("radius", Some(0.0), "", distance);
                self.env.own_track.putdata("cant", Some(0.0), "", distance);
            }
            ("curve", "interpolate") => {
                let r = self.extract_arg(func_args, 0);
                let c = if func_args.len() >= 2 {
                    self.eval_expression(&func_args[1])
                } else {
                    0.0
                };
                self.env.own_track.putdata("radius", Some(r), "i", distance);
                if func_args.len() >= 2 {
                    self.env.own_track.putdata("cant", Some(c), "i", distance);
                } else {
                    self.env.own_track.putdata("cant", None, "i", distance);
                }
            }
            ("curve", "change") => {
                let r = self.extract_arg(func_args, 0);
                let c = if func_args.len() >= 2 {
                    self.eval_expression(&func_args[1])
                } else {
                    0.0
                };
                self.env.own_track.putdata("radius", Some(r), "", distance);
                self.env.own_track.putdata("cant", Some(c), "", distance);
            }

            ("legacy", "turn") => {
                let v = self.extract_arg(func_args, 0);
                self.env.own_track.putdata("turn", Some(v), "", distance);
            }
            ("legacy", "curve") => {
                let r = self.extract_arg(func_args, 0);
                let c = if func_args.len() >= 2 {
                    self.eval_expression(&func_args[1])
                } else {
                    0.0
                };
                self.env.own_track.putdata("radius", Some(r), "", distance);
                self.env.own_track.putdata("cant", Some(c), "", distance);
            }
            ("legacy", "pitch") => {
                let v = self.extract_arg(func_args, 0);
                self.env
                    .own_track
                    .putdata("gradient", Some(v), "", distance);
            }
            ("legacy", "fog") => {}

            ("gradient", "begintransition") => {
                self.env.own_track.putdata("gradient", None, "bt", distance);
            }
            ("gradient", "begin") | ("gradient", "beginconst") => {
                let v = self.extract_arg(func_args, 0);
                self.env
                    .own_track
                    .putdata("gradient", Some(v), "", distance);
            }
            ("gradient", "end") => {
                self.env
                    .own_track
                    .putdata("gradient", Some(0.0), "", distance);
            }
            ("gradient", "interpolate") => {
                let v = self.extract_arg(func_args, 0);
                self.env
                    .own_track
                    .putdata("gradient", Some(v), "i", distance);
            }
            _ => {}
        }
    }

    fn handle_station(
        &mut self,
        objects: &[(String, Option<Expression>)],
        func_name: &str,
        func_args: &[Expression],
    ) {
        let distance = *self.env.predef_vars.get("distance").unwrap_or(&0.0);
        let func_name_l = func_name.to_lowercase();

        match func_name_l.as_str() {
            "load" => {
                let filename = self.eval_string(&func_args[0]);
                self.load_station_list(&filename);
            }
            "put" => {
                let key = if func_args.len() >= 1 {
                    self.eval_string(&func_args[0]).to_lowercase()
                } else {
                    String::new()
                };
                let key_obj = objects[0].1.as_ref();
                let station_key = if let Some(expr) = key_obj {
                    self.eval_string(expr).to_lowercase()
                } else {
                    key
                };
                self.env
                    .station
                    .position
                    .insert(StationDist(distance), station_key);
            }
            _ => {}
        }
    }

    fn handle_othertrack(
        &mut self,
        objects: &[(String, Option<Expression>)],
        func_name: &str,
        func_args: &[Expression],
    ) {
        let distance = *self.env.predef_vars.get("distance").unwrap_or(&0.0);
        let track_key = if let Some(expr) = objects[0].1.as_ref() {
            self.eval_string(expr)
        } else {
            String::new()
        };
        let tk = if track_key.is_empty() {
            "0".to_string()
        } else {
            track_key.to_lowercase()
        };
        let func_name_l = func_name.to_lowercase();
        let sub_obj = objects.get(1).map(|o| o.0.to_lowercase());

        if matches!(sub_obj.as_deref(), Some("x") | Some("y")) {
            if func_name_l == "interpolate" {
                let prefix = sub_obj.as_deref().unwrap();
                match func_args.len() {
                    0 => {
                        self.env.othertrack.putdata(
                            &tk,
                            &format!("{}.position", prefix),
                            None,
                            "",
                            distance,
                        );
                        self.env.othertrack.putdata(
                            &tk,
                            &format!("{}.radius", prefix),
                            None,
                            "",
                            distance,
                        );
                    }
                    1 => {
                        let pos = self.eval_expression(&func_args[0]);
                        self.env.othertrack.putdata(
                            &tk,
                            &format!("{}.position", prefix),
                            Some(pos),
                            "",
                            distance,
                        );
                        self.env.othertrack.putdata(
                            &tk,
                            &format!("{}.radius", prefix),
                            None,
                            "",
                            distance,
                        );
                    }
                    _ => {
                        let pos = self.eval_expression(&func_args[0]);
                        let radius = self.eval_expression(&func_args[1]);
                        self.env.othertrack.putdata(
                            &tk,
                            &format!("{}.position", prefix),
                            Some(pos),
                            "",
                            distance,
                        );
                        self.env.othertrack.putdata(
                            &tk,
                            &format!("{}.radius", prefix),
                            Some(radius),
                            "",
                            distance,
                        );
                    }
                }
            }
            return;
        }

        match func_name_l.as_str() {
            "position" => {
                let x = if !func_args.is_empty() {
                    self.eval_expression(&func_args[0])
                } else {
                    0.0
                };
                let y = if func_args.len() >= 2 {
                    self.eval_expression(&func_args[1])
                } else {
                    0.0
                };
                let r = if func_args.len() >= 3 {
                    self.eval_expression(&func_args[2])
                } else {
                    0.0
                };
                self.env
                    .othertrack
                    .putdata(&tk, "x.position", Some(x), "", distance);
                self.env
                    .othertrack
                    .putdata(&tk, "x.radius", Some(r), "", distance);
                self.env
                    .othertrack
                    .putdata(&tk, "y.position", Some(y), "", distance);
                if func_args.len() >= 4 {
                    let ry = self.eval_expression(&func_args[3]);
                    self.env
                        .othertrack
                        .putdata(&tk, "y.radius", Some(ry), "", distance);
                } else {
                    self.env
                        .othertrack
                        .putdata(&tk, "y.radius", Some(0.0), "", distance);
                }
            }
            "gauge" | "setgauge" => {
                let v = self.extract_arg(func_args, 0);
                self.env
                    .othertrack
                    .putdata(&tk, "gauge", Some(v), "", distance);
            }
            "setcenter" => {
                let v = self.extract_arg(func_args, 0);
                self.env
                    .othertrack
                    .putdata(&tk, "center", Some(v), "", distance);
            }
            "setfunction" => {
                let v = self.extract_arg(func_args, 0);
                let func_val = if v == 0.0 { 0.0 } else { 1.0 };
                self.env
                    .othertrack
                    .putdata(&tk, "interpolate_func", Some(func_val), "", distance);
            }
            "begintransition" => {
                self.env
                    .othertrack
                    .putdata(&tk, "cant", None, "bt", distance);
            }
            "begin" => {
                let v = self.extract_arg(func_args, 0);
                self.env
                    .othertrack
                    .putdata(&tk, "cant", Some(v), "i", distance);
            }
            "end" => {
                self.env
                    .othertrack
                    .putdata(&tk, "cant", Some(0.0), "i", distance);
            }
            "cant" | "interpolate" => {
                if func_args.is_empty() {
                    self.env
                        .othertrack
                        .putdata(&tk, "cant", None, "i", distance);
                } else {
                    let v = self.eval_expression(&func_args[0]);
                    self.env
                        .othertrack
                        .putdata(&tk, "cant", Some(v), "i", distance);
                }
            }
            _ => {}
        }
    }

    fn handle_speedlimit(&mut self, func_name: &str, func_args: &[Expression]) {
        let distance = *self.env.predef_vars.get("distance").unwrap_or(&0.0);
        match func_name.to_lowercase().as_str() {
            "begin" => {
                let speed = self.extract_arg(func_args, 0);
                self.env.speedlimit.begin(Some(speed), distance);
            }
            "end" => {
                self.env.speedlimit.begin(None, distance);
            }
            _ => {}
        }
    }

    fn extract_arg(&mut self, args: &[Expression], idx: usize) -> f64 {
        args.get(idx)
            .map(|e| self.eval_expression(e))
            .unwrap_or(0.0)
    }

    fn include_file(&mut self, path: &str) {
        let full_path = Self::join_path(&self.env.rootpath, path);
        if let Ok(env) = Self::load_file_child(&full_path, std::mem::take(&mut self.env)) {
            self.env = env;
        }
    }

    fn load_station_list(&mut self, filename: &str) {
        let full_path = Self::join_path(&self.env.rootpath, filename);
        let (_, _, encoding) = match read_header(&full_path, "BveTs Station List ", 0.04) {
            Ok(header) => header,
            Err(_) => return,
        };
        let raw = match std::fs::read(&full_path) {
            Ok(data) => data,
            Err(_) => return,
        };
        let content = decode_with_fallback(&raw, &encoding);
        let body = strip_first_line(&content);

        for line in body.lines() {
            let line = line
                .split('#')
                .next()
                .unwrap_or("")
                .replace(['\t', ' '], "");
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            let parts: Vec<&str> = line.splitn(2, ',').collect();
            if parts.len() >= 2 {
                let key = parts[0].trim().to_lowercase();
                let name = parts[1].trim().trim_matches('"');
                self.env.station.stationkey.insert(key, name.to_string());
            }
        }
    }

    fn join_path(rootpath: &str, filepath: &str) -> String {
        let rp = std::path::Path::new(rootpath);
        let fp = std::path::Path::new(filepath);
        rp.join(fp).to_string_lossy().to_string()
    }

    pub fn load_file(path: &str) -> Result<Environment, String> {
        let (_, rootpath, encoding) = read_header(path, "BveTs Map ", 2.0)?;

        let raw = match std::fs::read(path) {
            Ok(data) => data,
            Err(e) => return Err(format!("Cannot read file: {}", e)),
        };

        let content = decode_with_fallback(&raw, &encoding);
        let body = strip_first_line(&content);

        let mut interpreter = MapInterpreter::new();
        interpreter.env.rootpath = rootpath;

        match parse_map(body) {
            Ok((_, statements)) => {
                interpreter.interpret(&statements);
                Ok(interpreter.env)
            }
            Err(e) => Err(format!("Parse error: {}", e)),
        }
    }

    fn load_file_child(path: &str, parent_env: Environment) -> Result<Environment, String> {
        let (_, rootpath, encoding) = read_header(path, "BveTs Map ", 2.0)?;

        let raw = match std::fs::read(path) {
            Ok(data) => data,
            Err(e) => return Err(format!("Cannot read file: {}", e)),
        };

        let content = decode_with_fallback(&raw, &encoding);
        let body = strip_first_line(&content);

        let mut child_env = parent_env;
        if child_env.rootpath.is_empty() {
            child_env.rootpath = rootpath;
        }

        let mut interpreter = MapInterpreter::new_child(child_env);

        match parse_map(body) {
            Ok((_, statements)) => {
                interpreter.interpret(&statements);
                Ok(interpreter.env)
            }
            Err(e) => Err(format!("Parse error in include: {}", e)),
        }
    }

    fn read_file_with_encoding_fallback(path: &str) -> Option<(String, String)> {
        let raw = std::fs::read(path).ok()?;
        let content = decode_with_fallback(&raw, "utf-8");
        Some((content, "utf-8".to_string()))
    }
}

fn strip_first_line(content: &str) -> &str {
    content.split_once('\n').map(|(_, body)| body).unwrap_or("")
}

fn format_number_for_key(value: f64) -> String {
    if value.is_finite() && (value - value.round()).abs() < 1e-9 {
        format!("{}", value.round() as i64)
    } else {
        format!("{}", value)
    }
}

pub fn read_header(
    path: &str,
    head_str: &str,
    head_ver: f64,
) -> Result<(String, String, String), String> {
    let p = std::path::Path::new(path);
    let rootpath = p
        .parent()
        .map(|r| r.to_string_lossy().to_string())
        .unwrap_or_default();

    let raw = match std::fs::read(path) {
        Ok(data) => data,
        Err(e) => return Err(format!("File open error: {}: {}", path, e)),
    };

    let header_encoding = if raw.len() >= 2 {
        if raw[0] == 0xFF && raw[1] == 0xFE {
            "utf-16le"
        } else if raw[0] == 0xFE && raw[1] == 0xFF {
            "utf-16be"
        } else {
            "utf-8"
        }
    } else {
        "utf-8"
    };

    let header = decode_with_header_encoding(&raw, header_encoding);
    let first_line = header.lines().next().unwrap_or("");

    if !first_line.to_lowercase().contains(&head_str.to_lowercase()) {
        return Err(format!("{} is not {}", path, head_str));
    }

    let version: f64 = first_line
        .split(|c: char| !c.is_ascii_digit() && c != '.')
        .filter(|s| s.contains('.') && s.chars().filter(|&c| c == '.').count() == 1)
        .filter_map(|s| s.parse().ok())
        .next()
        .unwrap_or(0.0);

    if version < head_ver {
        return Err(format!("{} is under Ver.{}", path, head_ver));
    }

    let file_encoding: String = if header_encoding == "utf-8" {
        let enc_tag: Option<String> = first_line
            .split(':')
            .skip(1)
            .filter_map(|s| {
                let s = s.trim();
                let chars: String = s
                    .chars()
                    .take_while(|c| c.is_alphanumeric() || *c == '-' || *c == '_')
                    .collect();
                if chars.is_empty() {
                    None
                } else {
                    Some(chars)
                }
            })
            .next();
        match enc_tag {
            Some(ref s) if s == "shift_jis" || s == "sjis" => "cp932".to_string(),
            Some(s) => s,
            None => "utf-8".to_string(),
        }
    } else {
        header_encoding.to_string()
    };

    Ok((first_line.to_string(), rootpath, file_encoding))
}

fn decode_with_header_encoding(raw: &[u8], encoding: &str) -> String {
    let enc_label = match encoding.to_lowercase().as_str() {
        "utf-8" => "utf-8",
        "cp932" | "shift_jis" | "sjis" => "shift_jis",
        "utf-16le" => "utf-16le",
        "utf-16be" => "utf-16be",
        _ => "utf-8",
    };
    if enc_label == "shift_jis" {
        let (cow, _, _) = encoding_rs::SHIFT_JIS.decode(raw);
        cow.into_owned()
    } else if enc_label == "utf-16le" {
        let (cow, _, _) = encoding_rs::UTF_16LE.decode(raw);
        cow.into_owned()
    } else if enc_label == "utf-16be" {
        let (cow, _, _) = encoding_rs::UTF_16BE.decode(raw);
        cow.into_owned()
    } else {
        String::from_utf8_lossy(raw).to_string()
    }
}

fn decode_with_fallback(raw: &[u8], encoding: &str) -> String {
    let first_try = decode_with_encoding(raw, encoding);
    match first_try {
        Some(s) => s,
        None => {
            let retry_enc = if encoding.to_lowercase() == "utf-8" {
                "shift_jis"
            } else {
                "utf-8"
            };
            decode_with_encoding(raw, retry_enc)
                .unwrap_or_else(|| String::from_utf8_lossy(raw).to_string())
        }
    }
}

fn decode_with_encoding(raw: &[u8], encoding: &str) -> Option<String> {
    let enc_label = match encoding.to_lowercase().as_str() {
        "utf-8" => "utf-8",
        "cp932" | "shift_jis" | "sjis" => "shift_jis",
        "utf-16le" => "utf-16le",
        "utf-16be" => "utf-16be",
        _ => "utf-8",
    };
    if enc_label == "shift_jis" {
        let (cow, _, had_errors) = encoding_rs::SHIFT_JIS.decode(raw);
        if had_errors {
            None
        } else {
            Some(cow.into_owned())
        }
    } else if enc_label == "utf-16le" {
        let (cow, _, had_errors) = encoding_rs::UTF_16LE.decode(raw);
        if had_errors {
            None
        } else {
            Some(cow.into_owned())
        }
    } else if enc_label == "utf-16be" {
        let (cow, _, had_errors) = encoding_rs::UTF_16BE.decode(raw);
        if had_errors {
            None
        } else {
            Some(cow.into_owned())
        }
    } else {
        match std::str::from_utf8(raw) {
            Ok(s) => Some(s.to_string()),
            Err(_) => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_dotted_map_elements_and_comments() {
        let src = r#"
            # comment
            0;
            Curve.SetGauge(1067);
            100;
            Track['sub'].X.Interpolate(3.5, 0);
            Track['sub'].Cant(25);
            SpeedLimit.Begin(80);
        "#;

        let (_, statements) = parse_map(src).expect("map body should parse");
        let mut interpreter = MapInterpreter::new();
        interpreter.interpret(&statements);

        assert_eq!(interpreter.env.controlpoints.list_cp, vec![0.0, 100.0]);
        assert!(interpreter
            .env
            .own_track
            .data
            .iter()
            .any(|e| e.key == "gauge"));
        let other = interpreter
            .env
            .othertrack
            .data
            .get("sub")
            .expect("other track");
        assert!(other
            .iter()
            .any(|e| e.key == "x.position" && (e.value.as_value() - 3.5).abs() < 1e-9));
        assert!(other
            .iter()
            .any(|e| e.key == "cant" && (e.value.as_value() - 25.0).abs() < 1e-9));
        assert_eq!(interpreter.env.speedlimit.data.len(), 1);
    }

    #[test]
    fn load_file_skips_map_header() {
        let path = std::env::temp_dir().join("kobushi_rs_parser_header_test.map");
        std::fs::write(&path, "BveTs Map 2.02:utf-8\n0;\n100;\n").expect("write temp map");

        let env = MapInterpreter::load_file(path.to_str().unwrap()).expect("load map");

        assert_eq!(env.controlpoints.list_cp, vec![0.0, 100.0]);
        let _ = std::fs::remove_file(path);
    }
}
