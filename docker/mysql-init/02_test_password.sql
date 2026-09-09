-- 测试环境初始化（第二步）：将 admin 密码重置为 Qa123456
-- 哈希来自注册接口对 Qa123456 的 BCrypt 编码结果，
-- 使自动化用例（settings.yaml 中 admin/Qa123456）可直接登录
UPDATE `ums_admin` SET password = '$2a$10$sDy/XFB0D/2trdE5GLUYUOqqrQ9dJDM0R4lROzHTtOxlk8w5UJJHO' WHERE username = 'admin';
