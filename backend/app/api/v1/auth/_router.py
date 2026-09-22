"""Shared auth APIRouter instance."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
