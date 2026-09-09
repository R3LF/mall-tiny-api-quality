"""用户查询接口用例：ADMIN-04。"""
import requests


def test_admin_get_nonexistent_id(admin_token, settings):
    """ADMIN-04 查询不存在的用户 ID：约定的空结果（code 200 + data null）"""
    r = requests.get(f"{settings['base_url']}/admin/99999",
                     headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    assert body["data"] is None
