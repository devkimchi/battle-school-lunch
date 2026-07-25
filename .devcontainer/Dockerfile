# syntax=docker/dockerfile:1

FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# The base image's Yarn APT source can carry an expired key and break later
# Dev Container Features. This project uses npm, so remove the unused source.
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Use Astral's official image as the source for the uv and uvx binaries.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
