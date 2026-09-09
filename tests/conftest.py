"""pytest 夹具（fixture）集中管理文件。

fixture 的两条规则：
1. 测试函数的参数要么被 @pytest.mark.parametrize 注入，要么是这里的同名夹具；
2. scope 决定复用范围：session = 整个测试会话只执行一次，function = 每条用例独立。

数据类夹具（qa_user / qa_role / qa_category / qa_resource / qa_menus）统一遵循：
yield 之前是"前置造数据"，yield 交出数据，yield 之后是"后置清理"——
即使用例断言失败，清理也保证执行，这是用例可重复运行的根基。
"""
import pytest
import pymysql
import requests
import redis
import common


@pytest.fixture(scope="session")
def settings():
    """配置层：环境 URL、账号、数据库连接，来自 config/settings.yaml。

    换环境（如指向测试服）只改那个文件，所有用例自动生效。
    """
    return common.load_yaml("config/settings.yaml")


@pytest.fixture(scope="session")
def admin_token(settings):
    """会话级登录 Token：整个测试会话只登录一次。

    需要鉴权的用例只要在参数里声明 admin_token 即可拿到，
    这就是 pytest 里"用例间关联"的官方机制（登录一次、处处复用）。
    """
    acc = settings["accounts"]["admin"]
    r = requests.post(f"{settings['base_url']}/admin/login", json=acc)
    assert r.json()["code"] == 200, f"登录失败，请检查被测应用是否在运行：{r.text}"
    return r.json()["data"]["token"]


@pytest.fixture(scope="session")
def db_connection(settings):
    """会话级数据库连接（DictCursor：查询结果按列名取值）。

    autocommit=True：用例里的清理 DELETE 即时生效，无需手动 commit；
    被测应用写入的数据由应用自己的事务提交，与本连接无关。
    """
    conn = pymysql.connect(**settings["database"], autocommit=True)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    yield conn, cursor
    cursor.close()
    conn.close()

@pytest.fixture(scope="session")
def redis_connection(settings):
    """Redis连接
    """
    pool = redis.ConnectionPool(**settings['redis'],max_connections=10, protocol=2)
    client = redis.Redis(connection_pool=pool)
    yield client
    client.close()


# ============================================================
# 数据类夹具：前置造数据 + 后置清理（先关系表，后主体表）
# ============================================================

@pytest.fixture(scope="function")
def qa_user(settings, admin_token, db_connection, redis_connection):
    """注册一个 qa_ 测试用户，用例结束自动删除。

    teardown 先清 ums_admin_role_relation（防孤儿关系数据），
    再调删除接口删除用户本体，最后清该用户的两把 Redis 缓存键
    （防指向已删除用户的孤儿缓存残留 24 小时）。
    """
    conn, cursor = db_connection
    username = common.unique_name("qa_user")
    password = "Qa123456"
    r = requests.post(f"{settings['base_url']}/admin/register", json={
        "username": username,
        "password": password,
        "email": f"{username}@test.local",
        "nickName": "qa自动化用户",
    })
    assert r.json()["code"] == 200, f"前置：注册 qa 用户失败：{r.text}"
    cursor.execute("SELECT id FROM ums_admin WHERE username=%s", (username,))
    uid = cursor.fetchone()["id"]

    yield {"id": uid, "username": username, "password": password}

    cursor.execute("DELETE FROM ums_admin_role_relation WHERE admin_id=%s", (uid,))
    requests.post(f"{settings['base_url']}/admin/delete/{uid}",
                  headers={"Authorization": f"Bearer {admin_token}"})
    redis_connection.delete(f"mall-tiny:ums:admin:{username}",
                            f"mall-tiny:ums:resourceList:{uid}")


