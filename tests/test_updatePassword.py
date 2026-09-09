"""修改密码接口用例：ADMIN-07。"""
import requests


def test_update_password_wrong_old(admin_token, settings):
    """ADMIN-07 旧密码错误时修改密码：失败，且原密码仍可登录（前后两段）"""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 前半段：错误旧密码 → 业务层拒绝
    r = requests.post(f"{settings['base_url']}/admin/updatePassword",
                      json={"username": "admin",
                            "oldPassword": "224",
                            "newPassword": "1223"},
                      headers=headers)
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 500
    assert "密码错误" in body["message"]

    # 后半段：修改失败后，原密码仍可正常登录（密码未被改动）
    r2 = requests.post(f"{settings['base_url']}/admin/login",
                       json=settings["accounts"]["admin"])
    assert r2.status_code == 200
    assert r2.json()["code"] == 200

