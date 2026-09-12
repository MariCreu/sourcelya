from app.core.security import generate_secure_token, hash_token


def test_generated_tokens_are_unique_and_reasonably_long():
    tokens = {generate_secure_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(token) >= 32 for token in tokens)


def test_hash_is_deterministic_and_not_reversible_looking():
    token = generate_secure_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token


def test_different_tokens_hash_differently():
    a, b = generate_secure_token(), generate_secure_token()
    assert hash_token(a) != hash_token(b)
