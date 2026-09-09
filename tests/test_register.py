"""注册接口用例：AUTH-12 注册闭环、AUTH-12B 参数校验、ADMIN-01 重复注册。

AUTH-12 是"API 写入 → DB 验证 → 清理"的最小闭环参考实现：
唯一数据（unique_name）+ try/finally 清理 + DB 层断言。
"""
import time

import pytest
import requests

import common

REGISTER_CASES = common.load_yaml("data/register_cases.yaml")


@pytest.mark.parametrize("case", REGISTER_CASES, ids=lambda c: c["username"])
def test_register_success(case, settings, db_connection):
    """AUTH-12 注册新用户并验证落库：哈希非明文、用例可重复运行"""
    conn, cursor = db_connection
    username = f"{case['username']}_{int(time.time())}"   # 唯一数据：二次运行不撞名

    try:
        r = requests.post(f"{settings['base_url']}/admin/register", json={
            "email": case["email"],
            "icon": case["icon"],
            "nickName": case["nickName"],
            "note": case["note"],
            "password": case["password"],
            "username": username,
        })
        body = r.json()
        assert r.status_code == 200
        assert body["code"] == 200

        cursor.execute(
            "SELECT id, username, password, status FROM ums_admin WHERE username=%s",
            (username,))
        row = cursor.fetchone()
        assert row is not None, "注册后 DB 查不到该用户"
        assert row["username"] == username
        assert row["status"] == 1
        assert row["password"].startswith("$2a$"), "密码必须以哈希存储而非明文"
    finally:
        # 清理：try/finally 保证断言失败也执行
        # （conftest 已开启 autocommit=True，这里的 DELETE 即时生效）
        cursor.execute("DELETE FROM ums_admin WHERE username=%s", (username,))


@pytest.mark.parametrize("field", ["username", "password"])
def test_register_empty_field(field, settings):
    """AUTH-12B 注册参数校验：空字段 → code 404（与登录同套校验，HTTP 200）"""
    payload = {"username": "qa_x", "password": "Qa123456"}
    payload[field] = ""
    r = requests.post(f"{settings['base_url']}/admin/register", json=payload)
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 404
    assert body["message"] == f"{field}不能为空"


def test_register_duplicate_username(settings, db_connection):
    """ADMIN-01 重复用户名注册被拒：code 500（实测"操作失败"）且库中记录数不变"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/admin/register",
                      json={"username": "admin", "password": "Abc12345"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 500

    cursor.execute("SELECT COUNT(*) AS cnt FROM ums_admin WHERE username=%s", ("admin",))
    assert cursor.fetchone()["cnt"] == 1
