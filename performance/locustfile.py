"""Locust 性能测试：mall-tiny 核心接口基线（任务书第十节）。

场景与权重（模拟后台管理员的真实使用比例）：
  /admin/info      权重 5 —— 高频，观察权限缓存命中后的表现
  /admin/list      权重 2 —— 分页查询
  /role/list       权重 1
  /resource/list   权重 1
  重新登录         权重 1 —— 低频（登录链路较重，会写缓存）

负载阶梯（任务书）：
  基线 1 用户 2 分钟 → 轻负载 10 用户（spawn 2/s）5 分钟 → 目标 30 用户 10 分钟

运行：
  locust -f performance/locustfile.py --host http://localhost:8080
  无头模式（CI/命令行出报告）：
  locust -f performance/locustfile.py --host http://localhost:8080 \
         --headless -u 10 -r 2 -t 5m --html=reports/locust.html

记录指标：RPS、失败率、P50/P90/P95/P99；同时记录服务 CPU/内存与
MySQL 连接数、Redis 状态，不能把本地数字包装成生产容量结论。
"""
from locust import HttpUser, between, tag, task


class MallTinyAdmin(HttpUser):
    """模拟后台管理员：on_start 登录一次，之后混合访问查询接口。"""

    wait_time = between(1, 3)

    def on_start(self):
        """每个模拟用户启动时登录一次，Token 注入到会话级 headers。"""
        resp = self.client.post("/admin/login",
                                json={"username": "admin",
                                      "password": "Qa123456"})
        token = resp.json()["data"]["token"]
        self.client.headers["Authorization"] = f"Bearer {token}"

    @tag("高频")
    @task(5)
    def admin_info(self):
        """用户信息：JWT 鉴权 + 权限缓存命中路径"""
        self.client.get("/admin/info")

    @task(2)
    def admin_list(self):
        """用户分页列表：DB 分页查询"""
        self.client.get("/admin/list?pageNum=1&pageSize=10")

    @task(1)
    def role_list(self):
        """角色分页列表"""
        self.client.get("/role/list?pageNum=1&pageSize=10")

    @task(1)
    def resource_list(self):
        """资源分页列表"""
        self.client.get("/resource/list?pageNum=1&pageSize=10")

    @tag("低频")
    @task(1)
    def relogin(self):
        """重新登录：低频登录场景，刷新会话 Token"""
        resp = self.client.post("/admin/login",
                                json={"username": "admin",
                                      "password": "Qa123456"})
        token = resp.json()["data"]["token"]
        self.client.headers["Authorization"] = f"Bearer {token}"
