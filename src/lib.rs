use bzip2::read::BzDecoder;
use crc32fast::Hasher;
use memmap2::{Advice, Mmap, MmapMut};
use pyo3::prelude::*;
use qbsdiff::Bspatch;
use std::fs::File;
use std::io::{self, Read};
use std::os::unix::io::FromRawFd;

/// Given a binary patch, update a file in-place
///
/// `source`: writable, open file descriptor
/// `patch`: data produced from a BSDIFF 4.x compatible delta compressor
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
        // Don't run the destructor. We'll manage the file descriptor in Python
        std::mem::forget(file);
        let mut target = Vec::new();
        // Optimization. Let the kernel know the specific ranges we're
        // accessing. Here, we only need to access up to the original's
        // length
        mmap.advise_range(Advice::Sequential, 0, original_size as usize)
            .unwrap();
        patcher.apply(&mmap[..original_size as usize], &mut target)?;
        // Validate target size before writing to mmap
        if target.len() > mmap.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Patch exceeds mapped file size",
            ));
        }
        // Access the entire range, then apply our patched result in-place
        mmap.advise_range(Advice::Sequential, 0, target.len())
            .unwrap();
        mmap[..target.len()].copy_from_slice(&target[..]);
        // Handle small file case
        if target.len() < original_size as usize {
            let file = unsafe { File::from_raw_fd(source) };
            file.set_len(target.len() as u64)?;
            std::mem::forget(file);
        }
        mmap.flush_async()?;
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
