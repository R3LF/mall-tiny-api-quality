# 本机环境说明（mall-tiny 接口测试）

更新日期：2026-08-31

## 一、已安装组件与位置

| 组件 | 版本 | 位置 | 状态 |
| --- | --- | --- | --- |
| JDK | 1.8.0_333 | `C:\Program Files\Java\jdk1.8.0_333` | 可用 |
| Maven | 3.8.6 | `F:\apache-maven-3.8.6` | 可用 |
| MySQL | 5.7.38 | `D:\mysql-5.7.38-winx64\...\bin\mysql.exe` | Windows 服务 `MySQL`，端口 3306，开机自启 |
| Redis | 5.0.14.1 (tporadowski) | `E:\dev\redis` | Windows 服务 `Redis`，端口 6379，开机自启 |
| Docker Desktop | 29.7.2 (engine) | 程序 `E:\dev\docker\app`，WSL 数据 `E:\dev\docker\wsl` | 已启动，docker-desktop WSL2 发行版 |
| Allure 命令行 | 2.46.0 | `E:\dev\allure\allure-2.46.0`，bin 已加入用户 PATH | 与 allure-pytest 插件配合生成 HTML 报告 |
| mall-tiny 源码 | 固定 commit `a81ec47` | `E:\projects\mall-tiny` | 已构建 `target\mall-tiny-1.0.0-SNAPSHOT.jar` |
| 测试虚拟环境 | Python 3.10.7 | 本仓库 `.venv` | 依赖已装齐，7 条环境自检通过 |

说明：Docker 安装时已通过安装参数把程序目录与 WSL 数据目录都放在 E 盘（`--installation-dir` / `--wsl-default-data-root`），不占用 C 盘。

## 二、被测系统配置

- 数据库：本机 MySQL `mall_tiny` 库，9 张 `ums_*` 表 + 种子数据；root 密码只写在 mall-tiny 的 `src/main/resources/application-dev.yml`（本机学习用，勿提交到公开仓库）。
- Redis：本机 6379，无密码，db 0。
- 应用端口：`http://localhost:8080`；Swagger UI：`http://localhost:8080/swagger-ui/`
- **管理员账号：`admin` / `Qa123456`**（种子 SQL 中 admin 原始密码未知，2026-08-31 通过注册接口生成的 BCrypt 哈希重置；仅本机测试环境使用）
- JWT：请求头 `Authorization: Bearer {token}`，有效期 7 天。

## 三、常用启动/停止命令（Git Bash）

```bash
# 启动被测应用（先确保 MySQL、Redis 服务在运行）
cd /e/projects/mall-tiny && java -jar target/mall-tiny-1.0.0-SNAPSHOT.jar > app.log 2>&1 &

# 应用日志
tail -f /e/projects/mall-tiny/app.log

# Redis 服务（服务名 Redis）
net start Redis   # 或 net stop Redis

# Docker
"/e/dev/docker/app/Docker Desktop.exe" &   # 启动 Docker Desktop
"/e/dev/docker/app/resources/bin/docker.exe" ps
```

## 四、已验证的关键链路（2026-08-31）

1. `POST /admin/login` 正确密码 → `code:200` + JWT。
2. `GET /admin/info` 带 Token → 返回 roles/menus/username。
3. 无 Token 访问 `/admin/list` → 业务码 401。
4. Redis 缓存键 `mall-tiny:ums:admin:admin`、`mall-tiny:ums:resourceList:{adminId}` 登录后自动生成，删除后再次登录会重建（CACHE-01/CACHE-02 行为已人工确认）。

## 五、7 天计划进度

- [x] Day 0：测试仓库、Python 环境、依赖、环境自检用例（`tests/test_environment.py`，7 passed）
- [x] Day 1 环境部分：MySQL/Redis/应用全部就绪，登录接口调通
- [x] Day 1~2 产出：AUTH-01~10、ADMIN-02/04/07 共 30 条用例全绿
- [x] YAML 分层改造（2026-09-04）：config/data 抽离，见下方第六节
- [x] MySQL 验证用例（2026-09-05）：AUTH-11/12、ADMIN 全部、ROLE-01~08、RES-01~05、MENU-01/02，共 55 条全绿；db_connection 开启 autocommit，新增 qa_user/qa_role/qa_category/qa_resource/qa_menus 数据夹具
- [ ] 待做：CACHE-01~04（Redis 缓存验证）、Docker Compose 交付物（Day 4）、GitHub Actions（Day 6）、Locust（Day 7）

## 六、测试仓库分层结构（2026-09-04 YAML 改造后）

```text
mall-tiny-api-quality/
  config/settings.yaml        配置层：环境 URL、账号（换环境只改这里）
  data/*.yaml                 数据层：登录失败矩阵、非法JSON、损坏token（改数据不动代码）
  tests/
    common.py                 公共工具：load_yaml()（路径锚定项目根，不依赖运行目录）
    conftest.py               夹具层：settings / admin_token（session 级，登录一次处处复用）
    test_login.py             登录：成功 + 失败矩阵 + 非法JSON
    test_info.py              用户信息：带Token/无Token/损坏Token/篡改Token
    test_list.py              用户列表：无Token + 分页结构
    test_getid.py             查询单用户（不存在ID）
    test_updatePassword.py    修改密码（错旧密码 + 原密码仍可登录）
    test_getrefresh.py        刷新Token
  reports/                    测试报告输出目录
```

分层规则：配置与数据进 YAML，场景与断言留在用例代码；用例间关联（Token 共享）用 conftest 的
fixture；断言同构的用例才做数据驱动，复杂断言（刷新闭环、将来的 DB 验证）留在代码里。
