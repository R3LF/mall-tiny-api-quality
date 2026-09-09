"""菜单管理用例：MENU-01/02。

服务端按 parentId 自动计算 level（父 0 子 1，见 UmsMenuServiceImpl.updateLevel），
因此用例直接断言 DB 中的 parent_id/level/sort 而不是请求参数。
"""
import requests


def test_create_parent_child_menus(qa_menus, db_connection):
    """MENU-01 创建父菜单和子菜单：parent_id/level/sort 正确"""
    conn, cursor = db_connection

    cursor.execute("SELECT parent_id, level, sort FROM ums_menu WHERE id=%s",
                   (qa_menus["parent"]["id"],))
    parent = cursor.fetchone()
    assert parent["parent_id"] == 0
    assert parent["level"] == 0
    assert parent["sort"] == 5

    cursor.execute("SELECT parent_id, level, sort FROM ums_menu WHERE id=%s",
                   (qa_menus["child"]["id"],))
    child = cursor.fetchone()
    assert child["parent_id"] == qa_menus["parent"]["id"]
    assert child["level"] == 1
    assert child["sort"] == 2


def test_menu_tree_and_hidden(qa_menus, admin_token, settings, db_connection):
    """MENU-02 菜单树层级正确 + hidden 切换落库"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = requests.get(f"{settings['base_url']}/menu/treeList", headers=headers)
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200

    parent_node = next((n for n in body["data"] if n["id"] == qa_menus["parent"]["id"]),
                       None)
    assert parent_node is not None, "树中找不到 qa 父菜单"
    child_ids = {c["id"] for c in parent_node.get("children", [])}
    assert qa_menus["child"]["id"] in child_ids, "子菜单应挂在父节点的 children 下"

    r2 = requests.post(
        f"{settings['base_url']}/menu/updateHidden/{qa_menus['child']['id']}?hidden=1",
        headers=headers)
    assert r2.json()["code"] == 200
    cursor.execute("SELECT hidden FROM ums_menu WHERE id=%s", (qa_menus["child"]["id"],))
    assert cursor.fetchone()["hidden"] == 1
