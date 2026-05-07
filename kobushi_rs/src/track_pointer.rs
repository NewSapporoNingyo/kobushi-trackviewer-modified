use crate::environment::*;

#[derive(Debug, Clone)]
pub struct TrackPointer {
    pub last: Option<usize>,
    pub next: Option<usize>,
    target: String,
}

impl TrackPointer {
    pub fn new(data: &[TrackElement], target: &str) -> Self {
        let next = Self::seek(data, 0, target);
        TrackPointer {
            last: None,
            next,
            target: target.to_string(),
        }
    }

    fn seek(data: &[TrackElement], ix0: usize, target: &str) -> Option<usize> {
        let mut ix = ix0;
        while ix < data.len() {
            if data[ix].key == target {
                return Some(ix);
            }
            ix += 1;
        }
        None
    }

    pub fn seek_next(&mut self, data: &[TrackElement]) {
        if let Some(n) = self.next {
            self.last = Some(n);
            self.next = Self::seek(data, n + 1, &self.target);
        }
    }

    pub fn on_next_point(&self, data: &[TrackElement], distance: f64) -> bool {
        if let Some(n) = self.next {
            (data[n].distance - distance).abs() < 1e-9
        } else {
            false
        }
    }

    pub fn over_next_point(&self, data: &[TrackElement], distance: f64) -> bool {
        if let Some(n) = self.next {
            data[n].distance < distance
        } else {
            false
        }
    }

    pub fn seek_origin_of_continuous(&self, data: &[TrackElement], index: usize) -> Option<usize> {
        let mut ix = index as isize;
        while ix >= 0 {
            let i = ix as usize;
            if data[i].key == self.target && !data[i].value.is_continue() {
                return Some(i);
            }
            ix -= 1;
        }
        None
    }
}
