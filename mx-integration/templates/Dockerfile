FROM artifactory.moodys.com/docker/eclipse-temurin:21-jre-alpine

ARG BINARY_NAME

RUN addgroup -g 999 rmsuser && adduser -u 999 -G rmsuser -s /bin/sh -D rmsuser

WORKDIR /app

COPY {{vendor}}-${BINARY_NAME}/target/*.jar /app/app.jar

RUN chown -R rmsuser:rmsuser /app

USER rmsuser

EXPOSE 3000

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
