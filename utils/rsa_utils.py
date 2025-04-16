from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from decouple import config

# Load keys
private_key = load_pem_private_key(
    config("PRIVATE_KEY").encode(),
    password=None
)

public_key = load_pem_public_key(
    config("PUBLIC_KEY").encode()
)

def rsa_encrypt(message: bytes) -> bytes:
    """
    Encrypt a message using the RSA public key.

    Args:
        message (bytes): The plaintext message to encrypt.

    Returns:
        bytes: The encrypted message.
    """
    return public_key.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def rsa_decrypt(encrypted_message: bytes) -> bytes:
    """
    Decrypt an RSA encrypted message using the RSA private key.

    Args:
        encrypted_message (bytes): The encrypted message to decrypt.

    Returns:
        bytes: The decrypted plaintext message.
    """
    return private_key.decrypt(
        encrypted_message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
