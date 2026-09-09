# mall-tiny 应用镜像（测试环境专用）
# 与被测源码仓库自带的 Dockerfile 等价，但基础镜像换为维护中的
# eclipse-temurin:8-jre（官方 openjdk:8 已弃更，部分镜像源拒绝提供）。
# 构建上下文 = mall-tiny 源码目录（需先 mvn -DskipTests package 出 jar）：
#   docker build -f docker/app.Dockerfile -t mall-tiny:test ${MALL_TINY_SOURCE}
FROM eclipse-temurin:8-jre
WORKDIR /app
COPY target/mall-tiny-1.0.0-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
