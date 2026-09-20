"""
Tests for Firm type (INDIVIDUAL vs MULTI) functionality and permissions.
"""

import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


from apps.accounts.models import User, UserRole
from apps.firm.models import Firm, FirmType
from apps.lawyer.models import Client
from apps.matters.models import Matter, MatterStatus


def get_auth_client(user: User) -> APIClient:
    """Helper to return an authenticated API client for a given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client._user = user
    return client


@pytest.fixture
def individual_firm(db):
    return Firm.objects.create(name="Solo Law Practice", type=FirmType.INDIVIDUAL, email="solo@law.com")


@pytest.fixture
def multi_firm(db):
    return Firm.objects.create(name="Apex Law Partners", type=FirmType.MULTI, email="contact@apexlaw.com")


@pytest.fixture
def individual_firm_admin(make_user, individual_firm):
    admin = make_user(email="solo_admin@law.com", name="Solo Admin", role=UserRole.FIRM_ADMIN)
    admin.firm = individual_firm
    admin.save(update_fields=["firm"])
    return admin


@pytest.fixture
def multi_firm_admin(make_user, multi_firm):
    admin = make_user(email="multi_admin@apexlaw.com", name="Multi Admin", role=UserRole.FIRM_ADMIN)
    admin.firm = multi_firm
    admin.save(update_fields=["firm"])
    return admin


@pytest.fixture
def multi_firm_lawyer(make_user, multi_firm):
    lawyer = make_user(email="lawyer@apexlaw.com", name="Firm Lawyer", role=UserRole.LAWYER)
    lawyer.firm = multi_firm
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.mark.django_db
class TestFirmAdminCreationAndUpdate:
    """Tests for creating and updating firms with type."""

    def test_super_admin_create_firm_with_type(self, super_admin):
        client = get_auth_client(super_admin)
        payload = {
            "name": "Beacon Law Practice",
            "type": "INDIVIDUAL",
            "email": "beacon@law.com",
            "phone": "+1234567890",
        }
        response = client.post("/api/admin/firms/", payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "INDIVIDUAL"
        assert response.data["name"] == "Beacon Law Practice"
        assert response.data["admin_user"] is not None
        assert response.data["admin_user"]["email"] == "beacon@law.com"
        assert response.data["admin_user"]["role"] == UserRole.FIRM_ADMIN

        # Verify initial Firm Admin user was created in DB
        created_admin = User.objects.get(email="beacon@law.com")
        assert created_admin.role == UserRole.FIRM_ADMIN
        assert created_admin.firm.name == "Beacon Law Practice"
        assert created_admin.is_active is True
        assert created_admin.has_usable_password()

        # Verify welcome email was sent with credentials
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.to == ["beacon@law.com"]
        assert "Welcome to Beacon Law Practice" in sent_email.subject
        assert "Temporary Password:" in sent_email.body

    def test_super_admin_create_firm_with_custom_admin(self, super_admin):
        client = get_auth_client(super_admin)
        payload = {
            "name": "Apex Custom Practice",
            "type": "MULTI",
            "email": "info@apexcustom.com",
            "phone": "+1987654321",
            "admin_name": "Harvey Managing Admin",
            "admin_email": "harvey@apexcustom.com",
        }
        response = client.post("/api/admin/firms/", payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["admin_user"]["email"] == "harvey@apexcustom.com"
        assert response.data["admin_user"]["name"] == "Harvey Managing Admin"

        admin_user = User.objects.get(email="harvey@apexcustom.com")
        assert admin_user.name == "Harvey Managing Admin"
        assert admin_user.role == UserRole.FIRM_ADMIN

        # Verify email sent to admin_email
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["harvey@apexcustom.com"]

    def test_super_admin_create_firm_duplicate_admin_email_fails(self, super_admin, make_user):
        make_user(email="existing@law.com")
        client = get_auth_client(super_admin)
        payload = {
            "name": "Duplicate Practice",
            "type": "INDIVIDUAL",
            "email": "existing@law.com",
        }
        response = client.post("/api/admin/firms/", payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in str(response.data)

    def test_super_admin_update_firm_type(self, super_admin, individual_firm):
        client = get_auth_client(super_admin)
        response = client.patch(f"/api/admin/firms/{individual_firm.id}/", {"type": "MULTI"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "MULTI"
        individual_firm.refresh_from_db()
        assert individual_firm.type == FirmType.MULTI

    def test_firm_admin_update_firm_type_via_profile(self, individual_firm_admin, individual_firm):
        client = get_auth_client(individual_firm_admin)
        response = client.patch("/api/firm/profile/", {"type": "MULTI"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "MULTI"
        individual_firm.refresh_from_db()
        assert individual_firm.type == FirmType.MULTI

    def test_admin_cannot_create_firm_admin_via_users_endpoint(self, super_admin):
        client = get_auth_client(super_admin)
        payload = {
            "name": "New Solo Admin",
            "email": "newsolo@test.com",
            "role": UserRole.FIRM_ADMIN,
            "firm_name": "New Solo Firm",
            "firm_type": "INDIVIDUAL",
        }
        response = client.post("/api/admin/users/", payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "law firm admin" in response.data.get("error", "").lower()



@pytest.mark.django_db
class TestIndividualFirmPermissions:
    """
    Firm with INDIVIDUAL type:
    - Can add and manage matters and clients
    - CANNOT add or manage lawyers
    """

    def test_individual_firm_cannot_add_lawyer(self, individual_firm_admin):
        client = get_auth_client(individual_firm_admin)
        payload = {
            "name": "Associate Lawyer",
            "email": "associate@law.com",
        }
        response = client.post("/api/firm/lawyers/", payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "individual" in response.data.get("detail", "").lower()

    def test_individual_firm_list_lawyers_returns_empty(self, individual_firm_admin):
        client = get_auth_client(individual_firm_admin)
        response = client.get("/api/firm/lawyers/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_individual_firm_cannot_manage_lawyer(self, individual_firm_admin, make_user, individual_firm):
        dummy_lawyer = make_user(email="dummy@law.com", role=UserRole.LAWYER)
        dummy_lawyer.firm = individual_firm
        dummy_lawyer.save(update_fields=["firm"])

        client = get_auth_client(individual_firm_admin)
        # Cannot update
        response = client.patch(f"/api/firm/lawyers/{dummy_lawyer.id}/", {"name": "Updated Name"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Cannot soft-delete
        response = client.delete(f"/api/firm/lawyers/{dummy_lawyer.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Cannot reactivate
        response = client.post(f"/api/firm/lawyers/{dummy_lawyer.id}/reactivate/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_individual_firm_can_add_and_manage_clients(self, individual_firm_admin):
        client = get_auth_client(individual_firm_admin)
        # Create client
        payload = {
            "name": "Solo Client A",
            "email": "clienta@example.com",
            "phone": "+123456789",
        }
        response = client.post("/api/lawyer/clients/", payload)
        assert response.status_code == status.HTTP_201_CREATED
        client_id = response.data["id"]

        # List client
        list_resp = client.get("/api/lawyer/clients/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] >= 1

        # Retrieve client
        detail_resp = client.get(f"/api/lawyer/clients/{client_id}/")
        assert detail_resp.status_code == status.HTTP_200_OK
        assert detail_resp.data["name"] == "Solo Client A"

        # Update client
        update_resp = client.patch(f"/api/lawyer/clients/{client_id}/", {"name": "Solo Client A Updated"})
        assert update_resp.status_code == status.HTTP_200_OK
        assert update_resp.data["name"] == "Solo Client A Updated"

        # Soft delete client
        del_resp = client.delete(f"/api/lawyer/clients/{client_id}/")
        assert del_resp.status_code == status.HTTP_200_OK

        # Reactivate client
        reactivate_resp = client.post(f"/api/lawyer/clients/{client_id}/reactivate/")
        assert reactivate_resp.status_code == status.HTTP_200_OK

    def test_individual_firm_can_add_and_manage_matters(self, individual_firm_admin):
        client = get_auth_client(individual_firm_admin)
        # First create a client
        c_resp = client.post("/api/lawyer/clients/", {"name": "Matter Client", "email": "mc@example.com"})
        assert c_resp.status_code == status.HTTP_201_CREATED
        client_id = c_resp.data["id"]

        # Create matter
        matter_payload = {
            "title": "Solo Matter 1",
            "description": "Matter description",
            "client": client_id,
        }
        m_resp = client.post("/api/matters/", matter_payload)
        assert m_resp.status_code == status.HTTP_201_CREATED
        matter_id = m_resp.data["id"]

        # List matters
        list_resp = client.get("/api/matters/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] >= 1

        # Retrieve matter
        det_resp = client.get(f"/api/matters/{matter_id}/")
        assert det_resp.status_code == status.HTTP_200_OK
        assert det_resp.data["title"] == "Solo Matter 1"

        # Update matter
        up_resp = client.patch(f"/api/matters/{matter_id}/", {"title": "Updated Solo Matter 1"})
        assert up_resp.status_code == status.HTTP_200_OK
        assert up_resp.data["title"] == "Updated Solo Matter 1"

        # Delete matter
        del_resp = client.delete(f"/api/matters/{matter_id}/")
        assert del_resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestMultiFirmPermissions:
    """
    Firm with MULTI type:
    - Can only list matters and clients within firm
    - CANNOT create or manage (update/delete) matters and clients
    - CAN add, list, and manage lawyers
    """

    def test_multi_firm_can_add_and_manage_lawyers(self, multi_firm_admin):
        client = get_auth_client(multi_firm_admin)
        payload = {
            "name": "New Associate",
            "email": "newassociate@apexlaw.com",
        }
        response = client.post("/api/firm/lawyers/", payload)
        assert response.status_code == status.HTTP_201_CREATED
        lawyer_id = response.data["id"]

        # List lawyers
        list_resp = client.get("/api/firm/lawyers/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] >= 1

        # Update lawyer
        up_resp = client.patch(f"/api/firm/lawyers/{lawyer_id}/", {"name": "Associate Updated"})
        assert up_resp.status_code == status.HTTP_200_OK

        # Soft delete lawyer
        del_resp = client.delete(f"/api/firm/lawyers/{lawyer_id}/")
        assert del_resp.status_code == status.HTTP_200_OK

        # Reactivate lawyer
        react_resp = client.post(f"/api/firm/lawyers/{lawyer_id}/reactivate/")
        assert react_resp.status_code == status.HTTP_200_OK

    def test_multi_firm_can_list_firm_clients_but_cannot_create_or_manage(
        self, multi_firm_admin, multi_firm_lawyer, multi_firm
    ):
        # Lawyer creates a client
        lawyer_client = get_auth_client(multi_firm_lawyer)
        c_resp = lawyer_client.post("/api/lawyer/clients/", {"name": "Firm Client 1", "email": "fc1@example.com"})
        assert c_resp.status_code == status.HTTP_201_CREATED
        client_id = c_resp.data["id"]

        # Multi firm admin tries to list clients -> CAN LIST
        admin_client = get_auth_client(multi_firm_admin)
        list_resp = admin_client.get("/api/lawyer/clients/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] >= 1
        assert any(c["id"] == client_id for c in list_resp.data["results"])

        # Multi firm admin CANNOT create clients -> 403
        create_resp = admin_client.post("/api/lawyer/clients/", {"name": "Admin Client", "email": "ac@example.com"})
        assert create_resp.status_code == status.HTTP_403_FORBIDDEN

        # Multi firm admin CANNOT update clients -> 403
        up_resp = admin_client.patch(f"/api/lawyer/clients/{client_id}/", {"name": "Hacked Name"})
        assert up_resp.status_code == status.HTTP_403_FORBIDDEN

        # Multi firm admin CANNOT delete clients -> 403
        del_resp = admin_client.delete(f"/api/lawyer/clients/{client_id}/")
        assert del_resp.status_code == status.HTTP_403_FORBIDDEN

        # Multi firm admin CANNOT reactivate clients -> 403
        react_resp = admin_client.post(f"/api/lawyer/clients/{client_id}/reactivate/")
        assert react_resp.status_code == status.HTTP_403_FORBIDDEN

    def test_multi_firm_can_list_firm_matters_but_cannot_create_or_manage(
        self, multi_firm_admin, multi_firm_lawyer, multi_firm
    ):
        # Lawyer creates client and matter
        lawyer_client = get_auth_client(multi_firm_lawyer)
        c_resp = lawyer_client.post("/api/lawyer/clients/", {"name": "Firm Client 2", "email": "fc2@example.com"})
        assert c_resp.status_code == status.HTTP_201_CREATED
        client_id = c_resp.data["id"]

        m_resp = lawyer_client.post(
            "/api/matters/",
            {"title": "Firm Matter 2", "client": client_id, "description": "Matter desc"},
        )
        assert m_resp.status_code == status.HTTP_201_CREATED
        matter_id = m_resp.data["id"]

        # Multi firm admin tries to list matters -> CAN LIST
        admin_client = get_auth_client(multi_firm_admin)
        list_resp = admin_client.get("/api/matters/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] >= 1
        assert any(m["id"] == matter_id for m in list_resp.data["results"])

        # Multi firm admin CANNOT create matters -> 403
        create_resp = admin_client.post(
            "/api/matters/",
            {"title": "Admin Matter", "client": client_id},
        )
        assert create_resp.status_code == status.HTTP_403_FORBIDDEN

        # Multi firm admin CANNOT update matters -> 403
        up_resp = admin_client.patch(f"/api/matters/{matter_id}/", {"title": "Admin Updated Matter"})
        assert up_resp.status_code == status.HTTP_403_FORBIDDEN

        # Multi firm admin CANNOT delete matters -> 403
        del_resp = admin_client.delete(f"/api/matters/{matter_id}/")
        assert del_resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestExistingLawyerPermissions:
    """Existing lawyer can add and manage matters and clients, but cannot manage lawyers."""

    def test_lawyer_can_add_and_manage_matters_and_clients(self, multi_firm_lawyer):
        client = get_auth_client(multi_firm_lawyer)

        # Client CRUD
        c_resp = client.post("/api/lawyer/clients/", {"name": "Lawyer Client", "email": "lc@test.com"})
        assert c_resp.status_code == status.HTTP_201_CREATED
        client_id = c_resp.data["id"]

        up_c = client.patch(f"/api/lawyer/clients/{client_id}/", {"name": "Lawyer Client Renamed"})
        assert up_c.status_code == status.HTTP_200_OK

        # Matter CRUD
        m_resp = client.post("/api/matters/", {"title": "Lawyer Matter", "client": client_id})
        assert m_resp.status_code == status.HTTP_201_CREATED
        matter_id = m_resp.data["id"]

        up_m = client.patch(f"/api/matters/{matter_id}/", {"title": "Lawyer Matter Renamed"})
        assert up_m.status_code == status.HTTP_200_OK

        # Cannot onboard lawyer
        lawyer_onboard = client.post("/api/firm/lawyers/", {"name": "Associate", "email": "assoc@test.com"})
        assert lawyer_onboard.status_code == status.HTTP_403_FORBIDDEN
