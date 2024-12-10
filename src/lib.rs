use bzip2::read::BzDecoder;
use crc32fast::Hasher;
use memmap2::{Mmap, MmapMut};
use pyo3::prelude::*;
use qbsdiff::Bspatch;
use std::fs::File;
use std::io::{self, Read};
use std::os::unix::io::FromRawFd;

#[pyfunction]
fn bspatch_rs(py: Python<'_>, source: i32, patch: &[u8]) -> io::Result<Vec<u8>> {
    py.allow_threads(|| {
        let patcher = Bspatch::new(patch)?;
        let file = unsafe { File::from_raw_fd(source) };
        let original_size = file.metadata()?.len();
        // Ensure file is resized to accommodate the patch
        if original_size < patcher.hint_target_size() {
            file.set_len(patcher.hint_target_size())?;
        }
        let mut mmap = unsafe {
            MmapMut::map_mut(&file).map_err(|e| {
                io::Error::new(io::ErrorKind::Other, format!("Failed to map source: {}", e))
            })?
        };
        // Don't run the destructor. We'll manage the resource within Python
        std::mem::forget(file);
        let mut target = Vec::new();
        patcher.apply(&mmap[..original_size as usize], &mut target)?;
        // Validate target size before writing to mmap
        if target.len() > mmap.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Patch exceeds mapped file size",
            ));
        }
        mmap[..target.len()].copy_from_slice(&target[..]);
        // Handle small file case
        if target.len() < original_size as usize {
            let file = unsafe { File::from_raw_fd(source) };
            file.set_len(target.len() as u64)?;
            std::mem::forget(file);
        }
        Ok(target)
    })
}

#[pyfunction]
fn bz2_decompress_rs(py: Python<'_>, source: &[u8], target: i32) -> io::Result<u64> {
    py.allow_threads(|| {
        let mut file = unsafe { File::from_raw_fd(target) };
        let mut decoder = BzDecoder::new(source);
        let result = io::copy(&mut decoder, &mut file);
        std::mem::forget(file);
        return result;
    })
}

#[pyfunction]
fn crc32_rs(py: Python<'_>, source: i32) -> io::Result<u32> {
    py.allow_threads(|| {
        let mut file = unsafe { File::from_raw_fd(source) };
        let mut hasher = Hasher::new();
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)?;
        hasher.update(&buffer);
        std::mem::forget(file);
        Ok(hasher.finalize())
    })
}

#[pyfunction]
fn crc32_mmap_rs(py: Python<'_>, source: i32) -> u32 {
    py.allow_threads(|| {
        let file = unsafe { File::from_raw_fd(source) };
        let mmap = unsafe { Mmap::map(&file).ok() };
        let mut hasher = Hasher::new();
        if let Some(mmap) = mmap {
            hasher.update(&mmap[..]);
        }
        std::mem::forget(file);
        hasher.finalize()
    })
}

#[pymodule(name = "umu_delta")]
fn umu(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(bspatch_rs, m)?)?;
    m.add_function(wrap_pyfunction!(crc32_rs, m)?)?;
    m.add_function(wrap_pyfunction!(bz2_decompress_rs, m)?)?;
    m.add_function(wrap_pyfunction!(crc32_mmap_rs, m)?)?;
    Ok(())
}
