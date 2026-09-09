"""用户列表接口用例：无 Token 安全场景 + ADMIN-02 分页查询。"""
import requests


def test_admin_list_without_token(settings):
    """无 Token 访问用户列表：业务层 401，data 携带 Spring 安全提示"""
    r = requests.get(f"{settings['base_url']}/admin/list")
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 401
    assert body["message"] == "暂未登录或token已经过期"
    assert "Full authentication" in body["data"]


def test_admin_list_pagination(admin_token, settings):
    """ADMIN-02 默认分页查询：分页结构五个字段齐全，条数不超过 pageSize"""
    r = requests.get(f"{settings['base_url']}/admin/list?pageNum=1&pageSize=2",
                     headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    for key in ("pageNum", "pageSize", "totalPage", "total", "list"):
        assert key in body["data"], f"分页结构缺少 {key}"
    assert isinstance(body["data"]["list"], list)
    assert len(body["data"]["list"]) <= 2
