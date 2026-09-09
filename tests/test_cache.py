"""缓存一致性用例：CACHE-02 / CACHE-03（CACHE-01 在 test_login.py，CACHE-04 暂缓）。

核心模式：登录生成缓存 → 业务操作触发失效 → 断言键被删 → 再登录重建 →
缓存内容 / DB / 最新业务值三方一致。

序列化结构（实测，GenericJackson2JsonRedisSerializer）：
  用户键   mall-tiny:ums:admin:{username}
           = ["类名字符串", {用户对象字典}]
  权限键   mall-tiny:ums:resourceList:{adminId}
           = ["java.util.ArrayList", [["类名字符串", {资源对象}], ...]]
  取业务数据时按这个嵌套结构下钻（CACHE-01 的 hgetall 教训）。

两个身份：qa_user 是"被观察的缓存主人"，admin_token 是"触发失效的操作者"。

实测契约：无角色（无资源）用户登录后 resourceList 键【不会生成】，
所以 CACHE-03 必须先给用户配上带资源的角色，再观察失效与重建。
"""
import json

import pytest
import requests

import common


def test_login_cache(settings,redis_connection,db_connection):
    """CACHE-01 测试管理员登录后，Redis 缓存是否正确生成"""
    con, cursor = db_connection
    username = settings["accounts"]["admin"]["username"]
    cursor.execute("SELECT id FROM ums_admin where username=%s",(username,))
    row = cursor.fetchone()
    assert row is not None, f"测试账号 {username} 不存在，请先在 DB 中准备"
    admin_id = row["id"]

    redis_connection.delete(f"mall-tiny:ums:admin:{username}",f"mall-tiny:ums:resourceList:{admin_id}")

    r = requests.post(f"{settings['base_url']}/admin/login",
                    json = settings["accounts"]["admin"])
    body = r.json()
    assert r.status_code == 200
    assert body["code"] == 200

    admin_key = f"mall-tiny:ums:admin:{username}"
    resource_key = f"mall-tiny:ums:resourceList:{admin_id}"

    assert  redis_connection.exists(admin_key) == 1, f"缓存键 {admin_key} 不存在"
    assert  redis_connection.exists(resource_key) == 1, f"缓存键 {resource_key} 不存在"
    # ---------- 4. TTL 检查（键的剩余存活秒数） ----------
    admin_ttl = redis_connection.ttl(admin_key)
    resource_ttl = redis_connection.ttl(resource_key)

    # 断言：TTL 应该 > 0（假设缓存过期时间为 3600 秒，刚创建时剩余时间应该接近 3600）
    assert 0 < admin_ttl <= 86400, f"{admin_key} 的 TTL 为 {admin_ttl}，应该大于 0"

    # ---------- 5. 取键值内容与 DB 对比 ----------
    # 5.1 检查 admin 缓存（String 存 JSON）
    admin_cache_raw = redis_connection.get(admin_key)
    assert admin_cache_raw is not None, f"{admin_key} 缓存数据为空"

    cache = json.loads(redis_connection.get(admin_key))[1]  # 值是 [类名, 对象] 数组
    cursor.execute("SELECT username, status FROM ums_admin WHERE id=%s", (admin_id,))
    db_row = cursor.fetchone()
    assert cache["username"] == db_row["username"] == username
    assert cache["status"] == db_row["status"] == 1

