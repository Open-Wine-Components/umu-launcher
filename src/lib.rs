use bzip2::read::BzDecoder;
use crc32fast::Hasher;
use memmap2::{Mmap, MmapMut, UncheckedAdvice};
use pyo3::prelude::*;
use qbsdiff::Bspatch;
use ssh_key::{PublicKey, SshSig};
use std::fs::File;
use std::io::{self, Read};
use std::os::unix::io::FromRawFd;
use zstd;

/// Required parameter to create/verify digital signatures
/// See https://cvsweb.openbsd.org/src/usr.bin/ssh/PROTOCOL.sshsig?annotate=HEAD
const NAMESPACE: &str = "umu.openwinecomponents.org";

/// Given a binary patch, update a file in-place
///
/// `source`: writable, open file descriptor
/// `patch`: data produced from a BSDIFF 4.x compatible delta compressor
#[pyfunction]
fn bspatch_rs(py: Python<'_>, source: i32, patch: &[u8]) -> io::Result<Vec<u8>> {
    py.allow_threads(|| {
        let patcher = Bspatch::new(patch)?;

        // Safety: We pass the file descriptor from Python, which is foreign
        // to Rust and handling them is currently always unsafe. While we
        // could pass a string representing the absolute file path instead,
        // it'll come at higher conversion and path resolution costs
        // See https://pyo3.rs/v0.23.1/conversions/tables.html#using-rust-library-types-vs-python-native-types
        let file = unsafe { File::from_raw_fd(source) };
        let original_size = file.metadata()?.len();

        // Ensure file is resized to accommodate the patch
        if original_size < patcher.hint_target_size() {
            file.set_len(patcher.hint_target_size())?;
        }

        // Safety: In context of applying partial updates, umu-launcher
        // mitigates this risk by holding a lock in Python's context before
        // applying the partial update in Rust and ensures mutual exclusivity
        // of file access
        // See https://docs.rs/memmap2/0.9.5/memmap2/struct.MmapMut.html#safety
        let mut mmap = unsafe {
            MmapMut::map_mut(&file).map_err(|e| {
                io::Error::new(io::ErrorKind::Other, format!("Failed to map source: {}", e))
            })?
        };

        // Don't run the destructor. We'll manage the file descriptor in Python
        std::mem::forget(file);
        let mut target = Vec::with_capacity(patcher.hint_target_size() as usize);

        patcher.apply(&mmap[..original_size as usize], &mut target)?;

        // Validate target size before writing to mmap
        if target.len() > mmap.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Patch exceeds mapped file size",
            ));
        }
        // Access the entire range, then apply our patched result in-place
        mmap[..target.len()].copy_from_slice(&target[..]);

        // Handle small file case
        if target.len() < original_size as usize {
            // Safety: See above for rationale
            let file = unsafe { File::from_raw_fd(source) };
            file.set_len(target.len() as u64)?;
            mmap.unchecked_advise_range(UncheckedAdvice::DontNeed, 0, target.len())?;
            std::mem::forget(file);
            return Ok(target);
        }

        mmap.unchecked_advise_range(UncheckedAdvice::DontNeed, 0, target.len())?;
        Ok(target)
    })
}

#[pyfunction]
fn bz2_decompress_rs(py: Python<'_>, source: &[u8], target: i32, size: u64) -> io::Result<u64> {
    py.allow_threads(|| {
        // Safety: See bspatch_rs for rationale on the use of unsafe
        let mut file = unsafe { File::from_raw_fd(target) };
        file.set_len(size)?;
        let mut decoder = BzDecoder::new(source);
        let result = io::copy(&mut decoder, &mut file);
        std::mem::forget(file);
        return result;
    })
}

#[pyfunction]
fn crc32_rs(py: Python<'_>, source: i32) -> io::Result<u32> {
    py.allow_threads(|| {
        // Safety: See bspatch_rs for rationale on the use of unsafe
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
        // Safety: See bspatch_rs for rationale on the use of unsafe
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

#[pyfunction]
fn ssh_verify_rs(source: &str, message: &[u8], pem: &[u8]) -> io::Result<()> {
    // Parse the public key
    let public_key = PublicKey::from_openssh(source)
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
    // Parse the signature from the PEM format
    let ssh_sig =
        SshSig::from_pem(pem).map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
    // Verify the signature
    public_key
        .verify(NAMESPACE, message, &ssh_sig)
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e.to_string()))?;
    Ok(())
}

#[pyfunction]
fn zstd_decompress_rs(py: Python<'_>, source: &[u8], target: i32, size: u64) -> io::Result<u64> {
    py.allow_threads(|| {
        let mut file = unsafe { File::from_raw_fd(target) };
        file.set_len(size)?;
        let mut decoder = zstd::Decoder::new(source)?;
        let result = io::copy(&mut decoder, &mut file);
        std::mem::forget(file);
        return result;
    })
}

#[pymodule(name = "umu_delta")]
fn umu(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(bspatch_rs, m)?)?;
    m.add_function(wrap_pyfunction!(crc32_rs, m)?)?;
    m.add_function(wrap_pyfunction!(bz2_decompress_rs, m)?)?;
    m.add_function(wrap_pyfunction!(crc32_mmap_rs, m)?)?;
    m.add_function(wrap_pyfunction!(ssh_verify_rs, m)?)?;
    m.add_function(wrap_pyfunction!(zstd_decompress_rs, m)?)?;
    Ok(())
}
