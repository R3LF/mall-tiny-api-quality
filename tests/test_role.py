"""角色管理用例：ROLE-01 ~ ROLE-08（创建/更新/查询/状态/分配/删除）。

ROLE-01 显式创建（try/finally 清理，与注册用例同模式）；
其余用例使用 qa_role 夹具。ROLE-05~07 验证 ums_admin_role_relation 关系表，
注意 /admin/role/update 的 adminId 与 roleIds 是查询参数而非 JSON body。
"""
import pytest
import requests

import common


def test_create_role_syncs_db(admin_token, settings, db_connection):
    """ROLE-01 创建角色并验证落库"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    name = common.unique_name("qa_role")

    try:
        r = requests.post(f"{settings['base_url']}/role/create",
                          json={"name": name, "description": "ROLE-01 测试角色"},
                          headers=headers)
        assert r.json()["code"] == 200

        cursor.execute("SELECT name, description FROM ums_role WHERE name=%s", (name,))
        row = cursor.fetchone()
        assert row is not None, "创建后 DB 查不到该角色"
        assert row["description"] == "ROLE-01 测试角色"
    finally:
        cursor.execute("DELETE FROM ums_role WHERE name=%s", (name,))


def test_update_role_syncs_db(qa_role, admin_token, settings, db_connection):
    """ROLE-02 更新角色描述：DB 同步"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/role/update/{qa_role['id']}",
                      json={"name": qa_role["name"], "description": "更新后的描述"},
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["code"] == 200

    cursor.execute("SELECT description FROM ums_role WHERE id=%s", (qa_role["id"],))
    assert cursor.fetchone()["description"] == "更新后的描述"


def test_role_list_keyword_filter(qa_role, admin_token, settings):
    """ROLE-03 角色分页与关键字查询：结果全部命中关键字"""
    r = requests.get(
        f"{settings['base_url']}/role/list?keyword={qa_role['name']}&pageNum=1&pageSize=10",
        headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    assert body["data"]["total"] >= 1
    for item in body["data"]["list"]:
        assert qa_role["name"] in item["name"]


def test_role_status_reversible(qa_role, admin_token, settings, db_connection):
    """ROLE-04 启用/禁用角色：DB status 与每次请求一致"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    for status in (0, 1):
        r = requests.post(
            f"{settings['base_url']}/role/updateStatus/{qa_role['id']}?status={status}",
            headers=headers)
        assert r.json()["code"] == 200
        cursor.execute("SELECT status FROM ums_role WHERE id=%s", (qa_role["id"],))
        assert cursor.fetchone()["status"] == status


def test_alloc_single_role_to_user(qa_user, qa_role, admin_token, settings, db_connection):
    """ROLE-05 给用户分配单个角色：关系表出现 admin_id↔role_id 记录"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/admin/role/update"
                      f"?adminId={qa_user['id']}&roleIds={qa_role['id']}",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["code"] == 200

    cursor.execute("SELECT role_id FROM ums_admin_role_relation WHERE admin_id=%s",
                   (qa_user["id"],))
    rows = cursor.fetchall()
    assert [row["role_id"] for row in rows] == [qa_role["id"]]


def test_alloc_multiple_roles_no_duplicates(qa_user, qa_role, admin_token,
                                            settings, db_connection):
    """ROLE-06 分配多个角色：关系表两条，重复提交不产生重复记录"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 第二个 qa_ 角色（用完即删，关系数据由 qa_user 夹具的 teardown 兜底清理）
    name2 = common.unique_name("qa_role")
    r0 = requests.post(f"{settings['base_url']}/role/create",
                       json={"name": name2, "description": "ROLE-06 第二角色"},
                       headers=headers)
    assert r0.json()["code"] == 200
    cursor.execute("SELECT id FROM ums_role WHERE name=%s", (name2,))
    rid2 = cursor.fetchone()["id"]

    try:
        url = (f"{settings['base_url']}/admin/role/update"
               f"?adminId={qa_user['id']}&roleIds={qa_role['id']},{rid2}")
        r = requests.post(url, headers=headers)
        assert r.json()["code"] == 200
        cursor.execute("SELECT role_id FROM ums_admin_role_relation WHERE admin_id=%s",
                       (qa_user["id"],))
        ids = sorted(row["role_id"] for row in cursor.fetchall())
        assert ids == sorted([qa_role["id"], rid2])

        requests.post(url, headers=headers)   # 重复提交
        cursor.execute("SELECT role_id FROM ums_admin_role_relation WHERE admin_id=%s",
                       (qa_user["id"],))
        ids = sorted(row["role_id"] for row in cursor.fetchall())
        assert ids == sorted([qa_role["id"], rid2]), "重复提交不应产生重复关系记录"
    finally:
        cursor.execute("DELETE FROM ums_role WHERE id=%s", (rid2,))


def test_clear_user_roles(qa_user, qa_role, admin_token, settings, db_connection):
    """ROLE-07 清空用户角色：roleIds= 空值传参（实测可行，返回 code 200）"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    alloc_url = (f"{settings['base_url']}/admin/role/update"
                 f"?adminId={qa_user['id']}&roleIds={qa_role['id']}")

    requests.post(alloc_url, headers=headers)
    cursor.execute("SELECT COUNT(*) AS cnt FROM ums_admin_role_relation WHERE admin_id=%s",
                   (qa_user["id"],))
    assert cursor.fetchone()["cnt"] == 1, "前置：分配角色失败"

    r = requests.post(f"{settings['base_url']}/admin/role/update"
                      f"?adminId={qa_user['id']}&roleIds=",
                      headers=headers)
    assert r.json()["code"] == 200

    cursor.execute("SELECT COUNT(*) AS cnt FROM ums_admin_role_relation WHERE admin_id=%s",
                   (qa_user["id"],))
    assert cursor.fetchone()["cnt"] == 0, "清空后关系表应无该用户记录"


def test_delete_role(qa_role, admin_token, settings, db_connection):
    """ROLE-08 删除测试角色：DB 无记录"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/role/delete?ids={qa_role['id']}",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["code"] == 200

    cursor.execute("SELECT COUNT(*) AS cnt FROM ums_role WHERE id=%s", (qa_role["id"],))
    assert cursor.fetchone()["cnt"] == 0
