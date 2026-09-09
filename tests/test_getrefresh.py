"""刷新 Token 接口用例：AUTH-10。"""
import requests


def test_refresh_token_usable(admin_token, settings):
    """AUTH-10 刷新 Token：返回有效 token 并可用于受保护接口。

    已知设计契约：token 创建后 30 分钟内刷新返回原 token
    （JwtTokenUtil.refreshToken 的防滥用窗口），因此不断言新旧不同。
    """
    r = requests.get(f"{settings['base_url']}/admin/refreshToken",
                     headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    new_token = body["data"]["token"]
    assert new_token

    r2 = requests.get(f"{settings['base_url']}/admin/info",
                      headers={"Authorization": f"Bearer {new_token}"})
    assert r2.status_code == 200
    assert r2.json()["code"] == 200
