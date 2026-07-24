# syntax=docker/dockerfile:1

FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Use Astral's official image as the source for the uv and uvx binaries.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
