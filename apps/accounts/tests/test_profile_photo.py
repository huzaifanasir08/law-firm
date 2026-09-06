"""
Tests for PATCH /api/accounts/me/photo/
"""

import io

import pytest
from PIL import Image
from rest_framework import status

PHOTO_URL = "/api/accounts/me/photo/"


def _make_image_file(fmt="JPEG", size=(100, 100), color=(255, 0, 0)):
    """Return an in-memory image file-like object."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    buf.name = f"test.{fmt.lower()}"
    return buf


@pytest.mark.django_db
class TestProfilePhotoView:
    # ── Valid upload ──────────────────────────────────────────────────────────

    def test_upload_jpeg_returns_200(self, auth_client):
        img = _make_image_file("JPEG")
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": img}, format="multipart"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_upload_png_returns_200(self, auth_client):
        img = _make_image_file("PNG")
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": img}, format="multipart"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_upload_returns_user_profile_with_photo_url(self, auth_client):
        img = _make_image_file("JPEG")
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": img}, format="multipart"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("profile_photo") is not None

    def test_upload_photo_url_is_absolute(self, auth_client):
        img = _make_image_file("JPEG")
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": img}, format="multipart"
        )
        photo_url = response.data.get("profile_photo", "")
        assert photo_url.startswith("http")

    def test_upload_saves_photo_to_user(self, auth_client):
        img = _make_image_file("JPEG")
        auth_client.patch(PHOTO_URL, {"profile_photo": img}, format="multipart")
        user = auth_client._user
        user.refresh_from_db()
        assert bool(user.profile_photo)

    # ── File-size validation ──────────────────────────────────────────────────

    def test_upload_oversized_file_returns_400(self, auth_client):
        """Create a synthetic oversized payload (> 5 MB)."""
        large_data = io.BytesIO(b"x" * (6 * 1024 * 1024))
        large_data.name = "large.jpg"
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": large_data}, format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Invalid file type ─────────────────────────────────────────────────────

    def test_upload_text_file_returns_400(self, auth_client):
        fake = io.BytesIO(b"this is not an image at all")
        fake.name = "malicious.txt"
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": fake}, format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_pdf_disguised_as_jpg_returns_400(self, auth_client):
        # PDF header disguised with a .jpg name
        fake = io.BytesIO(b"%PDF-1.4 this is a pdf")
        fake.name = "photo.jpg"
        response = auth_client.patch(
            PHOTO_URL, {"profile_photo": fake}, format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Unauthenticated ───────────────────────────────────────────────────────

    def test_upload_unauthenticated_returns_401(self, api_client):
        img = _make_image_file("JPEG")
        response = api_client.patch(
            PHOTO_URL, {"profile_photo": img}, format="multipart"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
