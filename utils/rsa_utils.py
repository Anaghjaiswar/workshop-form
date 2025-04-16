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
    Tries both OAEP and PKCS#1v1.5 padding.
    
    Args:
        encrypted_message (bytes): The encrypted message to decrypt.
        
    Returns:
        bytes: The decrypted plaintext message.
        
    Raises:
        ValueError: If decryption fails with both padding methods.
    """
    try:
        # Attempt decryption with OAEP padding
        return private_key.decrypt(
            encrypted_message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    except Exception as oaep_error:
        print(f"OAEP decryption failed: {str(oaep_error)}")
        try:
            # Fallback to PKCS#1v1.5 padding
            return private_key.decrypt(
                encrypted_message,
                padding.PKCS1v15()
            )
        except Exception as pkcs_error:
            print(f"PKCS#1v1.5 decryption failed: {str(pkcs_error)}")
            raise ValueError("Decryption failed with both OAEP and PKCS#1v1.5 padding.") from pkcs_error