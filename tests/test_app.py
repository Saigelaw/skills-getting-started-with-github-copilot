"""
Tests for the Mergington High School API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": activity["description"],
            "schedule": activity["schedule"],
            "max_participants": activity["max_participants"],
            "participants": activity["participants"].copy()
        }
        for name, activity in activities.items()
    }
    
    yield
    
    # Restore original state
    for name in activities:
        activities[name]["participants"] = original_activities[name]["participants"].copy()


class TestRootEndpoint:
    """Test the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root redirects to /static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestActivitiesEndpoint:
    """Test the GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that all activities are returned"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "Chess Club" in data
        assert "Programming Class" in data
    
    def test_activities_have_required_fields(self, client):
        """Test that activities have all required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            assert "description" in activity_details
            assert "schedule" in activity_details
            assert "max_participants" in activity_details
            assert "participants" in activity_details
            assert isinstance(activity_details["participants"], list)
    
    def test_activities_participants_are_strings(self, client):
        """Test that all participants are strings (emails)"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            for participant in activity_details["participants"]:
                assert isinstance(participant, str)
                assert "@" in participant  # Basic email validation


class TestSignupEndpoint:
    """Test the POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_valid_activity_and_email(self, client, reset_activities):
        """Test signing up for an activity with valid inputs"""
        response = client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "newstudent@mergington.edu"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in activities["Chess Club"]["participants"]
    
    def test_signup_activity_not_found(self, client):
        """Test signing up for a non-existent activity"""
        response = client.post(
            "/activities/NonExistent%20Activity/signup",
            params={"email": "student@mergington.edu"}
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_signup_student_already_registered(self, client, reset_activities):
        """Test that a student cannot sign up twice for the same activity"""
        # First signup
        response1 = client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "duplicate@mergington.edu"}
        )
        assert response1.status_code == 200
        
        # Duplicate signup
        response2 = client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "duplicate@mergington.edu"}
        )
        assert response2.status_code == 400
        data = response2.json()
        assert "already signed up" in data["detail"].lower()
    
    def test_signup_updates_participant_count(self, client, reset_activities):
        """Test that signup correctly updates participant list"""
        activity_name = "Chess Club"
        original_count = len(activities[activity_name]["participants"])
        
        response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": "counttest@mergington.edu"}
        )
        assert response.status_code == 200
        assert len(activities[activity_name]["participants"]) == original_count + 1


class TestUnregisterEndpoint:
    """Test the POST /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_participant(self, client, reset_activities):
        """Test unregistering a participant from an activity"""
        activity_name = "Chess Club"
        email = "michael@mergington.edu"  # Already registered
        original_count = len(activities[activity_name]["participants"])
        
        response = client.post(
            f"/activities/{activity_name}/unregister",
            params={"email": email}
        )
        assert response.status_code == 200
        assert len(activities[activity_name]["participants"]) == original_count - 1
        assert email not in activities[activity_name]["participants"]
    
    def test_unregister_activity_not_found(self, client):
        """Test unregistering from a non-existent activity"""
        response = client.post(
            "/activities/NonExistent%20Activity/unregister",
            params={"email": "student@mergington.edu"}
        )
        assert response.status_code == 404
    
    def test_unregister_participant_not_registered(self, client, reset_activities):
        """Test that unregistering a non-registered student fails"""
        response = client.post(
            "/activities/Chess%20Club/unregister",
            params={"email": "notregistered@mergington.edu"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "not signed up" in data["detail"].lower()


class TestActivityCapacity:
    """Test activity capacity limits"""
    
    def test_can_view_max_participants(self, client):
        """Test that max_participants is accessible"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            assert activity_details["max_participants"] > 0
    
    def test_available_spots_calculation(self, client):
        """Test that available spots can be calculated from response"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            max_participants = activity_details["max_participants"]
            current_participants = len(activity_details["participants"])
            available_spots = max_participants - current_participants
            assert available_spots >= 0
