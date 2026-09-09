"""资源管理用例：RES-01 ~ RES-05（分类/资源 CRUD 与角色资源分配）。"""
import requests

import common


def test_create_resource_category_syncs_db(admin_token, settings, db_connection):
    """RES-01 创建资源分类并验证落库（显式创建 + finally 清理）"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    name = common.unique_name("qa分类")

    try:
        r = requests.post(f"{settings['base_url']}/resourceCategory/create",
                          json={"name": name}, headers=headers)
        assert r.json()["code"] == 200

        cursor.execute("SELECT name FROM ums_resource_category WHERE name=%s", (name,))
        assert cursor.fetchone() is not None, "创建后 DB 查不到该分类"
    finally:
        cursor.execute("DELETE FROM ums_resource_category WHERE name=%s", (name,))


def test_create_resource_syncs_db(qa_resource, qa_category, settings, db_connection):
    """RES-02 创建测试资源：name/url/category_id 落库一致"""
    conn, cursor = db_connection
    cursor.execute("SELECT name, url, category_id FROM ums_resource WHERE id=%s",
                   (qa_resource["id"],))
    row = cursor.fetchone()
    assert row is not None
    assert row["name"] == qa_resource["name"]
    assert row["url"] == qa_resource["url"]
    assert row["category_id"] == qa_category["id"]


def test_update_resource_syncs_db(qa_resource, admin_token, settings, db_connection):
    """RES-03 更新资源：DB 同步"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/resource/update/{qa_resource['id']}",
                      json={"name": common.unique_name("qa资源改名"), "url": "/qa/updated"},
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["code"] == 200

    cursor.execute("SELECT url FROM ums_resource WHERE id=%s", (qa_resource["id"],))
    assert cursor.fetchone()["url"] == "/qa/updated"


def test_resource_list_combined_filter(qa_resource, qa_category, admin_token, settings):
    """RES-04 资源列表组合筛选：categoryId+name 过滤结果全部命中"""
    r = requests.get(
        f"{settings['base_url']}/resource/list"
        f"?categoryId={qa_category['id']}&name=qa&pageNum=1&pageSize=10",
        headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200
    assert body["data"]["total"] >= 1
    for item in body["data"]["list"]:
        assert item["categoryId"] == qa_category["id"]


def test_alloc_resource_to_role(qa_role, qa_resource, admin_token, settings, db_connection):
    """RES-05 给角色分配资源：关系表验证（roleId/resourceIds 是查询参数）"""
    conn, cursor = db_connection
    r = requests.post(f"{settings['base_url']}/role/allocResource"
                      f"?roleId={qa_role['id']}&resourceIds={qa_resource['id']}",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["code"] == 200

    cursor.execute("SELECT resource_id FROM ums_role_resource_relation WHERE role_id=%s",
                   (qa_role["id"],))
    rows = cursor.fetchall()
    assert [row["resource_id"] for row in rows] == [qa_resource["id"]]
