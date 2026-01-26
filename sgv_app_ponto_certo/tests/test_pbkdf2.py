try:
    from passlib.hash import pbkdf2_sha256

    print("✓ pbkdf2_sha256 disponível")

    # Teste a verificação
    stored_hash = "$pbkdf2-sha256$29000$BiDE2Lu3Viql1LqXco4R4g$GUOmDoA6cCO2hHt2e5r5JoVH7UMeg9HDGxuquDo0wds"
    test_password = "root"

    result = pbkdf2_sha256.verify(test_password, stored_hash)
    print(f"Verificação de 'root' contra hash admin: {result}")

except ImportError as e:
    print(f"✗ Erro ao importar pbkdf2_sha256: {e}")
