"""用户管理 DB 验证用例：AUTH-11、ADMIN-03、ADMIN-05、ADMIN-06、ADMIN-08、ADMIN-09。

这些用例共享 qa_user 夹具（每条用例独立注册一个测试用户，结束自动删除），
因此互相之间零依赖、任意单独运行。
"""
import requests


def test_disabled_user_cannot_login(qa_user, admin_token, settings, db_connection):
    """AUTH-11 禁用用户后登录被拒（实测契约：code 500「帐号已被禁用」）"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = requests.post(f"{settings['base_url']}/admin/updateStatus/{qa_user['id']}?status=0",
                      headers=headers)
    assert r.json()["code"] == 200

    cursor.execute("SELECT status FROM ums_admin WHERE id=%s", (qa_user["id"],))
    assert cursor.fetchone()["status"] == 0

    r2 = requests.post(f"{settings['base_url']}/admin/login",
                       json={"username": qa_user["username"],
                             "password": qa_user["password"]})
    body = r2.json()
    assert body["code"] == 500
    assert body["message"] == "帐号已被禁用"


def test_admin_list_keyword_filter(admin_token, settings, db_connection):
    """ADMIN-03 用户名关键字模糊查询：响应与 DB 交叉核对 total 一致"""
    conn, cursor = db_connection
    r = requests.get(f"{settings['base_url']}/admin/list?keyword=admin&pageNum=1&pageSize=10",
                     headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    for item in body["data"]["list"]:
        # 实测契约：MySQL utf8_general_ci 排序规则下 LIKE 不区分大小写
        # （keyword=admin 能命中 productAdmin），断言必须与该行为一致
        assert "admin" in item["username"].lower()

    cursor.execute("SELECT COUNT(*) AS cnt FROM ums_admin WHERE username LIKE %s",
                   ("%admin%",))
    assert body["data"]["total"] == cursor.fetchone()["cnt"]


def test_update_user_profile_syncs_db(qa_user, admin_token, settings, db_connection):
    """ADMIN-05 更新昵称与邮箱：API 成功且 DB 字段同步"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    new_email = f"{qa_user['username']}@update.local"

    r = requests.post(f"{settings['base_url']}/admin/update/{qa_user['id']}",
                      json={"nickName": "qa测试昵称", "email": new_email},
                      headers=headers)
    assert r.json()["code"] == 200

    cursor.execute("SELECT nick_name, email FROM ums_admin WHERE id=%s", (qa_user["id"],))
    row = cursor.fetchone()
    assert row["nick_name"] == "qa测试昵称"
    assert row["email"] == new_email


def test_update_status_reversible(qa_user, admin_token, settings, db_connection):
    """ADMIN-06 更新用户状态：DB 与每次请求一致（0→1 可逆）"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}

    for status in (0, 1):
        r = requests.post(f"{settings['base_url']}/admin/updateStatus/{qa_user['id']}?status={status}",
                          headers=headers)
        assert r.json()["code"] == 200
        cursor.execute("SELECT status FROM ums_admin WHERE id=%s", (qa_user["id"],))
        assert cursor.fetchone()["status"] == status


def test_change_password_success(qa_user, admin_token, settings, db_connection):
    """ADMIN-08 正确修改密码：旧密码失效、新密码可用、DB 哈希更新且非明文"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}

    cursor.execute("SELECT password FROM ums_admin WHERE id=%s", (qa_user["id"],))
    old_hash = cursor.fetchone()["password"]

    r = requests.post(f"{settings['base_url']}/admin/updatePassword",
                      json={"username": qa_user["username"],
                            "oldPassword": qa_user["password"],
                            "newPassword": "New123456"},
                      headers=headers)
    assert r.json()["code"] == 200

    r_old = requests.post(f"{settings['base_url']}/admin/login",
                          json={"username": qa_user["username"],
                                "password": qa_user["password"]})
    assert r_old.json()["code"] != 200, "旧密码应该已失效"

    r_new = requests.post(f"{settings['base_url']}/admin/login",
                          json={"username": qa_user["username"],
                                "password": "New123456"})
    assert r_new.json()["code"] == 200, "新密码应该可以登录"

    cursor.execute("SELECT password FROM ums_admin WHERE id=%s", (qa_user["id"],))
    new_hash = cursor.fetchone()["password"]
    assert new_hash != old_hash
    assert new_hash.startswith("$2a$")


def test_delete_user_removes_record(qa_user, admin_token, settings, db_connection):
    """ADMIN-09 删除测试用户：DB 记录消失"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/admin/delete/{qa_user['id']}",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["code"] == 200

    cursor.execute("SELECT COUNT(*) AS cnt FROM ums_admin WHERE id=%s", (qa_user["id"],))
    assert cursor.fetchone()["cnt"] == 0
    # qa_user 夹具的 teardown 会再删一次，对已删除 id 返回业务 500 但不作断言，无害
