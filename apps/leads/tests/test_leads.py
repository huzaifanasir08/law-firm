import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.leads.models import (
    Lead,
    LeadContactWay,
    LeadInterest,
    LeadInterestedFirm,
    LeadPreferredTime,
    LeadStatus,
)


@pytest.fixture
def superadmin_client(api_client, super_admin):
    refresh = RefreshToken.for_user(super_admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = super_admin
    return api_client


@pytest.fixture
def lawyer_client(api_client, lawyer):
    refresh = RefreshToken.for_user(lawyer)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = lawyer
    return api_client


@pytest.fixture
def sample_lead(db):
    return Lead.objects.create(
        name="John Doe",
        email="johndoe@example.com",
        phone="+1234567890",
        address="123 Main St, New York, NY",
        interest=LeadInterest.REGISTER,
        interested_firm=LeadInterestedFirm.INDIVIDUAL,
        status=LeadStatus.PENDING,
        preferred_time=LeadPreferredTime.TIME_8_10,
        preferred_contact_way=LeadContactWay.PHONE_CALL,
    )


@pytest.mark.django_db
class TestPublicLeadCreation:
    """Test public endpoint POST /api/leads/"""

    url = reverse("leads:lead-create")

    def test_public_create_lead_success(self, api_client):
        data = {
            "name": "Jane Smith",
            "email": "janesmith@example.com",
            "phone": "+9876543210",
            "address": "456 Elm Street",
            "interest": "register",
            "interested_firm": "multi",
            "preferred_time": "10-12",
            "preferred_contact_way": "whatsapp",
        }
        response = api_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Jane Smith"
        assert response.data["email"] == "janesmith@example.com"
        assert response.data["status"] == LeadStatus.PENDING
        assert Lead.objects.filter(email="janesmith@example.com").exists()

    def test_public_create_lead_duplicate_email_fails(self, api_client, sample_lead):
        data = {
            "name": "Another John",
            "email": "johndoe@example.com",  # Duplicate email
            "phone": "+1122334455",
            "address": "789 Pine Rd",
            "interest": "inquiry",
            "interested_firm": "individual",
            "preferred_time": "12-02",
            "preferred_contact_way": "phone_call",
        }
        response = api_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data or "error" in response.data
        assert any("already exists" in str(err) for err in response.data.values())

    def test_public_create_lead_duplicate_email_case_insensitive(self, api_client, sample_lead):
        data = {
            "name": "Case Insensitive John",
            "email": "JohnDoe@Example.com",  # Same email different casing
            "phone": "+1122334455",
            "interest": "other",
            "interested_firm": "multi",
            "preferred_time": "02-04",
            "preferred_contact_way": "whatsapp",
        }
        response = api_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_public_create_lead_normalization(self, api_client):
        """Test accepting spelling variants and space-separated choices."""
        data = {
            "name": "Normalize User",
            "email": "norm@example.com",
            "phone": "555-1234",
            "address": "Some Street",
            "interest": "inqury",  # Variant of inquiry
            "interested_firm": "indvidual",  # Variant of individual
            "preferred_time": "8-10",
            "preferred_contact_way": "phone call",  # Space instead of underscore
        }
        response = api_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        lead = Lead.objects.get(email="norm@example.com")
        assert lead.interest == LeadInterest.INQUIRY
        assert lead.interested_firm == LeadInterestedFirm.INDIVIDUAL
        assert lead.preferred_contact_way == LeadContactWay.PHONE_CALL

    def test_public_create_lead_missing_required_fields(self, api_client):
        data = {"name": "Incomplete"}
        response = api_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = response.data.get("error", "") or response.data.get("detail", "")
        assert "email" in error_msg
        assert "phone" in error_msg


@pytest.mark.django_db
class TestAdminLeadManagement:
    """Test Super Admin endpoints under /api/admin/leads/"""

    list_url = reverse("administration:lead-list")

    def test_super_admin_can_list_leads_with_pagination(self, superadmin_client, sample_lead):
        response = superadmin_client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "total_pages" in response.data
        assert "results" in response.data
        assert response.data["count"] == 1
        assert response.data["results"][0]["email"] == sample_lead.email

    def test_unauthenticated_cannot_access_admin_leads(self, api_client):
        response = api_client.get(self.list_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_superadmin_cannot_access_admin_leads(self, lawyer_client):
        response = lawyer_client.get(self.list_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_search_leads(self, superadmin_client):
        Lead.objects.create(
            name="Alice Wonder",
            email="alice@wonderland.com",
            phone="111222",
            interest=LeadInterest.REGISTER,
            interested_firm=LeadInterestedFirm.MULTI,
            preferred_time=LeadPreferredTime.TIME_8_10,
            preferred_contact_way=LeadContactWay.WHATSAPP,
        )
        Lead.objects.create(
            name="Bob Builder",
            email="bob@builder.com",
            phone="333444",
            interest=LeadInterest.INQUIRY,
            interested_firm=LeadInterestedFirm.INDIVIDUAL,
            preferred_time=LeadPreferredTime.TIME_10_12,
            preferred_contact_way=LeadContactWay.PHONE_CALL,
        )

        response = superadmin_client.get(f"{self.list_url}?search=Alice")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["name"] == "Alice Wonder"

        response = superadmin_client.get(f"{self.list_url}?search=builder.com")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["email"] == "bob@builder.com"

    def test_filter_leads_by_status_and_interest(self, superadmin_client):
        Lead.objects.create(
            name="Pending Lead",
            email="pending@test.com",
            phone="123",
            interest=LeadInterest.REGISTER,
            interested_firm=LeadInterestedFirm.INDIVIDUAL,
            status=LeadStatus.PENDING,
            preferred_time=LeadPreferredTime.TIME_8_10,
            preferred_contact_way=LeadContactWay.WHATSAPP,
        )
        Lead.objects.create(
            name="Contacted Lead",
            email="contacted@test.com",
            phone="456",
            interest=LeadInterest.INQUIRY,
            interested_firm=LeadInterestedFirm.MULTI,
            status=LeadStatus.CONTACTED,
            preferred_time=LeadPreferredTime.TIME_10_12,
            preferred_contact_way=LeadContactWay.PHONE_CALL,
        )

        # Filter by status
        res = superadmin_client.get(f"{self.list_url}?status=contacted")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["status"] == LeadStatus.CONTACTED

        # Filter by interest
        res = superadmin_client.get(f"{self.list_url}?interest=register")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["interest"] == LeadInterest.REGISTER

    def test_super_admin_can_retrieve_lead_detail(self, superadmin_client, sample_lead):
        detail_url = reverse("administration:lead-detail", kwargs={"pk": sample_lead.pk})
        response = superadmin_client.get(detail_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == sample_lead.id
        assert response.data["email"] == sample_lead.email

    def test_super_admin_can_edit_lead(self, superadmin_client, sample_lead):
        detail_url = reverse("administration:lead-detail", kwargs={"pk": sample_lead.pk})
        patch_data = {
            "status": "meeting scheduled",
            "notes": "Spoke on phone, scheduled consultation for Tuesday.",
        }
        response = superadmin_client.patch(detail_url, patch_data, format="json")
        assert response.status_code == status.HTTP_200_OK
        sample_lead.refresh_from_db()
        assert sample_lead.status == LeadStatus.MEETING_SCHEDULED
        assert sample_lead.notes == "Spoke on phone, scheduled consultation for Tuesday."

    def test_super_admin_edit_lead_same_email_succeeds(self, superadmin_client, sample_lead):
        """Updating lead keeping its existing email should not trigger duplicate email error."""
        detail_url = reverse("administration:lead-detail", kwargs={"pk": sample_lead.pk})
        patch_data = {
            "email": sample_lead.email,
            "status": LeadStatus.CONFIRMED,
        }
        response = superadmin_client.patch(detail_url, patch_data, format="json")
        assert response.status_code == status.HTTP_200_OK
        sample_lead.refresh_from_db()
        assert sample_lead.status == LeadStatus.CONFIRMED

    def test_super_admin_edit_lead_to_existing_other_email_fails(self, superadmin_client, sample_lead):
        other_lead = Lead.objects.create(
            name="Other Lead",
            email="other@example.com",
            phone="999",
            interest=LeadInterest.OTHER,
            interested_firm=LeadInterestedFirm.MULTI,
            preferred_time=LeadPreferredTime.TIME_12_02,
            preferred_contact_way=LeadContactWay.WHATSAPP,
        )
        detail_url = reverse("administration:lead-detail", kwargs={"pk": sample_lead.pk})
        patch_data = {
            "email": other_lead.email,
        }
        response = superadmin_client.patch(detail_url, patch_data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = response.data.get("error", "") or response.data.get("detail", "")
        assert "email" in error_msg
        assert "already exists" in error_msg

    def test_non_superadmin_cannot_edit_lead(self, lawyer_client, sample_lead):
        detail_url = reverse("administration:lead-detail", kwargs={"pk": sample_lead.pk})
        response = lawyer_client.patch(detail_url, {"status": "confirmed"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