def test_update_user_evicts_and_rebuilds_cache(qa_user, admin_token, settings,
                                               db_connection, redis_connection):
    """CACHE-02 更新用户后：用户键失效 → 重建内容为最新值（缓存/DB/业务三方一致）"""
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    admin_key = f"mall-tiny:ums:admin:{qa_user['username']}"

    # 1. 前置：qa 用户登录一次，生成旧缓存（昵称为注册时的默认值）
    r = requests.post(f"{settings['base_url']}/admin/login",
                      json={"username": qa_user["username"],
                            "password": qa_user["password"]})
    assert r.json()["code"] == 200
    assert redis_connection.exists(admin_key) == 1, "前置：旧缓存未生成"

    # 2. 管理员更新昵称（源码：UmsAdminServiceImpl.update → delAdmin，删该用户的用户键）
    new_nick = common.unique_name("qa新昵称")
    r = requests.post(f"{settings['base_url']}/admin/update/{qa_user['id']}",
                      json={"nickName": new_nick}, headers=headers)
    assert r.json()["code"] == 200

    # 3. 断言精准失效：旧键被删；且不误删 admin 自己的用户键
    assert redis_connection.exists(admin_key) == 0, "更新后该用户的缓存键应被删除"
    assert redis_connection.exists("mall-tiny:ums:admin:admin") == 1, \
        "delAdmin 不应误删其他用户的缓存"

    # 4. 重建：qa 用户再次登录（缓存已删，本次从 DB 取最新值并回写）
    r = requests.post(f"{settings['base_url']}/admin/login",
                      json={"username": qa_user["username"],
                            "password": qa_user["password"]})
    assert r.json()["code"] == 200

    # 5. 三方一致：缓存内容 == DB 内容 == 最新业务值
    cache = json.loads(redis_connection.get(admin_key))[1]
    cursor.execute("SELECT nick_name FROM ums_admin WHERE id=%s", (qa_user["id"],))
    db_nick = cursor.fetchone()["nick_name"]
    assert cache["nickName"] == db_nick == new_nick


def test_alloc_role_evicts_and_rebuilds_resource_list(
        qa_user, qa_role, qa_resource, admin_token, settings,
        db_connection, redis_connection):
    """CACHE-03 分配角色后：权限键失效 → 重建内容包含新角色下的资源

    前置链路：资源分配给角色（/role/allocResource）→ 角色分配给用户
    （/admin/role/update）→ 用户登录即缓存"有资源的"权限列表；
    重复执行分配动作触发 delResourceList（源码已核实），
    重建后的权限列表应与 DB 关系表一致。
    """
    conn, cursor = db_connection
    headers = {"Authorization": f"Bearer {admin_token}"}
    resource_key = f"mall-tiny:ums:resourceList:{qa_user['id']}"

    # 0. 前置：把资源分配给角色（让"获得角色"这件事能改变权限内容）
    r = requests.post(f"{settings['base_url']}/role/allocResource"
                      f"?roleId={qa_role['id']}&resourceIds={qa_resource['id']}",
                      headers=headers)
    assert r.json()["code"] == 200

    # 把角色分配给用户
    alloc_url = (f"{settings['base_url']}/admin/role/update"
                 f"?adminId={qa_user['id']}&roleIds={qa_role['id']}")
    r = requests.post(alloc_url, headers=headers)
    assert r.json()["code"] == 200

    # 1. qa 用户登录：权限键生成，内容包含角色下的资源
    r = requests.post(f"{settings['base_url']}/admin/login",
                      json={"username": qa_user["username"],
                            "password": qa_user["password"]})
    assert r.json()["code"] == 200
    assert redis_connection.exists(resource_key) == 1, "前置：权限缓存未生成"
    resources = json.loads(redis_connection.get(resource_key))[1]
    assert qa_resource["id"] in [item[1]["id"] for item in resources], \
        "初始权限缓存应包含角色下的资源"

    # 2. 触发失效：重复执行分配动作（源码：updateRole → delResourceList，只清权限键）
    r = requests.post(alloc_url, headers=headers)
    assert r.json()["code"] == 200

    # 3. 断言精准失效：权限键被删；用户键未受影响
    assert redis_connection.exists(resource_key) == 0, "分配角色后权限缓存应被删除"
    assert redis_connection.exists(f"mall-tiny:ums:admin:{qa_user['username']}") == 1, \
        "delResourceList 不应误删用户键"

    # 4. 重建：qa 用户再次登录
    r = requests.post(f"{settings['base_url']}/admin/login",
                      json={"username": qa_user["username"],
                            "password": qa_user["password"]})
    assert r.json()["code"] == 200

    # 5. 内容断言：重建后的权限列表与 DB 关系表一致
    assert redis_connection.exists(resource_key) == 1, "重建后权限缓存应存在"
    resources = json.loads(redis_connection.get(resource_key))[1]
    cached_ids = [item[1]["id"] for item in resources]

    cursor.execute("SELECT resource_id FROM ums_role_resource_relation WHERE role_id=%s",
                   (qa_role["id"],))
    db_ids = [row["resource_id"] for row in cursor.fetchall()]
    assert sorted(cached_ids) == sorted(db_ids)
