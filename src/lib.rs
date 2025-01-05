use base16ct::lower::encode_string;
use pyo3::prelude::*;
use sha2::{Digest, Sha512};
use ssh_key::{PublicKey, SshSig};

/// Required parameter to create/verify digital signatures
/// See https://cvsweb.openbsd.org/src/usr.bin/ssh/PROTOCOL.sshsig?annotate=HEAD
const NAMESPACE: &str = "umu.openwinecomponents.org";

/// Whitelist of valid OpenSSH formatted, Ed25519 public keys
/// Used for delta updates to create the root of trust
const PUBLIC_KEYS: [&str; 1] = ["5b0b4cd1dad99cd013d5a88cf27d6c7414db33ece7f3146f96fb0f62c64ec15317a22f3f05048ac29177be9d95c47856e01b6e2a3dc61dd8202df4156465899c"];

#[pyfunction]
fn valid_key(source: &str) -> bool {
    let hash = Sha512::digest(source.as_bytes());
    let hash_hex = &encode_string(&hash);
    PUBLIC_KEYS.contains(&hash_hex.as_str())
}

#[pyfunction]
fn valid_signature(source: &str, message: &[u8], pem: &[u8]) -> bool {
    let public_key = match PublicKey::from_openssh(source) {
        Ok(ret) => ret,
        Err(e) => {
            eprintln!("{}", e);
            return false;
        }
    };
    let ssh_sig = match SshSig::from_pem(pem) {
        Ok(ret) => ret,
        Err(e) => {
            eprintln!("{}", e);
            return false;
        }
    };
    public_key.verify(NAMESPACE, message, &ssh_sig).is_ok()
}

#[pymodule(name = "umu_delta")]
fn umu(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(valid_signature, m)?)?;
    m.add_function(wrap_pyfunction!(valid_key, m)?)?;
    Ok(())
}
