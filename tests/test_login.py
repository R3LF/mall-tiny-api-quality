"""登录接口用例：AUTH-01 ~ AUTH-06。

AUTH-01 成功用例单独写（断言 token/tokenHead，形状与失败用例不同）；
AUTH-02~05 失败矩阵数据驱动（data/login_cases.yaml）；
AUTH-06 非法 JSON 数据驱动（data/illegal_json.yaml），用 data= 原样发送。
CACHE-01  登录后产生用户/权限缓存
"""
import pytest
import requests
import json
import common

FAILURE_CASES = common.load_yaml("data/login_cases.yaml")
ILLEGAL_BODIES = common.load_yaml("data/illegal_json.yaml")


def test_login_success(settings):
    """AUTH-01 正确账号密码登录：返回 token 与 tokenHead 契约"""
    r = requests.post(f"{settings['base_url']}/admin/login",
                      json=settings["accounts"]["admin"])
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    assert body["data"]["token"]
    assert body["data"]["tokenHead"] == "Bearer "


@pytest.mark.parametrize("case", FAILURE_CASES, ids=lambda c: c["name"])
def test_login_failure(case, settings):
    """AUTH-02~05 失败矩阵：HTTP 200 + 业务码/message 与实测契约一致"""
    r = requests.post(f"{settings['base_url']}/admin/login",
                      json={"username": case["username"],
                            "password": case["password"]})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == case["code"]
    assert body["message"] == case["message"]
    assert body["data"] is None


@pytest.mark.parametrize("case", ILLEGAL_BODIES, ids=lambda c: c["name"])
def test_login_illegal_json(case, settings):
    """AUTH-06 非法 JSON：HTTP 400 + Spring 默认错误体（唯一非 200 的接口）"""
    r = requests.post(f"{settings['base_url']}/admin/login",
                      data=case["body"],
                      headers={"Content-Type": "application/json"})
    body = r.json()
    assert r.status_code == 400
    assert body["status"] == 400
    assert body["path"] == "/admin/login"
