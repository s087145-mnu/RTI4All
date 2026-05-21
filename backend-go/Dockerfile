# Multi-stage build: compile in a Go image, ship a tiny scratch-ish runtime.
FROM golang:1.22-alpine AS build

WORKDIR /src

# Cache the module download layer.
COPY go.mod go.sum ./
RUN go mod download

# Build the static binary.
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/rti4all ./

# Final image — Alpine for ca-certificates (Anthropic HTTPS) and a shell.
FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata && \
    adduser -D -u 10001 rti4all

WORKDIR /app
COPY --from=build /out/rti4all /app/rti4all
COPY data /app/data

# Ensure the non-root user owns the data dir so it can create backups.
RUN mkdir -p /app/data/backups && chown -R rti4all:rti4all /app

USER rti4all
EXPOSE 8000

ENV PORT=8000
CMD ["/app/rti4all"]
