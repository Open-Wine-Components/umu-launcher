use pyo3::prelude::*;
use ssh_key::{PublicKey, SshSig};
use std::io::{self};

/// Required parameter to create/verify digital signatures
/// See https://cvsweb.openbsd.org/src/usr.bin/ssh/PROTOCOL.sshsig?annotate=HEAD
const NAMESPACE: &str = "umu.openwinecomponents.org";

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

#[pymodule(name = "umu_delta")]
fn umu(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ssh_verify_rs, m)?)?;
    Ok(())
}
