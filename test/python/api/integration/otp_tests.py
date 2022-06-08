from takumi.utils.login import create_login_code, get_otp_from_login_code


class RedisMock:
    values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, exp, value):
        self.values[key] = value

    def delete(self, key):
        del self.values[key]


def test_create_login_code_creates_a_working_login_code_to_retrieve_otp_token(app, monkeypatch):
    # Arrange
    monkeypatch.setattr("takumi.extensions.redis.get_connection", lambda *_: RedisMock())

    # Act
    otp = "SOME_OTP"
    login_code = create_login_code(otp)

    # Assert
    assert get_otp_from_login_code(login_code) == otp
