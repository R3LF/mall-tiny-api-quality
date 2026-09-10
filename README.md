# mall-tiny-api-quality

![api-test](https://github.com/R3LF/mall-tiny-api-quality/actions/workflows/api-test.yml/badge.svg)

基于 **pytest + requests** 的接口自动化测试项目，被测系统为 [mall-tiny](https://github.com/macrozheng/mall-tiny)（权限管理系统，测试基线固定于 commit `a81ec47`）。

## 覆盖能力

- **58 个测试点**：任务书 40 条用例覆盖 39 条（CACHE-04 Redis 停机降级为探索型用例，暂缓）
- 正常 / 异常 / 边界 / 参数校验 / 权限（401/403）全维度
- **MySQL 落库验证**：注册/更新/禁用/删除后的数据一致性
- **Redis 缓存一致性**：缓存生成、精准失效、重建后内容核对
- **Docker Compose 一键重建**被测三件套环境（MySQL + Redis + 应用）
- **GitHub Actions 持续集成**：push 自动执行并归档 JUnit / Allure 报告
- Locust 性能基线脚本

## 分层架构

```text
config/settings.yaml   配置层：环境 URL、账号、DB/Redis 连接（gitignore，含密码不入仓库）
data/*.yaml            数据层：登录失败矩阵、非法JSON、损坏token 等数据驱动用例
tests/common.py        工具层：YAML 读取（路径锚定项目根）、唯一测试数据命名
tests/conftest.py      夹具层：settings / admin_token / db_connection / redis_connection
                       + qa_user / qa_role / qa_category / qa_resource / qa_menus
                       （function 级造数据夹具，yield 后自动清理，先关系表后主体表）
tests/test_*.py        用例层：场景与断言，HTTP 层 + 业务码 + 数据层三方校验
performance/           Locust 性能脚本
docker-compose.yml     被测环境编排：健康检查 + 初始化 SQL + 测试账号密码重置
.github/workflows/     CI 工作流
```

设计原则：配置与数据进 YAML，场景与断言留在用例；用例间关联（Token 共享、多身份）用 fixture；
断言同构的用例做数据驱动；清理操作全部幂等（按唯一键 DELETE），保证用例可重复运行。

## 快速开始

### 方式一：本机直跑（需要本机 MySQL 5.7 + Redis + JDK8/Maven 构建 jar）

```bash
pip install -e .
pytest tests/ -v
```

### 方式二：Docker Compose（被测环境全容器化）

```bash
mvn -f mall-tiny/pom.xml -DskipTests package   # 构建被测应用 jar
export MALL_TINY_SOURCE=/path/to/mall-tiny      # 指向被测源码目录
export MYSQL_ROOT_PASSWORD=123123               # 与 config/settings.yaml 保持一致
docker compose up -d --build                    # 三件套 + 健康检查 + 自动初始化
pytest tests/ -v                                # 全部用例打在容器化环境上
docker compose down -v                          # 清理（-v 会删除数据卷）
```

初始化说明：MySQL 首次启动自动执行 `docker/mysql-init/01_schema.sql`（mall_tiny 建表 + 种子数据，
冻结自被测源码固定 commit）与 `02_test_password.sql`（将 admin 密码重置为 Qa123456 供自动化登录）。

### 持续集成

push 到 main 自动触发（`.github/workflows/api-test.yml`）：
检出两个仓库 → Maven 构建 jar → 构建应用镜像 → Compose 起环境 → 等待健康探测 →
运行全部用例 → 归档 JUnit 与 Allure 报告（失败同样归档）。任意用例失败即 Job 失败（质量门禁）。

### 性能测试

```bash
locust -f performance/locustfile.py --host http://localhost:8080
```

负载阶梯与记录指标见 `performance/locustfile.py` 文件头说明。

## 缺陷与改进发现（探索过程产出）

| # | 发现 | 证据 |
| --- | --- | --- |
| 1 | 更新用户状态接口对不存在的 id 返回 HTTP 500 | 实测 `POST /admin/updateStatus/197609` |
| 2 | `/admin/role/update` 对不存在的 adminId 静默成功并写入孤儿关系行 | 实测返回 code 200 且关系表出现记录 |
| 3 | delete 与 updateStatus 对不存在资源的错误处理不一致（业务码 500 vs HTTP 500） | 同上对比 |
| 4 | 用户列表与注册接口响应泄露 BCrypt 密码哈希 | `GET /admin/list` 响应含 password 字段 |
| 5 | 登录失败提示可枚举用户名：密码错提示"密码不正确"暴露账号存在，与"用户名或密码错误"策略不一致 | 实测对比 |
| 6 | 容器化部署时校验消息随 locale 退化为英文、init SQL 无字符集声明导致中文乱码 | Docker 化过程中实测并修复 |

详见 `docs/缺陷报告.md`。

## 环境说明

被测环境完整参数与历史排障记录见 `ENVIRONMENT.md`；测试策略与风险清单见 `docs/`。
