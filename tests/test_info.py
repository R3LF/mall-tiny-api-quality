"""用户信息接口用例：AUTH-07 ~ AUTH-09。"""
import pytest
import requests

import common

CORRUPTED_TOKENS = common.load_yaml("data/corrupted_tokens.yaml")


def test_admin_info_with_token(admin_token, settings):
    """AUTH-09 带有效 Token 查询用户信息：roles/menus/username 契约"""
    r = requests.get(f"{settings['base_url']}/admin/info",
                     headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    assert "超级管理员" in body["data"]["roles"]
    assert "username" in body["data"]
    assert "menus" in body["data"]


def test_admin_info_without_token(settings):
    """AUTH-07 无 Token 访问受保护接口：业务层 401"""
    r = requests.get(f"{settings['base_url']}/admin/info")
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 401
    assert body["message"] == "暂未登录或token已经过期"
    assert body["data"] is None


@pytest.mark.parametrize("case", CORRUPTED_TOKENS, ids=lambda c: c["name"])
def test_admin_info_corrupted_token(case, settings):
    """AUTH-08 损坏 token（独立形态）：统一 401，不出现 500。

    数据来自 data/corrupted_tokens.yaml，本用例不依赖登录——
    健壮性验证不应与登录可用性绑定。
    """
    r = requests.get(f"{settings['base_url']}/admin/info",
                     headers={"Authorization": f"Bearer {case['token']}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 401
    assert body["message"] == "暂未登录或token已经过期"
    assert body["data"] is None


def test_admin_info_tampered_token(admin_token, settings):
    """AUTH-08 扩展：篡改 token 中部字符 → 签名校验拒绝。

    注意：不能篡改末位——Base64 每字符编码 6 位，签名末尾的填充位
    改了等于没改（实测返回 200），必须篡改中间字符才能破坏签名。
    这里使用 admin_token 是合理的（模拟攻击者截获后篡改）。
    """
    mid = len(admin_token) // 2
    replaced = "X" if admin_token[mid] != "X" else "Y"
    wrong_token = admin_token[:mid] + replaced + admin_token[mid + 1:]
    r = requests.get(f"{settings['base_url']}/admin/info",
                     headers={"Authorization": f"Bearer {wrong_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 401