@pytest.fixture(scope="function")
def qa_role(settings, admin_token, db_connection):
    """创建一个 qa_ 测试角色，用例结束自动清理（先清关系表再删角色）。"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    name = common.unique_name("qa_role")
    r = requests.post(f"{settings['base_url']}/role/create",
                      json={"name": name, "description": "qa自动化测试角色"},
                      headers=headers)
    assert r.json()["code"] == 200, f"前置：创建 qa 角色失败：{r.text}"
    cursor.execute("SELECT id FROM ums_role WHERE name=%s", (name,))
    rid = cursor.fetchone()["id"]

    yield {"id": rid, "name": name}

    cursor.execute("DELETE FROM ums_role_menu_relation WHERE role_id=%s", (rid,))
    cursor.execute("DELETE FROM ums_role_resource_relation WHERE role_id=%s", (rid,))
    requests.post(f"{settings['base_url']}/role/delete?ids={rid}", headers=headers)


@pytest.fixture(scope="function")
def qa_category(settings, admin_token, db_connection):
    """创建一个 qa_ 资源分类，用例结束自动删除。"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    name = common.unique_name("qa分类")
    r = requests.post(f"{settings['base_url']}/resourceCategory/create",
                      json={"name": name}, headers=headers)
    assert r.json()["code"] == 200, f"前置：创建资源分类失败：{r.text}"
    cursor.execute("SELECT id FROM ums_resource_category WHERE name=%s", (name,))
    cid = cursor.fetchone()["id"]

    yield {"id": cid, "name": name}

    requests.post(f"{settings['base_url']}/resourceCategory/delete/{cid}",
                  headers=headers)


@pytest.fixture(scope="function")
def qa_resource(settings, admin_token, db_connection, qa_category):
    """在 qa_ 分类下创建一个 qa_ 测试资源，用例结束自动删除。"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    name = common.unique_name("qa资源")
    url = f"/qa/{name}"
    r = requests.post(f"{settings['base_url']}/resource/create",
                      json={"name": name, "url": url, "categoryId": qa_category["id"]},
                      headers=headers)
    assert r.json()["code"] == 200, f"前置：创建资源失败：{r.text}"
    cursor.execute("SELECT id FROM ums_resource WHERE name=%s", (name,))
    resid = cursor.fetchone()["id"]

    yield {"id": resid, "name": name, "url": url, "category_id": qa_category["id"]}

    requests.post(f"{settings['base_url']}/resource/delete/{resid}", headers=headers)


@pytest.fixture(scope="function")
def qa_menus(settings, admin_token, db_connection):
    """创建 qa_ 父子菜单（服务端按 parentId 自动算 level：父 0 子 1），
    用例结束先删子再删父。
    """
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}

    pname = common.unique_name("qaParent")
    r = requests.post(f"{settings['base_url']}/menu/create",
                      json={"title": pname, "name": pname, "parentId": 0,
                            "icon": "qa", "hidden": 0, "sort": 5},
                      headers=headers)
    assert r.json()["code"] == 200, f"前置：创建父菜单失败：{r.text}"
    cursor.execute("SELECT id, level FROM ums_menu WHERE name=%s", (pname,))
    parent = cursor.fetchone()

    cname = common.unique_name("qaChild")
    r = requests.post(f"{settings['base_url']}/menu/create",
                      json={"title": cname, "name": cname, "parentId": parent["id"],
                            "icon": "qa", "hidden": 0, "sort": 2},
                      headers=headers)
    assert r.json()["code"] == 200, f"前置：创建子菜单失败：{r.text}"
    cursor.execute("SELECT id, level, parent_id FROM ums_menu WHERE name=%s", (cname,))
    child = cursor.fetchone()

    yield {"parent": {"id": parent["id"], "name": pname, "level": parent["level"]},
           "child": {"id": child["id"], "name": cname, "level": child["level"],
                     "parent_id": child["parent_id"]}}

    requests.post(f"{settings['base_url']}/menu/delete/{child['id']}", headers=headers)
    requests.post(f"{settings['base_url']}/menu/delete/{parent['id']}", headers=headers)
